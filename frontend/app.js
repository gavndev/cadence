const TOKEN_KEY = "cadence_token";

const splash = document.getElementById("splash");
const dashboard = document.getElementById("dashboard");
const loginForm = document.getElementById("login-form");
const loginError = document.getElementById("login-error");
const loginButton = document.getElementById("login-button");
const logoutButton = document.getElementById("logout-button");
const setupScreen = document.getElementById("setup");
const setupError = document.getElementById("setup-error");
const setupSuccess = document.getElementById("setup-success");
const setupCloseButton = document.getElementById("setup-close");
const customLibraryForm = document.getElementById("custom-library-form");
const builtinLibraryButton = document.getElementById("builtin-library");
const fileList = document.getElementById("file-list");
const fileSearch = document.getElementById("file-search");
const inspector = document.getElementById("inspector");
const inspectorEmpty = document.getElementById("inspector-empty");
const coverArt = document.getElementById("cover-art");
const coverFallback = document.getElementById("cover-fallback");
const coverInput = document.getElementById("cover-input");
const saveStatus = document.getElementById("save-status");

let token = localStorage.getItem(TOKEN_KEY) || "";
let files = [];
let selectedId = null;
let artworkUrl = "";

async function api(path, options = {}) {
  const headers = { ...(options.headers || {}) };
  if (token) headers.Authorization = `Bearer ${token}`;
  if (options.body && !(options.body instanceof FormData) && !headers["Content-Type"]) {
    headers["Content-Type"] = "application/json";
  }
  const response = await fetch(path, { ...options, headers });
  if (response.status === 401) {
    signOut(false);
    throw new Error("Not authenticated");
  }
  if (!response.ok) {
    let detail = `Request failed (${response.status})`;
    try {
      const payload = await response.json();
      detail = payload.detail || detail;
    } catch {
      /* ignore */
    }
    throw new Error(detail);
  }
  if (response.status === 204) return null;
  const contentType = response.headers.get("content-type") || "";
  if (contentType.includes("application/json")) return response.json();
  return response;
}

function showDashboard() {
  splash.classList.add("is-leaving");
  dashboard.classList.add("is-visible");
  dashboard.classList.remove("invisible");
  setTimeout(() => splash.classList.add("hidden"), 700);
}

function showSplash() {
  splash.classList.remove("hidden", "is-leaving");
  dashboard.classList.remove("is-visible");
  dashboard.classList.add("invisible");
}

function signOut(clearUi = true) {
  token = "";
  localStorage.removeItem(TOKEN_KEY);
  files = [];
  selectedId = null;
  if (clearUi) {
    setupScreen.classList.add("hidden");
    setupScreen.classList.remove("flex");
    showSplash();
    fileList.innerHTML = "";
    inspector.classList.add("hidden");
    inspectorEmpty.classList.remove("hidden");
  }
}

function showSetup(info) {
  document.getElementById("library-path").value = (info && info.music_path) || "";
  setupError.classList.add("hidden");
  setupSuccess.classList.add("max-h-0");
  setupSuccess.classList.remove("max-h-20");
  setupScreen.classList.remove("hidden");
  setupScreen.classList.add("flex");
}

function hideSetup() {
  setupScreen.classList.add("hidden");
  setupScreen.classList.remove("flex");
  setupSuccess.classList.add("max-h-0");
  setupSuccess.classList.remove("max-h-20");
}

function showSetupSuccess() {
  setupError.classList.add("hidden");
  setupSuccess.classList.remove("max-h-0");
  setupSuccess.classList.add("max-h-20");
}

async function openStudio() {
  hideSetup();
  showDashboard();
  selectedId = null;
  inspector.classList.add("hidden");
  inspectorEmpty.classList.remove("hidden");
  await loadLibrary();
}

async function enterApp() {
  const info = await api("/api/setup");
  if (!info.configured) {
    showSetup(info);
    return;
  }
  hideSetup();
  showDashboard();
  await loadLibrary();
}

function formatBytes(bytes) {
  if (!bytes) return "0 B";
  const units = ["B", "KB", "MB", "GB"];
  const index = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), units.length - 1);
  return `${(bytes / 1024 ** index).toFixed(index ? 1 : 0)} ${units[index]}`;
}

function formatDuration(seconds) {
  if (!seconds && seconds !== 0) return "";
  const total = Math.round(seconds);
  const minutes = Math.floor(total / 60);
  const remainder = String(total % 60).padStart(2, "0");
  return `${minutes}:${remainder}`;
}

function renderFiles(query = "") {
  const needle = query.trim().toLowerCase();
  const filtered = files.filter((file) => {
    const haystack = `${file.name} ${file.relative_path} ${file.folder}`.toLowerCase();
    return haystack.includes(needle);
  });

  if (!filtered.length) {
    fileList.innerHTML = `
      <div class="px-3 py-10 text-center text-sm text-zinc-500">
        ${files.length ? "No matching tracks." : "No audio files yet. Add MP3, FLAC, WAV, M4A, or OGG files to the library folder."}
      </div>`;
    return;
  }

  fileList.innerHTML = filtered
    .map(
      (file) => `
      <button type="button" data-id="${file.id}" class="file-row ${file.id === selectedId ? "active" : ""}">
        <span class="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-zinc-900 text-[10px] font-semibold uppercase tracking-wider text-zinc-400">
          ${file.extension}
        </span>
        <span class="min-w-0 flex-1">
          <span class="block truncate text-sm text-zinc-100">${escapeHtml(file.name)}</span>
          <span class="block truncate text-xs text-zinc-500">${escapeHtml(file.folder || "Library")} · ${formatBytes(file.size)}</span>
        </span>
      </button>`
    )
    .join("");
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

async function loadLibrary() {
  const data = await api("/api/library");
  files = data.files;
  document.getElementById("library-root").textContent = data.root;
  document.getElementById("library-count").textContent = `${data.count} track${data.count === 1 ? "" : "s"}`;
  renderFiles(fileSearch.value);
}

async function fillInspector(detail) {
  inspector.classList.remove("hidden");
  inspectorEmpty.classList.add("hidden");
  document.getElementById("file-heading").textContent = detail.tags.title || detail.name;
  document.getElementById("file-path").textContent = detail.relative_path;
  document.getElementById("file-format").textContent = detail.extension;
  const tech = [
    formatDuration(detail.duration),
    detail.sample_rate ? `${Math.round(detail.sample_rate / 1000)} kHz` : "",
    detail.bitrate ? `${Math.round(detail.bitrate / 1000)} kbps` : "",
    detail.channels ? `${detail.channels} ch` : "",
    formatBytes(detail.size),
  ].filter(Boolean);
  document.getElementById("file-tech").textContent = tech.join(" · ");

  for (const field of inspector.elements) {
    if (field.name && field.name in (detail.tags || {})) {
      field.value = detail.tags[field.name] || "";
    }
  }

  if (artworkUrl) {
    URL.revokeObjectURL(artworkUrl);
    artworkUrl = "";
  }

  if (detail.has_artwork) {
    try {
      const response = await api(`/api/files/${detail.id}/artwork`);
      const blob = await response.blob();
      artworkUrl = URL.createObjectURL(blob);
      coverArt.src = artworkUrl;
      coverArt.classList.remove("hidden");
      coverFallback.classList.add("hidden");
    } catch {
      coverArt.removeAttribute("src");
      coverArt.classList.add("hidden");
      coverFallback.classList.remove("hidden");
    }
  } else {
    coverArt.removeAttribute("src");
    coverArt.classList.add("hidden");
    coverFallback.classList.remove("hidden");
  }
}

async function selectFile(fileId) {
  selectedId = fileId;
  renderFiles(fileSearch.value);
  saveStatus.textContent = "";
  const detail = await api(`/api/files/${fileId}`);
  await fillInspector(detail);
}

loginForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  loginError.classList.add("hidden");
  loginButton.disabled = true;
  loginButton.textContent = "Signing in…";
  try {
    const payload = await api("/api/login", {
      method: "POST",
      body: JSON.stringify({
        username: document.getElementById("username").value,
        password: document.getElementById("password").value,
      }),
    });
    token = payload.token;
    localStorage.setItem(TOKEN_KEY, token);
    await enterApp();
  } catch (error) {
    loginError.textContent = error.message;
    loginError.classList.remove("hidden");
  } finally {
    loginButton.disabled = false;
    loginButton.textContent = "Log In";
  }
});

async function chooseLibrary(mode, path) {
  setupError.classList.add("hidden");
  try {
    await api("/api/setup", {
      method: "POST",
      body: JSON.stringify({ mode, path: path || "" }),
    });
    showSetupSuccess();
  } catch (error) {
    setupSuccess.classList.add("max-h-0");
    setupSuccess.classList.remove("max-h-20");
    setupError.textContent = error.message;
    setupError.classList.remove("hidden");
  }
}

customLibraryForm.addEventListener("submit", (event) => {
  event.preventDefault();
  chooseLibrary("custom", document.getElementById("library-path").value);
});

builtinLibraryButton.addEventListener("click", () => chooseLibrary("builtin"));

setupCloseButton.addEventListener("click", () => {
  openStudio();
});

logoutButton.addEventListener("click", () => signOut());
fileSearch.addEventListener("input", () => renderFiles(fileSearch.value));

fileList.addEventListener("click", (event) => {
  const button = event.target.closest("[data-id]");
  if (button) selectFile(button.dataset.id);
});

inspector.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (!selectedId) return;
  const form = new FormData(inspector);
  const tags = Object.fromEntries(form.entries());
  delete tags[""];
  saveStatus.textContent = "Saving…";
  try {
    const detail = await api(`/api/files/${selectedId}`, {
      method: "PUT",
      body: JSON.stringify(tags),
    });
    await fillInspector(detail);
    saveStatus.textContent = "Saved";
  } catch (error) {
    saveStatus.textContent = error.message;
  }
});

coverInput.addEventListener("change", async () => {
  if (!selectedId || !coverInput.files[0]) return;
  const body = new FormData();
  body.append("file", coverInput.files[0]);
  saveStatus.textContent = "Uploading artwork…";
  try {
    await api(`/api/files/${selectedId}/artwork`, { method: "POST", body });
    await selectFile(selectedId);
    saveStatus.textContent = "Artwork updated";
  } catch (error) {
    saveStatus.textContent = error.message;
  } finally {
    coverInput.value = "";
  }
});

async function boot() {
  if (!token) return;
  try {
    await api("/api/me");
    await enterApp();
  } catch {
    signOut(false);
  }
}

boot();
