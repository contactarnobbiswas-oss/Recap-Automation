const API_BASE_URL = "http://127.0.0.1:8000";

// Global State
const appState = {
  videoUrl: "",
  videoId: "",
  title: "",
  thumbnailUrl: "",
  rawTranscript: "",
  rewrittenTitle: "",
  rewrittenTranscript: "",
  processedThumbnailUrl: ""
};

document.addEventListener("DOMContentLoaded", () => {
  initServerCheck();
  initTabs();
  initApiKey();
  initVoices();
  initEventListeners();
});

// Check Python Backend status
async function initServerCheck() {
  const statusDot = document.querySelector("#serverStatus .status-dot");
  const statusText = document.querySelector("#serverStatus span:last-child");
  try {
    const res = await fetch(`${API_BASE_URL}/api/health`);
    if (res.ok) {
      statusDot.classList.add("online");
      statusText.textContent = "Backend Connected";
    } else {
      throw new Error();
    }
  } catch (err) {
    statusDot.classList.remove("online");
    statusText.textContent = "Backend Disconnected";
  }
}

// Tab Switching
function initTabs() {
  const tabBtns = document.querySelectorAll(".tab-btn");
  const tabContents = document.querySelectorAll(".tab-content");

  tabBtns.forEach(btn => {
    btn.addEventListener("click", () => {
      const targetTab = btn.dataset.tab;
      
      tabBtns.forEach(b => b.classList.remove("active"));
      tabContents.forEach(c => c.classList.remove("active"));

      btn.classList.add("active");
      document.getElementById(targetTab).classList.add("active");
    });
  });
}

// API Key Persistence
function initApiKey() {
  const keyInput = document.getElementById("geminiApiKey");
  const savedKey = localStorage.getItem("gemini_api_key") || "";
  keyInput.value = savedKey;
  updateKeyBadge(savedKey);

  keyInput.addEventListener("input", (e) => {
    const val = e.target.value.trim();
    localStorage.setItem("gemini_api_key", val);
    updateKeyBadge(val);
  });
}

function updateKeyBadge(key) {
  const badgeText = document.getElementById("apiKeyText");
  if (key) {
    badgeText.textContent = "Gemini API Key Set";
  } else {
    badgeText.textContent = "Gemini Key Missing";
  }
}

// Fetch Edge TTS voices
async function initVoices() {
  const voiceSelect = document.getElementById("voiceSelect");
  try {
    const res = await fetch(`${API_BASE_URL}/api/tts/voices`);
    const data = await res.json();
    if (data.success && data.voices && data.voices.length > 0) {
      voiceSelect.innerHTML = "";
      data.voices.forEach(v => {
        const opt = document.createElement("option");
        opt.value = v.short_name;
        opt.textContent = `${v.locale} - ${v.friendly_name} (${v.gender})`;
        if (v.short_name === "en-US-AvaMultilingualNeural") {
          opt.selected = true;
        }
        voiceSelect.appendChild(opt);
      });
    }
  } catch (err) {
    console.error("Failed to load voices from backend", err);
  }
}

// Event Listeners
function initEventListeners() {
  document.getElementById("btnExtract").addEventListener("click", handleExtract);
  
  document.getElementById("btnGoToRewrite").addEventListener("click", () => {
    switchTab("tab-rewriter");
  });

  document.getElementById("btnStartRewrite").addEventListener("click", handleRewrite);

  document.getElementById("btnGoToVoiceover").addEventListener("click", () => {
    const rewritten = document.getElementById("rewrittenTranscriptText").value;
    document.getElementById("voiceScriptText").value = rewritten || document.getElementById("rawTranscriptText").value;
    switchTab("tab-voiceover");
  });

  document.getElementById("btnGenerateVoice").addEventListener("click", handleGenerateVoice);

  // File Upload Handler (DownSub .txt / .srt / .vtt)
  const fileInput = document.getElementById("fileTranscriptInput");
  document.getElementById("btnUploadTranscriptFile").addEventListener("click", () => {
    fileInput.click();
  });

  fileInput.addEventListener("change", handleFileUpload);

  // Copy Buttons
  document.getElementById("btnCopyRawTranscript").addEventListener("click", () => {
    copyToClipboard(document.getElementById("rawTranscriptText").value, "Raw transcript copied!");
  });

  document.getElementById("btnCopySingleTitle").addEventListener("click", () => {
    copyToClipboard(appState.rewrittenTitle, "Title copied!");
  });

  document.getElementById("btnCopyRewrittenTranscript").addEventListener("click", () => {
    copyToClipboard(document.getElementById("rewrittenTranscriptText").value, "Rewritten transcript copied!");
  });
}

// Clean Subtitle text from SRT/VTT headers & timestamps
function cleanSubtitleText(rawContent) {
  const lines = rawContent.split(/\r?\n/);
  const cleanLines = [];

  for (let line of lines) {
    let str = line.trim();
    if (!str || str.startsWith("WEBVTT") || str.startsWith("Kind:") || str.startswith?.("Language:")) continue;
    if (str.includes("-->") || /^\d+$/.test(str)) continue;
    
    // Remove HTML tags <c>, </c>
    str = str.replace(/<[^>]+>/g, '').trim();
    if (str && (cleanLines.length === 0 || cleanLines[cleanLines.length - 1] !== str)) {
      cleanLines.push(str);
    }
  }

  return cleanLines.join(" ");
}

function handleFileUpload(e) {
  const file = e.target.files[0];
  if (!file) return;

  const reader = new FileReader();
  reader.onload = (evt) => {
    const content = evt.target.result;
    const cleanText = cleanSubtitleText(content);
    document.getElementById("rawTranscriptText").value = cleanText;
    appState.rawTranscript = cleanText;
    alert(`File '${file.name}' loaded and cleaned successfully!`);
  };
  reader.readAsText(file);
}

function switchTab(tabId) {
  document.querySelector(`.tab-btn[data-tab="${tabId}"]`).click();
}

function copyToClipboard(text, alertMsg) {
  if (!text) return;
  navigator.clipboard.writeText(text);
  alert(alertMsg);
}

function sanitizeFilename(title) {
  return title
    .replace(/[/\\?%*:|"<>]/g, '')
    .trim()
    .replace(/\s+/g, '_');
}

// Handler: Extract Content
async function handleExtract() {
  const urlInput = document.getElementById("ytUrlInput").value.trim();
  if (!urlInput) {
    alert("Please paste a valid YouTube URL!");
    return;
  }

  const loader = document.getElementById("extractorLoader");
  const results = document.getElementById("extractorResults");

  loader.classList.remove("hidden");
  results.classList.add("hidden");

  try {
    const res = await fetch(`${API_BASE_URL}/api/extract`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url: urlInput })
    });

    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Extraction failed");

    // Update State
    appState.videoUrl = urlInput;
    appState.videoId = data.video_id;
    appState.title = data.title;
    appState.thumbnailUrl = data.thumbnail_url;
    appState.rawTranscript = data.transcript;

    // Render UI
    document.getElementById("origThumbnailImg").src = data.thumbnail_url;
    document.getElementById("origTitleText").textContent = data.title;
    document.getElementById("origChannelText").textContent = data.channel;
    document.getElementById("origDurationText").textContent = `${Math.floor(data.duration / 60)}m ${data.duration % 60}s`;
    document.getElementById("btnDownloadVideo").href = `${API_BASE_URL}${data.video_url}`;
    
    const rawTextarea = document.getElementById("rawTranscriptText");
    rawTextarea.value = data.transcript;

    results.classList.remove("hidden");
  } catch (err) {
    alert(`Error: ${err.message}`);
  } finally {
    loader.classList.add("hidden");
  }
}

// Handler: AI Rewrite
async function handleRewrite() {
  const apiKey = document.getElementById("geminiApiKey").value.trim();
  const flipThumb = document.getElementById("chkFlipThumb").checked;
  const transcript = document.getElementById("rawTranscriptText").value.trim();

  if (!apiKey) {
    alert("Please enter your Google Gemini API Key first!");
    return;
  }

  const loader = document.getElementById("rewriteLoader");
  const results = document.getElementById("rewriteResults");

  loader.classList.remove("hidden");
  results.classList.add("hidden");

  try {
    const res = await fetch(`${API_BASE_URL}/api/rewrite`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        title: appState.title || "YouTube Video",
        transcript: transcript,
        thumbnail_url: appState.thumbnailUrl,
        gemini_api_key: apiKey,
        flip_thumbnail: flipThumb
      })
    });

    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Rewrite failed");

    appState.rewrittenTitle = data.rewritten_title;
    appState.rewrittenTranscript = data.rewritten_transcript;
    appState.processedThumbnailUrl = `${API_BASE_URL}${data.processed_thumbnail_url}`;

    // Render Single Title
    document.getElementById("rewrittenTitleDisplay").textContent = data.rewritten_title;

    // Update Thumbnail Download Button (Auto-named with Title)
    const downloadBtn = document.getElementById("btnDownloadThumb");
    const thumbImg = document.getElementById("processedThumbImg");
    thumbImg.src = appState.processedThumbnailUrl;
    downloadBtn.href = appState.processedThumbnailUrl;
    const cleanName = sanitizeFilename(data.rewritten_title || "Rewritten_Thumbnail");
    downloadBtn.download = `${cleanName}.jpg`;

    // Render Rewritten Transcript
    document.getElementById("rewrittenTranscriptText").value = data.rewritten_transcript;

    results.classList.remove("hidden");
  } catch (err) {
    alert(`Error: ${err.message}`);
  } finally {
    loader.classList.add("hidden");
  }
}

// Handler: Voiceover Generation
async function handleGenerateVoice() {
  const script = document.getElementById("voiceScriptText").value.trim();
  const voice = document.getElementById("voiceSelect").value;
  const rate = document.getElementById("voiceRate").value;
  const pitch = document.getElementById("voicePitch").value;

  if (!script) {
    alert("Please provide a script for voiceover generation!");
    return;
  }

  const loader = document.getElementById("voiceLoader");
  const playerCard = document.getElementById("voicePlayerCard");

  loader.classList.remove("hidden");
  playerCard.classList.add("hidden");

  try {
    const res = await fetch(`${API_BASE_URL}/api/tts/generate`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        text: script,
        voice: voice,
        rate: rate,
        pitch: pitch
      })
    });

    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Voiceover generation failed");

    const fullAudioUrl = `${API_BASE_URL}${data.audio_url}`;
    const audioPlayer = document.getElementById("audioPlayer");
    audioPlayer.src = fullAudioUrl;

    const cleanTitleName = sanitizeFilename(appState.rewrittenTitle || "Voiceover");
    const downloadAudioBtn = document.getElementById("btnDownloadAudio");
    downloadAudioBtn.href = fullAudioUrl;
    downloadAudioBtn.download = `${cleanTitleName}_Voiceover.mp3`;

    playerCard.classList.remove("hidden");
    audioPlayer.play();
  } catch (err) {
    alert(`Error: ${err.message}`);
  } finally {
    loader.classList.add("hidden");
  }
}
