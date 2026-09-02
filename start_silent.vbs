Set WshShell = CreateObject("WScript.Shell")
WshShell.CurrentDirectory = "d:\download_music"
WshShell.Run "cmd /c d:\download_music\start_all.bat", 0, False
Set WshShell = Nothing


