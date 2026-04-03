const sectionView = document.getElementById("section-view");
const listView = document.getElementById("list-view");
const listTitle = document.getElementById("list-title");
const listSubtitle = document.getElementById("list-subtitle");
const listContent = document.getElementById("list-content");
const listTools = document.getElementById("list-tools");
const backButton = document.getElementById("backButton");
const playerCard = document.getElementById("player-card");
const playerTitle = document.getElementById("player-title");
const playerMeta = document.getElementById("player-meta");
const audioPlayer = document.getElementById("audio-player");
const prevButton = document.getElementById("prevButton");
const nextButton = document.getElementById("nextButton");

const sections = {
  top: {
    title: "Top yuklanganlar",
    subtitle: "Eng mashhur va tez-tez tinglangan qo'shiqlar.",
    endpoint: "/api/top?limit=500",
    type: "songs",
  },
  artists: {
    title: "Artistlar",
    subtitle: "Eng ko'p yuklangan ijrochilar.",
    endpoint: "/api/artists",
    type: "artists",
  },
  instagram: {
    title: "Instagram",
    subtitle: "Instagram orqali yuklangan kontent.",
    endpoint: "/api/platform/instagram?limit=500",
    type: "songs",
  },
  youtube: {
    title: "YouTube",
    subtitle: "YouTube orqali yuklangan audio va videolar.",
    endpoint: "/api/platform/youtube?limit=500",
    type: "songs",
  },
  tiktok: {
    title: "TikTok",
    subtitle: "TikTokdan olingan eng yangi musiqalar.",
    endpoint: "/api/platform/tiktok?limit=500",
    type: "songs",
  },
  all: {
    title: "Barchasi",
    subtitle: "Bot orqali yuklangan barcha qo'shiqlar.",
    endpoint: "/api/all?limit=2000",
    type: "all",
  },
};

const PIN_STORAGE_KEY = "toparchik_pins";
let currentList = [];
let currentIndex = -1;
let currentSection = null;
let currentSort = "downloads";

function loadPins() {
  try {
    const raw = localStorage.getItem(PIN_STORAGE_KEY);
    return new Set(raw ? JSON.parse(raw) : []);
  } catch {
    return new Set();
  }
}

function savePins(pins) {
  localStorage.setItem(PIN_STORAGE_KEY, JSON.stringify([...pins]));
}

function showSectionView() {
  listView.classList.add("hidden");
  sectionView.classList.remove("hidden");
  playerCard.classList.add("hidden");
}

function showListView() {
  sectionView.classList.add("hidden");
  listView.classList.remove("hidden");
}

function setLoading() {
  listContent.innerHTML = '<div class="empty-state">Yuklanmoqda...</div>';
}

function setEmpty(message) {
  listContent.innerHTML = `<div class="empty-state">${message}</div>`;
}

function formatDuration(seconds) {
  const total = Number(seconds || 0);
  if (!total) return "";
  const mins = Math.floor(total / 60);
  const secs = Math.floor(total % 60);
  return `${mins}:${secs.toString().padStart(2, "0")}`;
}

async function fetchJSON(url, options = {}) {
  const response = await fetch(url, options);
  if (!response.ok) {
    throw new Error("Request failed");
  }
  return response.json();
}

function ensurePlaylist(list, songId) {
  currentList = Array.isArray(list) ? list : [];
  currentIndex = currentList.findIndex((song) => song.id === songId);
}

function updatePlayer(song) {
  if (!song) return;
  playerTitle.textContent = song.title || "Ijro";
  const parts = [];
  if (song.artist) parts.push(song.artist);
  if (song.download_count !== undefined) {
    parts.push(`Yuklash: ${song.download_count}`);
  }
  if (song.play_count !== undefined) {
    parts.push(`Eshitish: ${song.play_count}`);
  }
  playerMeta.textContent = parts.join(" • ");
  playerCard.classList.remove("hidden");
}

async function playSong(song) {
  if (!song || !song.file_id) return;
  ensurePlaylist(currentList, song.id);
  const src = `/api/audio/${encodeURIComponent(song.file_id)}?t=${Date.now()}`;
  audioPlayer.src = src;
  updatePlayer(song);
  audioPlayer.play().catch(() => {});

  if (song.id) {
    try {
      await fetchJSON(`/api/play/${encodeURIComponent(song.id)}`, { method: "POST" });
      song.play_count = (song.play_count || 0) + 1;
      if (currentSection === "all" && song.play_count >= 2) {
        renderSongs(currentList, { showPins: true, sortMode: currentSort });
      }
    } catch {
      // ignore
    }
  }
}

function playSongByIndex(index) {
  if (index < 0 || index >= currentList.length) return;
  currentIndex = index;
  playSong(currentList[index]);
}

function handlePrev() {
  if (currentIndex <= 0) return;
  playSongByIndex(currentIndex - 1);
}

function handleNext() {
  if (currentIndex < 0) return;
  if (currentIndex >= currentList.length - 1) return;
  playSongByIndex(currentIndex + 1);
}

function renderSongs(items, options = {}) {
  const { showPins = false, sortMode = "downloads" } = options;
  currentSort = sortMode;
  if (!items || items.length === 0) {
    setEmpty("Hozircha qo'shiqlar topilmadi.");
    return;
  }

  const pins = loadPins();
  let list = [...items];

  if (showPins) {
    list.sort((a, b) => {
      const aPinned = pins.has(a.id);
      const bPinned = pins.has(b.id);
      if (aPinned !== bPinned) return aPinned ? -1 : 1;
      const aBoost = (a.play_count || 0) >= 2;
      const bBoost = (b.play_count || 0) >= 2;
      if (aBoost !== bBoost) return aBoost ? -1 : 1;
      if (sortMode === "plays") {
        const diff = (b.play_count || 0) - (a.play_count || 0);
        if (diff !== 0) return diff;
      } else if (sortMode === "title") {
        return (a.title || "").localeCompare(b.title || "");
      }
      const diff = (b.download_count || 0) - (a.download_count || 0);
      if (diff !== 0) return diff;
      return (a.title || "").localeCompare(b.title || "");
    });
  }

  currentList = list;
  listContent.innerHTML = "";

  list.forEach((song, index) => {
    const card = document.createElement("div");
    card.className = "song-card";

    const info = document.createElement("div");
    const title = document.createElement("p");
    title.className = "song-title";
    title.textContent = `${index + 1}. ${song.title || "Unknown"}`;

    const meta = document.createElement("p");
    meta.className = "song-meta";
    const duration = formatDuration(song.duration);
    const artist = song.artist ? ` • ${song.artist}` : "";
    const downloads = ` • Yuklash: ${song.download_count || 0}`;
    meta.textContent = `${duration || "0:00"}${artist}${downloads}`;

    info.appendChild(title);
    info.appendChild(meta);

    const actions = document.createElement("div");
    actions.className = "song-actions";

    if (showPins) {
      const pinButton = document.createElement("button");
      pinButton.className = "pin-button";
      pinButton.textContent = pins.has(song.id) ? "Pin" : "Pin";
      if (pins.has(song.id)) {
        pinButton.classList.add("active");
      }
      pinButton.addEventListener("click", () => {
        if (pins.has(song.id)) {
          pins.delete(song.id);
        } else {
          pins.add(song.id);
        }
        savePins(pins);
        renderSongs(list, { showPins: true, sortMode });
      });
      actions.appendChild(pinButton);
    }

    const button = document.createElement("button");
    button.className = "play-button";
    button.textContent = song.playable ? "Play" : "N/A";
    button.disabled = !song.playable;
    button.addEventListener("click", () => playSong(song));
    actions.appendChild(button);

    card.appendChild(info);
    card.appendChild(actions);
    listContent.appendChild(card);
  });
}

function renderArtists(items) {
  if (!items || items.length === 0) {
    setEmpty("Hozircha artistlar topilmadi.");
    return;
  }

  listContent.innerHTML = "";
  items.forEach((artist, index) => {
    const card = document.createElement("div");
    card.className = "song-card";
    const title = document.createElement("p");
    title.className = "song-title";
    title.textContent = `${index + 1}. ${artist.artist}`;

    const meta = document.createElement("p");
    meta.className = "song-meta";
    meta.textContent = `Qo'shiqlar: ${artist.song_count} • Yuklash: ${artist.total_downloads}`;
    card.appendChild(title);
    card.appendChild(meta);
    card.addEventListener("click", () => loadArtist(artist.artist));
    listContent.appendChild(card);
  });
}

function buildAllTools() {
  listTools.innerHTML = "";
  const select = document.createElement("select");
  select.innerHTML = `
    <option value="downloads">Yuklash bo'yicha</option>
    <option value="plays">Eshitish bo'yicha</option>
    <option value="title">Nomi bo'yicha</option>
  `;
  select.addEventListener("change", () => {
    renderSongs(currentList, { showPins: true, sortMode: select.value });
  });
  listTools.appendChild(select);
  listTools.classList.remove("hidden");
}

function hideAllTools() {
  listTools.classList.add("hidden");
  listTools.innerHTML = "";
}

async function loadSection(sectionId) {
  const section = sections[sectionId];
  if (!section) return;

  currentSection = sectionId;
  listTitle.textContent = section.title;
  listSubtitle.textContent = section.subtitle || "";
  showListView();
  playerCard.classList.add("hidden");

  if (sectionId === "all") {
    buildAllTools();
  } else {
    hideAllTools();
  }

  setLoading();

  try {
    const data = await fetchJSON(section.endpoint);
    if (section.type === "artists") {
      renderArtists(data.items || []);
    } else if (section.type === "all") {
      renderSongs(data.items || [], { showPins: true, sortMode: "downloads" });
    } else {
      renderSongs(data.items || []);
    }
  } catch (err) {
    setEmpty("Ma'lumotlarni yuklashda xato yuz berdi.");
  }
}

async function loadArtist(artist) {
  listTitle.textContent = artist;
  listSubtitle.textContent = "Artist qo'shiqlari";
  setLoading();
  hideAllTools();

  try {
    const data = await fetchJSON(`/api/artist/${encodeURIComponent(artist)}`);
    renderSongs(data.items || []);
  } catch (err) {
    setEmpty("Artist qo'shiqlarini yuklashda xato.");
  }
}

document.querySelectorAll("[data-section]").forEach((item) => {
  item.addEventListener("click", () => loadSection(item.dataset.section));
});

backButton.addEventListener("click", showSectionView);
prevButton.addEventListener("click", handlePrev);
nextButton.addEventListener("click", handleNext);
audioPlayer.addEventListener("ended", handleNext);

if (window.Telegram && window.Telegram.WebApp) {
  window.Telegram.WebApp.ready();
  window.Telegram.WebApp.expand();
}
