const API_BASE_URL = window.location.origin;

// State Management
const appState = {
  token: localStorage.getItem("recap_session_token") || "",
  user: null,
  allVoices: [],
  selectedVoice: "en-US-AvaMultilingualNeural",
  videoUrl: "",
  videoId: "",
  title: "",
  thumbnailUrl: "",
  rawTranscript: "",
  rewrittenTitle: "",
  rewrittenTranscript: "",
  processedThumbnailUrl: "",
  audioUrl: ""
};

document.addEventListener("DOMContentLoaded", () => {
  initHealthCheck();
  checkAuthSession();
  initVoices();
  initEventListeners();
  initDragAndDropAndPasteCleaners();
});

function getAuthHeaders() {
  return {
    "Content-Type": "application/json",
    "Authorization": `Bearer ${appState.token}`
  };
}

// Timer & Progress Helpers
function startTimer(timerId) {
  let seconds = 0;
  const el = document.getElementById(timerId);
  if (!el) return null;
  el.textContent = "00:00";
  const interval = setInterval(() => {
    seconds++;
    const m = String(Math.floor(seconds / 60)).padStart(2, '0');
    const s = String(seconds % 60).padStart(2, '0');
    el.textContent = `${m}:${s}`;
  }, 1000);
  return interval;
}

function stopTimer(interval) {
  if (interval) clearInterval(interval);
}

function setProgress(percentId, barId, percent) {
  const pEl = document.getElementById(percentId);
  const bEl = document.getElementById(barId);
  const rounded = Math.min(100, Math.max(0, Math.round(percent)));
  if (pEl) pEl.textContent = `${rounded}%`;
  if (bEl) bEl.style.width = `${rounded}%`;
}

// Complete Noise & Line-Break Cleaner for Transcripts
function cleanToContinuousParagraph(text) {
  if (!text) return "";
  
  let clean = text
    .replace(/^WEBVTT.*/gi, '')
    .replace(/\d+\r?\n\d\d:\d\d:\d\d[,\.]\d{3}\s*-->\s*\d\d:\d\d:\d\d[,\.]\d{3}.*/g, '')
    .replace(/\d\d:\d\d:\d\d[,\.]\d{3}\s*-->\s*\d\d:\d\d:\d\d[,\.]\d{3}.*/g, '')
    .replace(/\d\d:\d\d\s*-->\s*\d\d:\d\d.*/g, '')
    .replace(/\[\s*(music|applause|laughter|chuckles|cheering|sound|audio|unclear|sighs|singing|gasp|screaming|background music)\s*\]/gi, '')
    .replace(/\(\s*(music|applause|laughter|chuckles|cheering|sound|audio|unclear|sighs|singing|gasp|screaming|background music)\s*\)/gi, '')
    .replace(/\[[^\]]*music[^\]]*\]/gi, '')
    .replace(/\([^\)]*music[^\)]*\)/gi, '')
    .replace(/<[^>]+>/g, '') // strip HTML tags
    .replace(/\r?\n|\r/g, ' ') // convert ALL newline breaks to single spaces!
    .replace(/\s+/g, ' ') // collapse multi-spaces to single space
    .trim();

  return clean;
}

async function initHealthCheck() {
  const statusText = document.getElementById("serverStatusText");
  try {
    const res = await fetch(`${API_BASE_URL}/api/health`);
    if (res.ok) statusText.textContent = "Engine Active";
  } catch (err) {
    statusText.textContent = "Backend Offline";
  }
}

async function checkAuthSession() {
  const loginModal = document.getElementById("loginModal");
  if (!appState.token) {
    loginModal.classList.remove("hidden");
    return;
  }

  try {
    const res = await fetch(`${API_BASE_URL}/api/me`, {
      headers: getAuthHeaders()
    });

    const data = await res.json();
    if (res.ok && data.success) {
      appState.user = data.user;
      loginModal.classList.add("hidden");
      renderUserProfile();
    } else {
      throw new Error(data.detail || "Session invalid");
    }
  } catch (err) {
    localStorage.removeItem("recap_session_token");
    appState.token = "";
    loginModal.classList.remove("hidden");
  }
}

function renderUserProfile() {
  const u = appState.user;
  if (!u) return;

  document.getElementById("userNameDisplay").textContent = u.username;
  document.getElementById("userRoleBadge").textContent = u.role.toUpperCase();

  const usedDisplay = document.getElementById("quotaUsedDisplay");
  const limitDisplay = document.getElementById("quotaLimitDisplay");

  if (u.role === "admin") {
    usedDisplay.textContent = u.used_today;
    limitDisplay.textContent = "∞";
    document.getElementById("btnOpenAdmin").classList.remove("hidden");
  } else {
    usedDisplay.textContent = u.used_today;
    limitDisplay.textContent = u.daily_limit;
    document.getElementById("btnOpenAdmin").classList.add("hidden");
  }

  const keyInput = document.getElementById("userApiKeyInput");
  if (u.masked_api_key) {
    keyInput.placeholder = `Saved: ${u.masked_api_key}`;
  } else {
    keyInput.placeholder = "Paste Gemini API Key...";
  }
}

// Voices Loading & Filterable Dropdown
async function initVoices() {
  try {
    const res = await fetch(`${API_BASE_URL}/api/tts/voices`);
    const data = await res.json();
    if (data.success && data.voices && data.voices.length > 0) {
      appState.allVoices = data.voices;
      renderVoicesDropdown(data.voices);
    }
  } catch (err) {
    console.error("Failed to load voices:", err);
  }
}

function renderVoicesDropdown(voices) {
  const voiceSelect = document.getElementById("voiceSelect");
  voiceSelect.innerHTML = "";
  if (!voices || voices.length === 0) {
    const opt = document.createElement("option");
    opt.textContent = "No matching voices found";
    voiceSelect.appendChild(opt);
    return;
  }

  voices.forEach((v, index) => {
    const opt = document.createElement("option");
    opt.value = v.short_name;
    opt.textContent = `${v.locale} - ${v.friendly_name} (${v.gender})`;
    if (v.short_name === appState.selectedVoice || (index === 0 && !appState.selectedVoice)) {
      opt.selected = true;
      appState.selectedVoice = v.short_name;
    }
    voiceSelect.appendChild(opt);
  });
}

function filterVoices(query) {
  const q = query.toLowerCase().trim();
  if (!q) {
    renderVoicesDropdown(appState.allVoices);
    return;
  }

  const filtered = appState.allVoices.filter(v => {
    return v.short_name.toLowerCase().includes(q) ||
           v.friendly_name.toLowerCase().includes(q) ||
           v.locale.toLowerCase().includes(q);
  });

  renderVoicesDropdown(filtered);
}

// Drag & Drop + Instant Paste Sanitizer
function initDragAndDropAndPasteCleaners() {
  const textarea = document.getElementById("rawTranscriptTextarea");

  // Real-time Paste Cleaner
  textarea.addEventListener("paste", (e) => {
    e.preventDefault();
    const pastedText = (e.clipboardData || window.clipboardData).getData("text");
    const cleanText = cleanToContinuousParagraph(pastedText);

    const start = textarea.selectionStart;
    const end = textarea.selectionEnd;
    const currentVal = textarea.value;

    textarea.value = currentVal.substring(0, start) + cleanText + currentVal.substring(end);
    textarea.selectionStart = textarea.selectionEnd = start + cleanText.length;
    appState.rawTranscript = textarea.value;
  });

  // Drag & Drop
  const dropZones = [textarea, textarea.closest(".step-card")];
  dropZones.forEach(zone => {
    if (!zone) return;

    zone.addEventListener("dragover", (e) => {
      e.preventDefault();
      textarea.classList.add("drag-active");
    });

    zone.addEventListener("dragleave", (e) => {
      e.preventDefault();
      textarea.classList.remove("drag-active");
    });

    zone.addEventListener("drop", (e) => {
      e.preventDefault();
      textarea.classList.remove("drag-active");

      const files = e.dataTransfer.files;
      if (files && files.length > 0) {
        processUploadedFile(files[0]);
      }
    });
  });
}

function processUploadedFile(file) {
  const reader = new FileReader();
  reader.onload = (evt) => {
    const rawContent = evt.target.result;
    const cleanText = cleanToContinuousParagraph(rawContent);
    document.getElementById("rawTranscriptTextarea").value = cleanText;
    appState.rawTranscript = cleanText;
    alert(`File '${file.name}' imported and formatted into a continuous paragraph successfully!`);
  };
  reader.readAsText(file);
}

// Event Listeners
function initEventListeners() {
  document.getElementById("loginForm").addEventListener("submit", handleLogin);

  document.getElementById("btnLogout").addEventListener("click", () => {
    localStorage.removeItem("recap_session_token");
    location.reload();
  });

  document.getElementById("btnSaveUserKey").addEventListener("click", handleSavePersonalKey);

  document.getElementById("btnOpenAdmin").addEventListener("click", openAdminModal);
  document.getElementById("btnCloseAdminModal").addEventListener("click", () => {
    document.getElementById("adminModal").classList.add("hidden");
  });

  document.querySelectorAll(".admin-tab-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".admin-tab-btn").forEach(b => b.classList.remove("active"));
      document.querySelectorAll(".atab-content").forEach(c => c.classList.remove("active"));
      btn.classList.add("active");
      document.getElementById(btn.dataset.atab).classList.add("active");
    });
  });

  document.getElementById("btnCreateEditor").addEventListener("click", handleCreateEditor);

  // Search Box Filter Event for Dropdown
  document.getElementById("voiceSearchInput").addEventListener("input", (e) => {
    filterVoices(e.target.value);
  });

  // Dropdown Select Change Handler
  document.getElementById("voiceSelect").addEventListener("change", (e) => {
    appState.selectedVoice = e.target.value;
  });

  // Step 1: Extract
  document.getElementById("btnStep1Extract").addEventListener("click", handleStep1Extract);

  // Step 2: Title & Thumbnail Regenerate
  document.getElementById("btnStep2Regenerate").addEventListener("click", handleStep2Regenerate);

  // Step 3: Subtitle Upload & AI Script Rewrite
  const fileInput = document.getElementById("fileTranscriptInput");
  document.getElementById("btnUploadFile").addEventListener("click", () => fileInput.click());
  fileInput.addEventListener("change", handleFileUpload);

  document.getElementById("btnStep3RewriteScript").addEventListener("click", handleStep3RewriteScript);

  // Step 4: Voiceover Generation
  document.getElementById("btnStep4GenerateVoice").addEventListener("click", handleStep4GenerateVoice);

  // Copy Buttons
  document.getElementById("btnCopyTitle").addEventListener("click", () => {
    copyText(appState.rewrittenTitle, "Title copied!");
  });
  document.getElementById("btnCopyRewrittenScript").addEventListener("click", () => {
    copyText(document.getElementById("rewrittenScriptTextarea").value, "Script copied!");
  });
}

// Handlers
async function handleLogin(e) {
  e.preventDefault();
  const username = document.getElementById("loginUsername").value.trim();
  const password = document.getElementById("loginPassword").value.trim();

  try {
    const res = await fetch(`${API_BASE_URL}/api/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, password })
    });

    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Login failed");

    appState.token = data.token;
    appState.user = data.user;
    localStorage.setItem("recap_session_token", data.token);

    document.getElementById("loginModal").classList.add("hidden");
    renderUserProfile();
    alert(`Welcome back, ${data.user.username}!`);
  } catch (err) {
    alert(`Login Error: ${err.message}`);
  }
}

async function handleSavePersonalKey() {
  const key = document.getElementById("userApiKeyInput").value.trim();
  if (!key) return alert("Please enter your Gemini API Key first!");

  try {
    const res = await fetch(`${API_BASE_URL}/api/user/key`, {
      method: "POST",
      headers: getAuthHeaders(),
      body: JSON.stringify({ gemini_api_key: key })
    });

    const data = await res.json();
    if (!res.ok) throw new Error(data.detail);

    alert("Personal Gemini API Key saved securely to your user account!");
    checkAuthSession();
  } catch (err) {
    alert(`Save Key Error: ${err.message}`);
  }
}

async function openAdminModal() {
  document.getElementById("adminModal").classList.remove("hidden");
  loadAdminUsers();
  loadAdminLogs();
}

async function loadAdminUsers() {
  try {
    const res = await fetch(`${API_BASE_URL}/api/admin/users`, { headers: getAuthHeaders() });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail);

    const tbody = document.getElementById("usersTableBody");
    tbody.innerHTML = "";

    data.users.forEach(u => {
      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td>${u.id}</td>
        <td><strong>${u.username}</strong></td>
        <td><span class="role-badge">${u.role}</span></td>
        <td>${u.has_api_key ? `<span style="color:#10b981;">Saved (${u.masked_api_key})</span>` : '<span style="color:#ef4444;">Missing</span>'}</td>
        <td><strong>${u.used_today}</strong></td>
        <td>${u.role === 'admin' ? 'Unlimited' : u.daily_limit}</td>
        <td>
          ${u.role !== 'admin' ? `<button class="btn btn-secondary small-btn" onclick="editUserLimit(${u.id}, ${u.daily_limit})">Edit Limit</button>` : '-'}
        </td>
      `;
      tbody.appendChild(tr);
    });
  } catch (err) {
    alert(`Failed to load admin users: ${err.message}`);
  }
}

async function loadAdminLogs() {
  try {
    const res = await fetch(`${API_BASE_URL}/api/admin/logs`, { headers: getAuthHeaders() });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail);

    const tbody = document.getElementById("logsTableBody");
    tbody.innerHTML = "";

    data.logs.forEach(l => {
      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td>${new Date(l.created_at).toLocaleTimeString()}</td>
        <td><strong>${l.username}</strong></td>
        <td><code>${l.action}</code></td>
        <td>${l.video_title || '-'}</td>
      `;
      tbody.appendChild(tr);
    });
  } catch (err) {
    console.error("Failed to load logs:", err);
  }
}

async function handleCreateEditor() {
  const username = document.getElementById("newEditorUser").value.trim();
  const password = document.getElementById("newEditorPass").value.trim();
  const daily_limit = parseInt(document.getElementById("newEditorLimit").value) || 5;

  if (!username || !password) return alert("Username and Password are required!");

  try {
    const res = await fetch(`${API_BASE_URL}/api/admin/users`, {
      method: "POST",
      headers: getAuthHeaders(),
      body: JSON.stringify({ username, password, daily_limit })
    });

    const data = await res.json();
    if (!res.ok) throw new Error(data.detail);

    alert(`Editor '${username}' created successfully with daily limit of ${daily_limit}!`);
    document.getElementById("newEditorUser").value = "";
    document.getElementById("newEditorPass").value = "";
    loadAdminUsers();
  } catch (err) {
    alert(`Create Editor Error: ${err.message}`);
  }
}

window.editUserLimit = async function(userId, currentLimit) {
  const newLimitStr = prompt("Enter new daily limit for this editor:", currentLimit);
  if (!newLimitStr) return;
  const newLimit = parseInt(newLimitStr);
  if (isNaN(newLimit) || newLimit < 1) return alert("Invalid limit!");

  try {
    const res = await fetch(`${API_BASE_URL}/api/admin/users/limit`, {
      method: "POST",
      headers: getAuthHeaders(),
      body: JSON.stringify({ user_id: userId, daily_limit: newLimit })
    });

    const data = await res.json();
    if (!res.ok) throw new Error(data.detail);

    alert("Limit updated successfully!");
    loadAdminUsers();
  } catch (err) {
    alert(`Update Limit Error: ${err.message}`);
  }
};

function copyText(text, msg) {
  if (!text) return;
  navigator.clipboard.writeText(text);
  alert(msg);
}

function sanitizeFilename(text) {
  return text
    .replace(/[/\\?%*:|"<>]/g, '')
    .trim()
    .replace(/\s+/g, '_');
}

// STEP 1: Extract Media & Metadata with Live Timer
async function handleStep1Extract() {
  const url = document.getElementById("ytUrlInput").value.trim();
  if (!url) return alert("Please paste a valid YouTube video link!");

  const btn = document.getElementById("btnStep1Extract");
  const loader = document.getElementById("step1Loader");
  const results = document.getElementById("step1Results");

  btn.disabled = true;
  loader.classList.remove("hidden");
  results.classList.add("hidden");
  
  const timer = startTimer("step1Timer");

  try {
    const res = await fetch(`${API_BASE_URL}/api/extract`, {
      method: "POST",
      headers: getAuthHeaders(),
      body: JSON.stringify({ url })
    });

    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Extraction failed");

    appState.videoUrl = url;
    appState.videoId = data.video_id;
    appState.title = data.title;
    appState.thumbnailUrl = data.thumbnail_url;
    
    // Clean extracted transcript into continuous paragraph string
    const cleanText = cleanToContinuousParagraph(data.transcript);
    appState.rawTranscript = cleanText;

    document.getElementById("origTitleDisplay").textContent = data.title;
    document.getElementById("origChannelDisplay").textContent = data.channel;
    document.getElementById("origDurationDisplay").textContent = `${Math.floor(data.duration / 60)}m ${data.duration % 60}s`;
    
    document.getElementById("btnDownloadOrigVideo").href = `${API_BASE_URL}${data.video_url}`;
    document.getElementById("btnDownloadOrigThumb").href = data.thumbnail_url;
    document.getElementById("origThumbImg").src = data.thumbnail_url;

    document.getElementById("rawTranscriptTextarea").value = cleanText;

    results.classList.remove("hidden");
  } catch (err) {
    alert(`Step 1 Error: ${err.message}`);
  } finally {
    stopTimer(timer);
    btn.disabled = false;
    loader.classList.add("hidden");
  }
}

// STEP 2: Title & Thumbnail Regeneration with Live Timer
async function handleStep2Regenerate() {
  const flipThumb = document.getElementById("chkFlipThumb").checked;
  const title = appState.title || document.getElementById("origTitleDisplay").textContent;

  const btn = document.getElementById("btnStep2Regenerate");
  const loader = document.getElementById("step2Loader");
  const results = document.getElementById("step2Results");

  btn.disabled = true;
  loader.classList.remove("hidden");
  results.classList.add("hidden");

  const timer = startTimer("step2Timer");

  try {
    const res = await fetch(`${API_BASE_URL}/api/rewrite`, {
      method: "POST",
      headers: getAuthHeaders(),
      body: JSON.stringify({
        title: title,
        transcript: "",
        thumbnail_url: appState.thumbnailUrl,
        flip_thumbnail: flipThumb
      })
    });

    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Regeneration failed");

    appState.rewrittenTitle = data.rewritten_title;
    appState.processedThumbnailUrl = `${API_BASE_URL}${data.processed_thumbnail_url}`;

    if (data.used_today !== undefined) {
      appState.user.used_today = data.used_today;
      renderUserProfile();
    }

    document.getElementById("rewrittenTitleDisplay").textContent = data.rewritten_title;

    const thumbImg = document.getElementById("processedThumbImg");
    const thumbBtn = document.getElementById("btnDownloadProcessedThumb");
    thumbImg.src = appState.processedThumbnailUrl;
    thumbBtn.href = appState.processedThumbnailUrl;
    const cleanTitle = sanitizeFilename(data.rewritten_title || "Thumbnail");
    thumbBtn.download = `${cleanTitle}.jpg`;

    results.classList.remove("hidden");
  } catch (err) {
    alert(`Step 2 Error: ${err.message}`);
  } finally {
    stopTimer(timer);
    btn.disabled = false;
    loader.classList.add("hidden");
  }
}

// STEP 3: Subtitle Upload & AI Script Rewrite with Live Percentage & Timer
async function handleStep3RewriteScript() {
  const transcript = document.getElementById("rawTranscriptTextarea").value.trim();

  if (!transcript) return alert("Please provide a transcript/subtitle text first (extract, drop, or upload TXT/SRT file)!");

  const btn = document.getElementById("btnStep3RewriteScript");
  const loader = document.getElementById("step3Loader");

  btn.disabled = true;
  loader.classList.remove("hidden");

  const timer = startTimer("step3Timer");

  // Simulated live percentage progress smooth animation
  let p = 5;
  setProgress("step3ProgressPercent", "step3ProgressBar", p);
  const pInterval = setInterval(() => {
    if (p < 90) {
      p += Math.floor(Math.random() * 8) + 3;
      setProgress("step3ProgressPercent", "step3ProgressBar", p);
    }
  }, 1200);

  try {
    const res = await fetch(`${API_BASE_URL}/api/rewrite`, {
      method: "POST",
      headers: getAuthHeaders(),
      body: JSON.stringify({
        title: appState.title || "YouTube Video",
        transcript: transcript,
        thumbnail_url: appState.thumbnailUrl || "https://img.youtube.com/vi/dQw4w9WgXcQ/maxresdefault.jpg",
        flip_thumbnail: false
      })
    });

    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Script rewriting failed");

    clearInterval(pInterval);
    setProgress("step3ProgressPercent", "step3ProgressBar", 100);

    appState.rewrittenTranscript = data.rewritten_transcript;
    document.getElementById("rewrittenScriptTextarea").value = data.rewritten_transcript;

    if (data.used_today !== undefined) {
      appState.user.used_today = data.used_today;
      renderUserProfile();
    }
  } catch (err) {
    alert(`Step 3 Error: ${err.message}`);
  } finally {
    clearInterval(pInterval);
    stopTimer(timer);
    setTimeout(() => {
      btn.disabled = false;
      loader.classList.add("hidden");
      setProgress("step3ProgressPercent", "step3ProgressBar", 0);
    }, 500);
  }
}

function handleFileUpload(e) {
  const file = e.target.files[0];
  if (!file) return;
  processUploadedFile(file);
}

// STEP 4: Edge Neural Voiceover Generation with Live Percentage & Timer
async function handleStep4GenerateVoice() {
  const script = document.getElementById("rewrittenScriptTextarea").value.trim() || document.getElementById("rawTranscriptTextarea").value.trim();
  const voiceSelect = document.getElementById("voiceSelect");
  const voice = voiceSelect.value || appState.selectedVoice;

  if (!voice || voice === "No matching voices found") {
    return alert("Please select a valid voice character from the list!");
  }

  if (!script) return alert("Please provide a script for voiceover generation!");

  const loader = document.getElementById("step4Loader");
  const results = document.getElementById("step4Results");

  loader.classList.remove("hidden");
  results.classList.add("hidden");

  const timer = startTimer("step4Timer");

  // Simulated live percentage progress smooth animation
  let p = 8;
  setProgress("step4ProgressPercent", "step4ProgressBar", p);
  const pInterval = setInterval(() => {
    if (p < 92) {
      p += Math.floor(Math.random() * 10) + 4;
      setProgress("step4ProgressPercent", "step4ProgressBar", p);
    }
  }, 1000);

  try {
    const res = await fetch(`${API_BASE_URL}/api/tts/generate`, {
      method: "POST",
      headers: getAuthHeaders(),
      body: JSON.stringify({
        text: script,
        voice: voice,
        rate: "+0%"
      })
    });

    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Voiceover generation failed");

    clearInterval(pInterval);
    setProgress("step4ProgressPercent", "step4ProgressBar", 100);

    appState.audioUrl = `${API_BASE_URL}${data.audio_url}`;

    const player = document.getElementById("audioPlayer");
    const audioBtn = document.getElementById("btnDownloadAudio");
    
    player.src = appState.audioUrl;
    audioBtn.href = appState.audioUrl;
    const cleanTitle = sanitizeFilename(appState.rewrittenTitle || "Voiceover");
    audioBtn.download = `${cleanTitle}_Voiceover.mp3`;

    results.classList.remove("hidden");
    player.play();
  } catch (err) {
    alert(`Step 4 Error: ${err.message}`);
  } finally {
    clearInterval(pInterval);
    stopTimer(timer);
    setTimeout(() => {
      loader.classList.add("hidden");
      setProgress("step4ProgressPercent", "step4ProgressBar", 0);
    }, 500);
  }
}
