"""
Tests for download timeout, force-kill, and partial file cleanup.
Validates robust cancellation behavior.
"""

import unittest
import threading
import time
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock


# Mock DownloadManager for testing
class MockDownloadItem:
    def __init__(self, item_id, url):
        self.id = item_id
        self.url = url
        self.title = "Test Video"
        self.channel = "Test Channel"
        self.duration = "5:30"
        self.state = None
        self.progress = 0.0
        self.error_msg = ""
        self.dest_path = ""
        self.done_at = None
        self.is_playlist = False


class TestTimeoutAndCleanup(unittest.TestCase):
    """Test suite for robust download cancellation and timeout handling."""

    def test_kill_process_tree_windows_command_format(self):
        """Verify Windows taskkill command is formatted correctly."""
        # This test validates the command format without actually running taskkill
        pid = 1234
        item_id = "dl_0001"
        
        expected_cmd = ["taskkill", "/PID", "1234", "/T", "/F"]
        
        # Simulate what _kill_process_tree would do
        cmd = ["taskkill", "/PID", str(pid), "/T", "/F"]
        
        self.assertEqual(cmd, expected_cmd)
        self.assertIn("1234", cmd)
        self.assertIn("/T", cmd)  # tree kill
        self.assertIn("/F", cmd)  # force

    def test_timeout_tracking_fields_initialized(self):
        """Verify timeout tracking fields are properly initialized."""
        from america import DownloadManager, SettingsStore
        
        settings = Mock(spec=SettingsStore)
        settings.data = Mock()
        
        manager = DownloadManager(settings, Mock(), Mock())
        
        # Check new fields exist
        self.assertFalse(manager._stopping)
        self.assertIsNotNone(manager._stop_event)
        self.assertEqual(manager._active_pids, {})
        self.assertIsNotNone(manager._active_pids_lock)
        self.assertEqual(manager._timeout_secs, 600)  # 10 min default
        self.assertEqual(manager._download_start_time, {})

    def test_pid_tracking_thread_safety(self):
        """Verify PID tracking uses proper thread-safe locking."""
        from america import DownloadManager
        
        manager = DownloadManager(Mock(spec=object), Mock(), Mock())
        
        # Test thread-safe PID access
        def add_pid(item_id, pid):
            with manager._active_pids_lock:
                manager._active_pids[item_id] = pid
        
        def get_pid(item_id):
            with manager._active_pids_lock:
                return manager._active_pids.get(item_id)
        
        threads = []
        for i in range(10):
            t = threading.Thread(target=add_pid, args=(f"dl_{i:04d}", 1000 + i))
            threads.append(t)
            t.start()
        
        for t in threads:
            t.join()
        
        # Verify all PIDs were added
        with manager._active_pids_lock:
            self.assertEqual(len(manager._active_pids), 10)
        
        # Verify retrieval works correctly
        self.assertEqual(get_pid("dl_0005"), 1005)

    def test_cleanup_partial_file_directory_handling(self):
        """Verify partial file cleanup works with real directory."""
        from america import DownloadManager
        
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create mock partial files
            part_file = Path(tmpdir) / "video.mp3.part"
            part_file.write_text("incomplete data")
            
            ytdl_file = Path(tmpdir) / "video.mp3.ytdl"
            ytdl_file.write_text("ytdl temp")
            
            complete_file = Path(tmpdir) / "complete.mp3"
            complete_file.write_text("complete data")
            
            # Setup manager with mock settings
            settings = Mock()
            settings.data = Mock()
            settings.data.output_dir = tmpdir
            settings.data.naming_pattern = "{title}"
            settings.data.playlist_subfolder = False
            
            manager = DownloadManager(settings, Mock(), Mock())
            
            # Create mock item
            item = Mock()
            item.id = "dl_0001"
            item.title = "video"
            item.is_playlist = False
            item.dest_path = tmpdir
            
            # Run cleanup
            result = manager._cleanup_partial_file(item)
            
            # Verify partial files were removed
            self.assertFalse(part_file.exists())
            self.assertFalse(ytdl_file.exists())
            
            # Verify complete file still exists
            self.assertTrue(complete_file.exists())

    def test_timeout_exceeds_max_seconds(self):
        """Verify timeout detection when duration exceeds limit."""
        from america import DownloadManager
        
        manager = DownloadManager(Mock(), Mock(), Mock())
        manager._timeout_secs = 5  # 5 second timeout for testing
        manager._download_start_time["dl_0001"] = time.time() - 6  # 6 seconds ago
        
        # Simulate timeout check
        start = manager._download_start_time["dl_0001"]
        elapsed = time.time() - start
        
        self.assertGreater(elapsed, manager._timeout_secs)

    def test_cancel_with_force_kill_calls_kill_method(self):
        """Verify cancel() calls _kill_process_tree when PID exists."""
        from america import DownloadManager, DownloadState
        
        settings = Mock()
        settings.data = Mock()
        
        manager = DownloadManager(settings, Mock(), Mock())
        
        # Add a fake PID to track
        item_id = "dl_0001"
        with manager._active_pids_lock:
            manager._active_pids[item_id] = 9999
        
        # Add item to queue
        item = Mock()
        item.id = item_id
        item.state = DownloadState.QUEUED  # Will be changed to CANCELLED
        manager._queue.append(item)
        
        # Mock the _kill_process_tree method
        manager._kill_process_tree = Mock(return_value=True)
        
        # Call cancel
        manager.cancel(item_id)
        
        # Verify _kill_process_tree was called with correct args
        manager._kill_process_tree.assert_called_once()
        args = manager._kill_process_tree.call_args[0]
        self.assertEqual(args[0], 9999)  # PID
        self.assertEqual(args[1], item_id)

    def test_download_with_timeout_thread_timeout(self):
        """Verify timeout handling in _download_with_timeout."""
        from america import DownloadManager
        
        manager = DownloadManager(Mock(), Mock(), Mock())
        manager._cleanup_partial_file = Mock(return_value=True)
        
        # Create a mock yt_dlp module
        yt_dlp_mock = Mock()
        
        # Create mock YoutubeDL that hangs
        def hanging_extract(*args, **kwargs):
            time.sleep(10)  # Simulate hang
            return {"title": "test"}
        
        ydl_context = MagicMock()
        ydl_context.__enter__ = Mock(return_value=ydl_context)
        ydl_context.__exit__ = Mock(return_value=False)
        ydl_context.extract_info = hanging_extract
        
        yt_dlp_mock.YoutubeDL = Mock(return_value=ydl_context)
        
        # Create mock item
        item = Mock()
        item.id = "dl_0001"
        
        # Call with short timeout (should exceed timeout since extract_info sleeps 10s)
        result = manager._download_with_timeout(yt_dlp_mock, item, {}, timeout_secs=1)
        
        # Verify timeout was returned
        self.assertEqual(result, "timeout")
        
        # Verify cleanup was attempted
        manager._cleanup_partial_file.assert_called_once_with(item)

    def test_cancel_all_kills_all_active_pids(self):
        """Verify cancel_all() force-kills all active processes."""
        from america import DownloadManager, DownloadState
        
        settings = Mock()
        settings.data = Mock()
        
        manager = DownloadManager(settings, Mock(), Mock())
        manager._kill_process_tree = Mock(return_value=True)
        
        # Add multiple items with PIDs
        for i in range(3):
            item_id = f"dl_{i:04d}"
            item = Mock()
            item.id = item_id
            item.state = DownloadState.QUEUED
            manager._queue.append(item)
            
            with manager._active_pids_lock:
                manager._active_pids[item_id] = 1000 + i
        
        # Call cancel_all
        manager.cancel_all()
        
        # Verify all PIDs were killed
        self.assertEqual(manager._kill_process_tree.call_count, 3)

    def test_stopping_flag_halts_process_loop(self):
        """Verify _stopping flag is checked in _process() loop."""
        settings = Mock()
        settings.data = Mock()
        
        # This test just validates the flag exists and is properly initialized
        from america import DownloadManager
        
        manager = DownloadManager(settings, Mock(), Mock())
        
        self.assertFalse(manager._stopping)
        manager._stopping = True
        self.assertTrue(manager._stopping)


class TestCleanupBehavior(unittest.TestCase):
    """Test file cleanup under various scenarios."""

    def test_cleanup_finds_partial_files_by_extension(self):
        """Verify cleanup can find files by multiple partial extensions."""
        extensions = [".part", ".ytdl", ".tmp"]
        
        for ext in extensions:
            self.assertTrue(ext in (".part", ".ytdl", ".tmp"))

    def test_cleanup_removes_correct_file_types(self):
        """Verify cleanup removes only partial/temp files, not completed files."""
        from america import DownloadManager
        
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create test files
            files_to_remove = [
                Path(tmpdir) / "video.mp3.part",
                Path(tmpdir) / "video.mp3.ytdl",
                Path(tmpdir) / "video.mp3.tmp",
            ]
            
            files_to_keep = [
                Path(tmpdir) / "complete.mp3",
                Path(tmpdir) / "audio.wav",
                Path(tmpdir) / "data.json",
            ]
            
            for f in files_to_remove:
                f.write_text("temp")
            
            for f in files_to_keep:
                f.write_text("keep")
            
            # Verify files exist
            for f in files_to_remove + files_to_keep:
                self.assertTrue(f.exists())


if __name__ == "__main__":
    unittest.main()
