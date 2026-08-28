/**
 * América Web — Modern Frontend Application Logic
 * Real-time WebSockets, Video/Playlist extraction, Audio Player, Download Queue & QR Code LAN Pairing
 */

(function () {
  'use strict';

  // State
  let currentFormat = 'mp3';
  let currentQuality = '320';
  let currentInfo = null;
  let activeJobs = new Map();
  let ws = null;
  let systemInfo = { local_ip: '127.0.0.1' };
  let selectedPlaylistItems = new Set();
  let userDirectoryHandle = null;
  let userDirectoryName = localStorage.getItem('america_dest_folder_name') || 'Downloads do Navegador (Padrão)';

  // DOM Elements
  const urlInput = document.getElementById('urlInput');
  const btnPaste = document.getElementById('btnPaste');
  const btnClear = document.getElementById('btnClear');
  const formatChips = document.querySelectorAll('.format-chips .chip');
  const btnFetch = document.getElementById('btnFetch');
  const fetchSpinner = document.getElementById('fetchSpinner');

  // Preview Section
  const previewSection = document.getElementById('previewSection');
  const previewThumb = document.getElementById('previewThumb');
  const previewDuration = document.getElementById('previewDuration');
  const previewTitle = document.getElementById('previewTitle');
  const previewUploader = document.getElementById('previewUploader');
  const previewExtra = document.getElementById('previewExtra');
  const previewTypeTag = document.getElementById('previewTypeTag');
  const btnStartDownload = document.getElementById('btnStartDownload');
  const btnOpenPlaylistModal = document.getElementById('btnOpenPlaylistModal');
  const playlistItemCount = document.getElementById('playlistItemCount');

  // Tabs & Lists
  const tabBtnActive = document.getElementById('tabBtnActive');
  const tabBtnHistory = document.getElementById('tabBtnHistory');
  const tabActive = document.getElementById('tabActive');
  const tabHistory = document.getElementById('tabHistory');
  const emptyActive = document.getElementById('emptyActive');
  const emptyHistory = document.getElementById('emptyHistory');
  const activeDownloadsGrid = document.getElementById('activeDownloadsGrid');
  const historyList = document.getElementById('historyList');
  const activeCount = document.getElementById('activeCount');

  // Audio Player
  const audioPlayerBar = document.getElementById('audioPlayerBar');
  const html5Audio = document.getElementById('html5Audio');
  const playerCover = document.getElementById('playerCover');
  const playerTitle = document.getElementById('playerTitle');
  const playerArtist = document.getElementById('playerArtist');
  const btnPlayerPlay = document.getElementById('btnPlayerPlay');
  const playerPlayIcon = document.getElementById('playerPlayIcon');
  const playerProgress = document.getElementById('playerProgress');
  const playerCurrentTime = document.getElementById('playerCurrentTime');
  const playerTotalTime = document.getElementById('playerTotalTime');
  const btnPlayerBack10 = document.getElementById('btnPlayerBack10');
  const btnPlayerFwd10 = document.getElementById('btnPlayerFwd10');
  const volumeSlider = document.getElementById('volumeSlider');
  const volumeIcon = document.getElementById('volumeIcon');
  const btnPlayerSave = document.getElementById('btnPlayerSave');
  const btnPlayerClose = document.getElementById('btnPlayerClose');

  // Modals
  const playlistModal = document.getElementById('playlistModal');
  const btnClosePlaylistModal = document.getElementById('btnClosePlaylistModal');
  const btnCancelPlaylist = document.getElementById('btnCancelPlaylist');
  const btnConfirmPlaylistDownload = document.getElementById('btnConfirmPlaylistDownload');
  const modalPlaylistTitle = document.getElementById('modalPlaylistTitle');
  const playlistItemsContainer = document.getElementById('playlistItemsContainer');
  const selectedCountBadge = document.getElementById('selectedCountBadge');
  const btnSelectAll = document.getElementById('btnSelectAll');
  const btnUnselectAll = document.getElementById('btnUnselectAll');

  const lanModal = document.getElementById('lanModal');
  const btnShareLan = document.getElementById('btnShareLan');
  const btnCloseLanModal = document.getElementById('btnCloseLanModal');
  const lanUrlText = document.getElementById('lanUrlText');
  const btnCopyLanUrl = document.getElementById('btnCopyLanUrl');
  const serverStatusPill = document.getElementById('serverStatusPill');

  // Folder Modal
  const folderModal = document.getElementById('folderModal');
  const btnSelectFolder = document.getElementById('btnSelectFolder');
  const btnCloseFolderModal = document.getElementById('btnCloseFolderModal');
  const btnPickDirectory = document.getElementById('btnPickDirectory');
  const btnResetFolder = document.getElementById('btnResetFolder');
  const currentFolderText = document.getElementById('currentFolderText');
  const folderLabel = document.getElementById('folderLabel');

  // Theme
  const btnToggleTheme = document.getElementById('btnToggleTheme');
  const themeIcon = document.getElementById('themeIcon');

  // Toast Container
  const toastContainer = document.getElementById('toastContainer');

  // ─────────────────────────────────────────────────────────────
  // INIT & LIFECYCLE
  // ─────────────────────────────────────────────────────────────
  async function init() {
    setupTheme();
    setupEventListeners();
    setupWebSocket();
    await fetchSystemInfo();
    await loadHistory();
    await loadInitialJobs();
  }

  // ─────────────────────────────────────────────────────────────
  // THEME SWITCHER
  // ─────────────────────────────────────────────────────────────
  function setupTheme() {
    const savedTheme = localStorage.getItem('america_theme') || 'dark';
    document.documentElement.setAttribute('data-theme', savedTheme);
    updateThemeIcon(savedTheme);

    btnToggleTheme.addEventListener('click', () => {
      const current = document.documentElement.getAttribute('data-theme');
      const next = current === 'dark' ? 'light' : 'dark';
      document.documentElement.setAttribute('data-theme', next);
      localStorage.setItem('america_theme', next);
      updateThemeIcon(next);
    });
  }

  function updateThemeIcon(theme) {
    if (theme === 'light') {
      themeIcon.className = 'fa-solid fa-sun';
    } else {
      themeIcon.className = 'fa-solid fa-moon';
    }
  }

  // ─────────────────────────────────────────────────────────────
  // EVENT LISTENERS
  // ─────────────────────────────────────────────────────────────
  function setupEventListeners() {
    // URL input typing and clear button
    urlInput.addEventListener('input', () => {
      btnClear.classList.toggle('hidden', !urlInput.value.trim());
      // Auto-extract if valid full youtube url is pasted
      const val = urlInput.value.trim();
      if ((val.includes('youtube.com/watch') || val.includes('youtu.be/') || val.includes('youtube.com/playlist')) && val.length > 20) {
        // Debounced auto-fetch
        debounce(fetchUrlInfo, 600)();
      }
    });

    urlInput.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') {
        fetchUrlInfo();
      }
    });

    btnClear.addEventListener('click', () => {
      urlInput.value = '';
      btnClear.classList.add('hidden');
      previewSection.classList.add('hidden');
      currentInfo = null;
      urlInput.focus();
    });

    // Paste button
    btnPaste.addEventListener('click', async () => {
      try {
        const text = await navigator.clipboard.readText();
        if (text) {
          urlInput.value = text.trim();
          btnClear.classList.remove('hidden');
          fetchUrlInfo();
        }
      } catch (err) {
        showToast('Permissão de área de transferência não concedida. Cole manualmente.', 'info');
      }
    });

    // Format Chips
    formatChips.forEach(chip => {
      chip.addEventListener('click', () => {
        formatChips.forEach(c => c.classList.remove('active'));
        chip.classList.add('active');
        currentFormat = chip.getAttribute('data-format');
        currentQuality = chip.getAttribute('data-quality');
      });
    });

    // Fetch button
    btnFetch.addEventListener('click', () => {
      fetchUrlInfo();
    });

    // Download Single Action
    btnStartDownload.addEventListener('click', () => {
      if (currentInfo) {
        startDownloadJob(currentInfo.url || urlInput.value.trim());
      }
    });

    // Open Playlist Modal
    btnOpenPlaylistModal.addEventListener('click', () => {
      if (currentInfo && currentInfo.is_playlist) {
        openPlaylistModal();
      }
    });

    // Tabs
    tabBtnActive.addEventListener('click', () => switchTab('active'));
    tabBtnHistory.addEventListener('click', () => switchTab('history'));

    // Audio Player Controls
    btnPlayerPlay.addEventListener('click', togglePlay);
    btnPlayerBack10.addEventListener('click', () => { html5Audio.currentTime = Math.max(0, html5Audio.currentTime - 10); });
    btnPlayerFwd10.addEventListener('click', () => { html5Audio.currentTime = Math.min(html5Audio.duration || 0, html5Audio.currentTime + 10); });
    btnPlayerClose.addEventListener('click', () => {
      html5Audio.pause();
      audioPlayerBar.classList.add('hidden');
    });

    html5Audio.addEventListener('timeupdate', updateAudioProgress);
    html5Audio.addEventListener('ended', () => {
      playerPlayIcon.className = 'fa-solid fa-play';
      playerProgress.value = 0;
    });

    playerProgress.addEventListener('input', (e) => {
      if (html5Audio.duration) {
        html5Audio.currentTime = (e.target.value / 100) * html5Audio.duration;
      }
    });

    volumeSlider.addEventListener('input', (e) => {
      html5Audio.volume = e.target.value;
      if (e.target.value == 0) {
        volumeIcon.className = 'fa-solid fa-volume-xmark';
      } else if (e.target.value < 0.5) {
        volumeIcon.className = 'fa-solid fa-volume-low';
      } else {
        volumeIcon.className = 'fa-solid fa-volume-high';
      }
    });

    // Playlist Modal Toolbars
    btnSelectAll.addEventListener('click', () => {
      if (!currentInfo || !currentInfo.entries) return;
      currentInfo.entries.forEach(e => selectedPlaylistItems.add(e.id));
      renderPlaylistItems();
    });

    btnUnselectAll.addEventListener('click', () => {
      selectedPlaylistItems.clear();
      renderPlaylistItems();
    });

    btnClosePlaylistModal.addEventListener('click', () => playlistModal.classList.add('hidden'));
    btnCancelPlaylist.addEventListener('click', () => playlistModal.classList.add('hidden'));

    btnConfirmPlaylistDownload.addEventListener('click', () => {
      if (selectedPlaylistItems.size === 0) {
        showToast('Selecione pelo menos uma música para baixar.', 'error');
        return;
      }
      const selectedList = currentInfo.entries.filter(e => selectedPlaylistItems.has(e.id));
      playlistModal.classList.add('hidden');
      startDownloadJob(urlInput.value.trim(), selectedList);
    });

    // LAN Modal
    btnShareLan.addEventListener('click', openLanModal);
    btnCloseLanModal.addEventListener('click', () => lanModal.classList.add('hidden'));
    btnCopyLanUrl.addEventListener('click', () => {
      const text = lanUrlText.textContent;
      navigator.clipboard.writeText(text);
      showToast('Endereço copiado para a área de transferência!', 'success');
    });

    // Destination Folder Modal
    btnSelectFolder.addEventListener('click', () => {
      updateFolderUI();
      folderModal.classList.remove('hidden');
    });
    btnCloseFolderModal.addEventListener('click', () => folderModal.classList.add('hidden'));
    btnPickDirectory.addEventListener('click', pickLocalFolder);
    btnResetFolder.addEventListener('click', resetLocalFolder);
    updateFolderUI();
  }

  // ─────────────────────────────────────────────────────────────
  // DESTINATION FOLDER MANAGEMENT (FILE SYSTEM ACCESS API)
  // ─────────────────────────────────────────────────────────────
  async function pickLocalFolder() {
    if ('showDirectoryPicker' in window) {
      try {
        const handle = await window.showDirectoryPicker({ mode: 'readwrite' });
        userDirectoryHandle = handle;
        userDirectoryName = handle.name;
        localStorage.setItem('america_dest_folder_name', handle.name);
        updateFolderUI();
        showToast(`Pasta "${handle.name}" definida para salvar os downloads!`, 'success');
        folderModal.classList.add('hidden');
      } catch (e) {
        if (e.name !== 'AbortError') {
          console.error(e);
          showToast('Permissão de pasta não concedida.', 'error');
        }
      }
    } else {
      showToast('Neste dispositivo/navegador, os arquivos são salvos na sua pasta padrão de Downloads.', 'info');
      folderModal.classList.add('hidden');
    }
  }

  function resetLocalFolder() {
    userDirectoryHandle = null;
    userDirectoryName = 'Downloads do Navegador (Padrão)';
    localStorage.removeItem('america_dest_folder_name');
    updateFolderUI();
    showToast('Restaurado para a pasta padrão de Downloads.', 'info');
    folderModal.classList.add('hidden');
  }

  function updateFolderUI() {
    if (currentFolderText) {
      currentFolderText.textContent = userDirectoryName;
    }
    if (folderLabel) {
      if (userDirectoryName && userDirectoryName !== 'Downloads do Navegador (Padrão)') {
        folderLabel.textContent = `📁 ${userDirectoryName}`;
      } else {
        folderLabel.textContent = 'Pasta de Destino';
      }
    }
  }

  // ─────────────────────────────────────────────────────────────
  // WEBSOCKET FOR REAL-TIME PROGRESS
  // ─────────────────────────────────────────────────────────────
  function setupWebSocket() {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/ws/progress`;

    try {
      ws = new WebSocket(wsUrl);

      ws.onopen = () => {
        updateServerStatus(true);
      };

      ws.onmessage = (event) => {
        try {
          const msg = JSON.parse(event.data);
          if (msg.type === 'init_state') {
            (msg.jobs || []).forEach(job => {
              activeJobs.set(job.id, job);
            });
            renderActiveJobs();
          } else if (msg.type === 'job_update' && msg.job) {
            handleJobUpdate(msg.job);
          }
        } catch (e) {
          console.error('Error parsing WS message:', e);
        }
      };

      ws.onclose = () => {
        updateServerStatus(false);
        // Reconnect after 3 seconds
        setTimeout(setupWebSocket, 3000);
      };

      ws.onerror = () => {
        updateServerStatus(false);
      };
    } catch (e) {
      updateServerStatus(false);
    }
  }

  function updateServerStatus(connected) {
    const dot = serverStatusPill.querySelector('.status-dot');
    const text = serverStatusPill.querySelector('.status-text');
    if (connected) {
      dot.className = 'status-dot online';
      text.textContent = 'Conectado';
      serverStatusPill.style.borderColor = 'rgba(34, 197, 94, 0.25)';
    } else {
      dot.className = 'status-dot offline';
      text.textContent = 'Reconectando...';
      serverStatusPill.style.borderColor = 'rgba(239, 68, 68, 0.25)';
    }
  }

  // ─────────────────────────────────────────────────────────────
  // FETCH VIDEO / PLAYLIST METADATA
  // ─────────────────────────────────────────────────────────────
  async function fetchUrlInfo() {
    const url = urlInput.value.trim();
    if (!url) {
      showToast('Por favor, informe o link do vídeo ou playlist.', 'error');
      return;
    }

    setFetchingState(true);

    try {
      const response = await fetch('/api/info', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url })
      });

      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.detail || 'Falha ao buscar informações da URL.');
      }

      currentInfo = data;
      renderPreview(data);
      showToast('Informações carregadas com sucesso!', 'success');
    } catch (err) {
      showToast(err.message || 'Erro ao processar o link.', 'error');
    } finally {
      setFetchingState(false);
    }
  }

  function setFetchingState(isFetching) {
    btnFetch.disabled = isFetching;
    if (isFetching) {
      fetchSpinner.classList.remove('hidden');
      btnFetch.querySelector('.btn-content').classList.add('hidden');
    } else {
      fetchSpinner.classList.add('hidden');
      btnFetch.querySelector('.btn-content').classList.remove('hidden');
    }
  }

  function renderPreview(info) {
    previewThumb.src = info.thumbnail || 'https://images.unsplash.com/photo-1511671782779-c97d3d27a1d4?w=500&auto=format&fit=crop&q=60';
    previewTitle.textContent = info.title;
    previewUploader.innerHTML = `<i class="fa-solid fa-user"></i> ${info.uploader || 'YouTube'}`;

    if (info.is_playlist) {
      previewTypeTag.innerHTML = `<i class="fa-solid fa-list-check"></i> <span>Playlist Completa (${info.count} músicas)</span>`;
      previewDuration.textContent = `${info.count} faixas`;
      previewExtra.innerHTML = `<i class="fa-solid fa-file-zipper"></i> Empacotamento automático em ZIP`;

      btnStartDownload.innerHTML = `<i class="fa-solid fa-file-zipper"></i> Baixar Playlist Inteira em ZIP`;
      btnOpenPlaylistModal.classList.remove('hidden');
      playlistItemCount.textContent = info.count;

      // Select all by default
      selectedPlaylistItems.clear();
      (info.entries || []).forEach(e => selectedPlaylistItems.add(e.id));
    } else {
      previewTypeTag.innerHTML = `<i class="fa-solid fa-music"></i> <span>Vídeo Único</span>`;
      previewDuration.textContent = info.duration_string || '00:00';
      previewExtra.innerHTML = `<i class="fa-solid fa-circle-check"></i> Pronto para conversão em ${currentFormat.toUpperCase()}`;

      btnStartDownload.innerHTML = `<i class="fa-solid fa-download"></i> Baixar ${currentFormat.toUpperCase()} (${currentQuality}k)`;
      btnOpenPlaylistModal.classList.add('hidden');
    }

    previewSection.classList.remove('hidden');
  }

  // ─────────────────────────────────────────────────────────────
  // DOWNLOAD JOB INITIATION
  // ─────────────────────────────────────────────────────────────
  async function startDownloadJob(url, entries = null) {
    try {
      showToast('Iniciando download...', 'info');
      switchTab('active');

      const response = await fetch('/api/download', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          url: url,
          format: currentFormat,
          quality: currentQuality,
          entries: entries
        })
      });

      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.detail || 'Não foi possível iniciar o download.');
      }

      if (data.job) {
        activeJobs.set(data.job.id, data.job);
        renderActiveJobs();
      }
    } catch (err) {
      showToast(err.message || 'Erro ao iniciar download.', 'error');
    }
  }

  function handleJobUpdate(job) {
    activeJobs.set(job.id, job);
    renderActiveJobs();

    if (job.status === 'completed') {
      showToast(`"${job.title}" concluído!`, 'success');
      loadHistory();
      // Auto-trigger browser file download
      triggerBrowserDownload(job.id, job.output_filename);
    } else if (job.status === 'error') {
      showToast(`Erro no download: ${job.error_message || 'Desconhecido'}`, 'error');
    }
  }

  async function triggerBrowserDownload(jobId, filename) {
    const safeFilename = filename || 'download.mp3';

    // If the user selected a specific folder on their computer via File System Access API
    if (userDirectoryHandle) {
      try {
        showToast(`Salvando diretamente na pasta "${userDirectoryName}"...`, 'info');
        const response = await fetch(`/api/file/${jobId}`);
        if (!response.ok) throw new Error('Falha ao obter arquivo do servidor.');
        const blob = await response.blob();

        const fileHandle = await userDirectoryHandle.getFileHandle(safeFilename, { create: true });
        const writable = await fileHandle.createWritable();
        await writable.write(blob);
        await writable.close();

        showToast(`Arquivo salvo com sucesso na pasta "${userDirectoryName}"!`, 'success');
        return;
      } catch (err) {
        console.warn('Gravação direta na pasta local falhou, usando download padrão do navegador:', err);
      }
    }

    // Default Browser Download (standard folder / browser prompt)
    const link = document.createElement('a');
    link.href = `/api/file/${jobId}`;
    link.download = safeFilename;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  }

  // ─────────────────────────────────────────────────────────────
  // RENDER ACTIVE JOBS
  // ─────────────────────────────────────────────────────────────
  function renderActiveJobs() {
    const jobs = Array.from(activeJobs.values()).reverse();
    const activeList = jobs.filter(j => ['queued', 'preparing', 'downloading', 'converting'].includes(j.status));
    activeCount.textContent = activeList.length;

    if (jobs.length === 0) {
      emptyActive.classList.remove('hidden');
      activeDownloadsGrid.innerHTML = '';
      return;
    }

    emptyActive.classList.add('hidden');
    activeDownloadsGrid.innerHTML = jobs.map(job => createJobCardHTML(job)).join('');

    // Attach card event listeners
    jobs.forEach(job => {
      const card = document.getElementById(`job-${job.id}`);
      if (!card) return;

      const btnCancel = card.querySelector('.btn-cancel-job');
      if (btnCancel) {
        btnCancel.addEventListener('click', () => cancelJob(job.id));
      }

      const btnPlay = card.querySelector('.btn-play-job');
      if (btnPlay) {
        btnPlay.addEventListener('click', () => playTrack(job));
      }
    });
  }

  function createJobCardHTML(job) {
    let badgeText = job.status_label || 'Baixando';
    if (job.status === 'preparing') {
      badgeClass = 'badge-downloading';
    } else if (job.status === 'converting') {
      badgeClass = 'badge-converting';
      isConverting = true;
    } else if (job.status === 'completed') {
      badgeClass = 'badge-completed';
    } else if (job.status === 'error') {
      badgeClass = 'badge-error';
    } else if (job.status === 'cancelled') {
      badgeClass = 'badge-error';
    }

    const thumb = job.thumbnail || 'https://images.unsplash.com/photo-1511671782779-c97d3d27a1d4?w=500&auto=format&fit=crop&q=60';
    const progress = Math.min(100, Math.max(0, job.progress || 0)).toFixed(1);

    return `
      <div class="download-card" id="job-${job.id}">
        <img src="${thumb}" alt="Capa" class="download-thumb" />
        <div class="download-info">
          <div class="download-header-row">
            <h4 class="download-title" title="${escapeHtml(job.title)}">${escapeHtml(job.title)}</h4>
            <span class="download-status-badge ${badgeClass}">${escapeHtml(badgeText)}</span>
          </div>

          <div class="progress-bar-container">
            <div class="progress-bar-fill ${isConverting ? 'converting' : ''}" style="width: ${progress}%"></div>
          </div>

          <div class="download-meta-row">
            <span>${job.format_type.toUpperCase()} • ${job.quality}k</span>
            ${job.error_message ? `<span style="color: var(--color-danger);">${escapeHtml(job.error_message)}</span>` : `<span>${job.speed_str ? job.speed_str + ' • ' : ''}${job.eta_str ? 'ETA: ' + job.eta_str + ' • ' : ''}${progress}%</span>`}
          </div>
        </div>

        <div class="download-actions-row">
          ${job.status === 'completed' ? `
            <button class="btn-card-action btn-play-job" title="Ouvir agora"><i class="fa-solid fa-play"></i> Ouvir</button>
            <a href="/api/file/${job.id}" class="btn-card-action btn-accent" download="${job.output_filename}"><i class="fa-solid fa-download"></i> Salvar</a>
          ` : ''}
          ${['preparing', 'downloading', 'converting'].includes(job.status) ? `
            <button class="btn-card-action btn-cancel-job" title="Cancelar"><i class="fa-solid fa-xmark"></i> Cancelar</button>
          ` : ''}
        </div>
      </div>
    `;
  }

  async function cancelJob(jobId) {
    try {
      await fetch(`/api/cancel/${jobId}`, { method: 'POST' });
      showToast('Download cancelado.', 'info');
    } catch (e) {
      console.error(e);
    }
  }

  // ─────────────────────────────────────────────────────────────
  // HISTORY & STORAGE
  // ─────────────────────────────────────────────────────────────
  async function loadHistory() {
    try {
      const res = await fetch('/api/history');
      const history = await res.json();
      renderHistory(history);
    } catch (e) {
      console.error('Failed to load history:', e);
    }
  }

  function renderHistory(items) {
    if (!items || items.length === 0) {
      emptyHistory.classList.remove('hidden');
      historyList.innerHTML = '';
      return;
    }

    emptyHistory.classList.add('hidden');
    historyList.innerHTML = items.map(item => `
      <div class="history-card" id="history-${item.id}">
        <div class="history-left">
          <img src="${item.thumbnail || ''}" alt="Capa" class="history-thumb" />
          <div class="history-text">
            <div class="history-title" title="${escapeHtml(item.title)}">${escapeHtml(item.title)}</div>
            <div class="history-subtitle">
              ${item.uploader || 'YouTube'} • ${item.format_type.toUpperCase()} ${item.quality}k • ${item.duration_string || ''}
            </div>
          </div>
        </div>

        <div class="history-actions">
          <button class="btn-card-action btn-play-history" data-id="${item.id}" title="Ouvir"><i class="fa-solid fa-play"></i></button>
          <a href="/api/file/${item.id}" class="btn-card-action" download="${item.filename}" title="Baixar"><i class="fa-solid fa-download"></i></a>
          <button class="btn-card-action btn-delete-history" data-id="${item.id}" title="Excluir"><i class="fa-solid fa-trash"></i></button>
        </div>
      </div>
    `).join('');

    // Attach listeners
    items.forEach(item => {
      const el = document.getElementById(`history-${item.id}`);
      if (!el) return;

      el.querySelector('.btn-play-history').addEventListener('click', () => playTrack(item));
      el.querySelector('.btn-delete-history').addEventListener('click', async () => {
        await fetch(`/api/history/${item.id}`, { method: 'DELETE' });
        loadHistory();
        showToast('Item removido do histórico.', 'info');
      });
    });
  }

  // ─────────────────────────────────────────────────────────────
  // AUDIO PLAYER
  // ─────────────────────────────────────────────────────────────
  function playTrack(track) {
    if (!track) return;
    if (track.is_playlist) {
      showToast('Para playlists, baixe o arquivo ZIP para escutar todas as músicas.', 'info');
      return;
    }

    playerCover.src = track.thumbnail || '';
    playerTitle.textContent = track.title || 'Música';
    playerArtist.textContent = track.uploader || 'América Web';
    btnPlayerSave.href = `/api/file/${track.id}`;
    btnPlayerSave.download = track.output_filename || `${track.title}.mp3`;

    html5Audio.src = `/api/stream/${track.id}`;
    html5Audio.play().then(() => {
      playerPlayIcon.className = 'fa-solid fa-pause';
    }).catch(err => {
      console.warn('Playback error:', err);
    });

    audioPlayerBar.classList.remove('hidden');
  }

  function togglePlay() {
    if (html5Audio.paused) {
      html5Audio.play();
      playerPlayIcon.className = 'fa-solid fa-pause';
    } else {
      html5Audio.pause();
      playerPlayIcon.className = 'fa-solid fa-play';
    }
  }

  function updateAudioProgress() {
    if (!html5Audio.duration) return;
    const pct = (html5Audio.currentTime / html5Audio.duration) * 100;
    playerProgress.value = pct;
    playerCurrentTime.textContent = formatTime(html5Audio.currentTime);
    playerTotalTime.textContent = formatTime(html5Audio.duration);
  }

  function formatTime(seconds) {
    if (isNaN(seconds) || seconds < 0) return '00:00';
    const m = Math.floor(seconds / 60);
    const s = Math.floor(seconds % 60);
    return `${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;
  }

  // ─────────────────────────────────────────────────────────────
  // PLAYLIST MODAL
  // ─────────────────────────────────────────────────────────────
  function openPlaylistModal() {
    if (!currentInfo || !currentInfo.entries) return;
    modalPlaylistTitle.textContent = currentInfo.title;
    renderPlaylistItems();
    playlistModal.classList.remove('hidden');
  }

  function renderPlaylistItems() {
    if (!currentInfo || !currentInfo.entries) return;
    selectedCountBadge.textContent = `${selectedPlaylistItems.size} de ${currentInfo.entries.length}`;

    playlistItemsContainer.innerHTML = currentInfo.entries.map(entry => `
      <label class="playlist-item-row">
        <input type="checkbox" data-id="${entry.id}" ${selectedPlaylistItems.has(entry.id) ? 'checked' : ''} />
        <img src="${entry.thumbnail || ''}" alt="Capa" class="playlist-item-thumb" />
        <span class="playlist-item-title" title="${escapeHtml(entry.title)}">${escapeHtml(entry.title)}</span>
        <span class="playlist-item-duration">${entry.duration_string || ''}</span>
      </label>
    `).join('');

    // Attach change handlers
    playlistItemsContainer.querySelectorAll('input[type="checkbox"]').forEach(chk => {
      chk.addEventListener('change', (e) => {
        const id = e.target.getAttribute('data-id');
        if (e.target.checked) {
          selectedPlaylistItems.add(id);
        } else {
          selectedPlaylistItems.delete(id);
        }
        selectedCountBadge.textContent = `${selectedPlaylistItems.size} de ${currentInfo.entries.length}`;
      });
    });
  }

  // ─────────────────────────────────────────────────────────────
  // LAN ACCESS & QR CODE MODAL
  // ─────────────────────────────────────────────────────────────
  async function fetchSystemInfo() {
    try {
      const res = await fetch('/api/system');
      systemInfo = await res.json();
    } catch (e) {
      console.warn('Failed to load system info:', e);
    }
  }

  function openLanModal() {
    const port = window.location.port || '8000';
    const hostIp = systemInfo.local_ip || window.location.hostname;
    const fullUrl = `http://${hostIp}:${port}`;

    lanUrlText.textContent = fullUrl;

    const qrWrapper = document.getElementById('qrcode');
    qrWrapper.innerHTML = '';
    new QRCode(qrWrapper, {
      text: fullUrl,
      width: 180,
      height: 180,
      colorDark: "#0F172A",
      colorLight: "#ffffff",
      correctLevel: QRCode.CorrectLevel.H
    });

    lanModal.classList.remove('hidden');
  }

  // ─────────────────────────────────────────────────────────────
  // UTILITIES & HELPERS
  // ─────────────────────────────────────────────────────────────
  async function loadInitialJobs() {
    try {
      const res = await fetch('/api/jobs');
      const jobs = await res.json();
      jobs.forEach(j => activeJobs.set(j.id, j));
      renderActiveJobs();
    } catch (e) {
      console.error(e);
    }
  }

  function switchTab(tabName) {
    if (tabName === 'active') {
      tabBtnActive.classList.add('active');
      tabBtnHistory.classList.remove('active');
      tabActive.classList.add('active');
      tabHistory.classList.remove('active');
    } else {
      tabBtnHistory.classList.add('active');
      tabBtnActive.classList.remove('active');
      tabHistory.classList.add('active');
      tabActive.classList.remove('active');
      loadHistory();
    }
  }

  function showToast(message, type = 'info') {
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;

    let icon = 'fa-info-circle';
    if (type === 'success') icon = 'fa-circle-check';
    if (type === 'error') icon = 'fa-circle-exclamation';

    toast.innerHTML = `<i class="fa-solid ${icon}"></i> <span>${escapeHtml(message)}</span>`;
    toastContainer.appendChild(toast);

    setTimeout(() => {
      toast.style.opacity = '0';
      toast.style.transform = 'translateX(50px)';
      toast.style.transition = 'all 0.3s ease';
      setTimeout(() => toast.remove(), 300);
    }, 4000);
  }

  function debounce(func, wait) {
    let timeout;
    return function (...args) {
      clearTimeout(timeout);
      timeout = setTimeout(() => func.apply(this, args), wait);
    };
  }

  function escapeHtml(str) {
    if (!str) return '';
    return str
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }

  // Start app on DOM ready
  document.addEventListener('DOMContentLoaded', init);
})();
