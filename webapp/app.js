const searchInput = document.getElementById("searchInput");
const chipRow = document.getElementById("chipRow");
const homeView = document.getElementById("homeView");
const homeList = document.getElementById("homeList");
const artistsView = document.getElementById("artistsView");
const artistList = document.getElementById("artistList");
const artistDetailView = document.getElementById("artistDetailView");
const artistSongs = document.getElementById("artistSongs");
const artistName = document.getElementById("artistName");
const artistBack = document.getElementById("artistBack");
const libraryView = document.getElementById("libraryView");
const libraryList = document.getElementById("libraryList");
const libraryCount = document.getElementById("libraryCount");
const miniPlayer = document.getElementById("miniPlayer");
const miniTitle = document.getElementById("miniTitle");
const miniPlay = document.getElementById("miniPlay");
const miniNext = document.getElementById("miniNext");
const sheetBackdrop = document.getElementById("sheetBackdrop");
const playerSheet = document.getElementById("playerSheet");
const sheetClose = document.getElementById("sheetClose");
const sheetFav = document.getElementById("sheetFav");
const disc = document.getElementById("disc");
const sheetTitle = document.getElementById("sheetTitle");
const sheetArtist = document.getElementById("sheetArtist");
const sheetSeek = document.getElementById("sheetSeek");
const sheetCurrent = document.getElementById("sheetCurrent");
const sheetTotal = document.getElementById("sheetTotal");
const sheetPrev = document.getElementById("sheetPrev");
const sheetPlay = document.getElementById("sheetPlay");
const sheetNext = document.getElementById("sheetNext");
const sheetStats = document.getElementById("sheetStats");
const audioPlayer = document.getElementById("audio-player");

const API = {
  top: "/api/top?limit=500",
  instagram: "/api/platform/instagram?limit=500",
  youtube: "/api/platform/youtube?limit=500",
  tiktok: "/api/platform/tiktok?limit=500",
  all: "/api/all?limit=5000",
};

const state = {
  tab: "top",
  view: "home",
  playlist: [],
  currentIndex: -1,
  currentSong: null,
  searchTimer: null,
  favorites: new Set(),
  songStore: new Map(),
};

const FAV_KEY = "toparchik_favs";

function loadFavorites() {
  try {
    const raw = localStorage.getItem(FAV_KEY);
    if (raw) {
      state.favorites = new Set(JSON.parse(raw));
    }
  } catch {
    state.favorites = new Set();
  }
}

function saveFavorites() {
  localStorage.setItem(FAV_KEY, JSON.stringify([...state.favorites]));
}

function showSkeleton(container, count = 5) {
  container.innerHTML = "";
  for (let i = 0; i < count; i += 1) {
    const sk = document.createElement("div");
    sk.className = "skeleton";
    container.appendChild(sk);
  }
}

function setActiveView(view) {
  state.view = view;
  [homeView, artistsView, artistDetailView, libraryView].forEach((el) => {
    el.classList.remove("active");
  });
  if (view === "home") homeView.classList.add("active");
  if (view === "artists") artistsView.classList.add("active");
  if (view === "artist_detail") artistDetailView.classList.add("active");
  if (view === "library") libraryView.classList.add("active");
  document.querySelectorAll(".nav-item").forEach((item) => {
    item.classList.toggle("active", item.dataset.nav === view);
  });
}

function setActiveChip(tab) {
  state.tab = tab;
  document.querySelectorAll(".chip").forEach((chip) => {
    chip.classList.toggle("active", chip.dataset.tab === tab);
  });
}

function formatDuration(seconds) {
  const total = Number(seconds || 0);
  if (!total) return "0:00";
  const mins = Math.floor(total / 60);
  const secs = Math.floor(total % 60);
  return `${mins}:${secs.toString().padStart(2, "0")}`;
}

function formatCount(value) {
  const num = Number(value || 0);
  if (num >= 1000) {
    return `${(num / 1000).toFixed(1)}K`;
  }
  return `${num}`;
}

function platformIcon(song) {
  const platform = (song.platform || "").toLowerCase();
  if (platform === "youtube") return "▶️";
  if (platform === "instagram") return "📱";
  if (platform === "tiktok") return "🎵";
  if (state.tab === "top") return "🔥";
  if (state.tab === "all") return "♾️";
  return "🎵";
}

function getMarquee(title) {
  if (!title) return "";
  if (title.length <= 22) return title;
  return `<span class="marquee">${title}</span>`;
}

function mapSongStore(items) {
  items.forEach((song) => {
    if (song && song.id) {
      state.songStore.set(song.id, song);
    }
  });
}

async function fetchJSON(url, options = {}) {
  const response = await fetch(url, options);
  if (!response.ok) throw new Error("Request failed");
  return response.json();
}

function closeMenus() {
  document.querySelectorAll(".menu.show").forEach((menu) => menu.classList.remove("show"));
}

function renderSongs(container, items = [], playlist = true) {
  if (!items || items.length === 0) {
    container.innerHTML = '<div class="empty-state">Hozircha qo\'shiqlar topilmadi.</div>';
    return;
  }
  mapSongStore(items);
  if (playlist) {
    state.playlist = items;
  }
  container.innerHTML = "";

  items.forEach((song) => {
    const card = document.createElement("div");
    card.className = "song-card";
    card.dataset.songId = song.id || "";

    const left = document.createElement("div");
    left.className = "song-left";
    const icon = document.createElement("div");
    icon.className = "platform-icon";
    icon.textContent = platformIcon(song);

    const text = document.createElement("div");
    const title = document.createElement("div");
    title.className = "song-title";
    title.innerHTML = getMarquee(song.title || "Audio");

    const artist = document.createElement("div");
    artist.className = "song-artist";
    artist.textContent = song.artist || "Noma'lum ijrochi";

    const meta = document.createElement("div");
    meta.className = "song-meta";
    meta.textContent = `⏱️ ${formatDuration(song.duration)} | 🎧 ${formatCount(song.play_count)} | ⬇️ ${formatCount(song.download_count)}`;

    text.appendChild(title);
    text.appendChild(artist);
    text.appendChild(meta);
    left.appendChild(icon);
    left.appendChild(text);

    const actions = document.createElement("div");
    actions.className = "song-actions";
    const playBtn = document.createElement("button");
    playBtn.className = "play-button";
    playBtn.textContent = "▶";
    playBtn.addEventListener("click", () => playSong(song, items));

    const moreBtn = document.createElement("button");
    moreBtn.className = "more-button";
    moreBtn.textContent = "⋮";
    const menu = document.createElement("div");
    menu.className = "menu";
    const shareBtn = document.createElement("button");
    shareBtn.textContent = "Ulashish";
    shareBtn.addEventListener("click", () => handleShare(song));
    const uploadBtn = document.createElement("button");
    uploadBtn.textContent = "Kanalga yuklash";
    uploadBtn.addEventListener("click", () => window.open("https://t.me/toparchik_ai", "_blank"));
    menu.appendChild(shareBtn);
    menu.appendChild(uploadBtn);
    moreBtn.addEventListener("click", (e) => {
      e.stopPropagation();
      closeMenus();
      menu.classList.toggle("show");
    });

    actions.appendChild(playBtn);
    actions.appendChild(moreBtn);
    card.appendChild(left);
    card.appendChild(actions);
    card.appendChild(menu);
    container.appendChild(card);
  });

  setActiveCard(state.currentSong?.id);
}

function renderArtists(items = []) {
  if (!items || items.length === 0) {
    artistList.innerHTML = '<div class="empty-state">Hozircha artistlar topilmadi.</div>';
    return;
  }
  artistList.innerHTML = "";
  items.forEach((artist) => {
    const card = document.createElement("div");
    card.className = "song-card";
    const left = document.createElement("div");
    left.className = "song-left";
    const icon = document.createElement("div");
    icon.className = "platform-icon";
    icon.textContent = artist.artist?.charAt(0)?.toUpperCase() || "A";
    const text = document.createElement("div");
    const title = document.createElement("div");
    title.className = "song-title";
    title.textContent = artist.artist || "Artist";
    const meta = document.createElement("div");
    meta.className = "song-meta";
    meta.textContent = `Qo'shiqlar: ${artist.song_count} | ⬇️ ${formatCount(artist.total_downloads)}`;
    text.appendChild(title);
    text.appendChild(meta);
    left.appendChild(icon);
    left.appendChild(text);
    card.appendChild(left);
    card.addEventListener("click", () => loadArtistSongs(artist.artist));
    artistList.appendChild(card);
  });
}

function renderLibrary() {
  const items = [...state.favorites].map((id) => state.songStore.get(id)).filter(Boolean);
  libraryCount.textContent = items.length;
  renderSongs(libraryList, items, false);
}

async function loadTab(tab) {
  setActiveChip(tab);
  showSkeleton(homeList, 6);
  try {
    const data = await fetchJSON(API[tab]);
    renderSongs(homeList, data.items || [], true);
  } catch {
    homeList.innerHTML = '<div class="empty-state">Ma\'lumotlarni yuklashda xato yuz berdi.</div>';
  }
}

async function loadArtists() {
  showSkeleton(artistList, 5);
  try {
    const data = await fetchJSON("/api/artists");
    renderArtists(data.items || []);
  } catch {
    artistList.innerHTML = '<div class="empty-state">Artistlar yuklanmadi.</div>';
  }
}

async function loadArtistSongs(artist) {
  artistName.textContent = artist || "Artist";
  setActiveView("artist_detail");
  showSkeleton(artistSongs, 5);
  try {
    const data = await fetchJSON(`/api/artist/${encodeURIComponent(artist)}`);
    renderSongs(artistSongs, data.items || [], true);
  } catch {
    artistSongs.innerHTML = '<div class="empty-state">Artist qo\'shiqlari topilmadi.</div>';
  }
}

async function handleSearch(query) {
  if (!query) {
    loadTab(state.tab);
    return;
  }
  setActiveView("home");
  showSkeleton(homeList, 5);
  try {
    const data = await fetchJSON(`/api/search?q=${encodeURIComponent(query)}`);
    renderSongs(homeList, data.items || [], true);
  } catch {
    homeList.innerHTML = '<div class="empty-state">Qidiruvda xato yuz berdi.</div>';
  }
}

function setActiveCard(songId) {
  if (!songId) return;
  document.querySelectorAll(".song-card").forEach((card) => {
    card.classList.toggle("is-playing", card.dataset.songId === songId);
  });
}

async function playSong(song, list) {
  if (!song || !song.file_id) return;
  state.currentSong = song;
  if (list) {
    state.playlist = list;
    state.currentIndex = list.findIndex((item) => item.id === song.id);
  }
  audioPlayer.src = `/api/audio/${encodeURIComponent(song.file_id)}?t=${Date.now()}`;
  await audioPlayer.play().catch(() => {});
  updateMiniPlayer();
  updateSheet();
  setActiveCard(song.id);

  if (song.id) {
    try {
      await fetchJSON(`/api/play/${encodeURIComponent(song.id)}`, { method: "POST" });
      song.play_count = (song.play_count || 0) + 1;
      updateSheet();
      renderLibrary();
    } catch {
      // ignore
    }
  }
}

function updateMiniPlayer() {
  if (!state.currentSong) return;
  const title = state.currentSong.title || "Ijro";
  miniTitle.innerHTML = title.length > 22 ? `<span class="mini-marquee">${title}</span>` : title;
  miniPlayer.style.display = "flex";
}

function openSheet() {
  sheetBackdrop.classList.add("show");
  playerSheet.classList.add("show");
}

function closeSheet() {
  sheetBackdrop.classList.remove("show");
  playerSheet.classList.remove("show");
}

function updateSheet() {
  if (!state.currentSong) return;
  sheetTitle.textContent = state.currentSong.title || "Ijro";
  sheetArtist.textContent = state.currentSong.artist || "Noma'lum ijrochi";
  sheetStats.textContent = `🎧 ${formatCount(state.currentSong.play_count)} • ⬇️ ${formatCount(state.currentSong.download_count)} • ⏱️ ${formatDuration(state.currentSong.duration)}`;
  const isFav = state.favorites.has(state.currentSong.id);
  sheetFav.textContent = isFav ? "❤" : "♡";
}

function toggleFavorite() {
  if (!state.currentSong) return;
  if (state.favorites.has(state.currentSong.id)) {
    state.favorites.delete(state.currentSong.id);
  } else {
    state.favorites.add(state.currentSong.id);
  }
  saveFavorites();
  updateSheet();
  renderLibrary();
}

function handleShare(song) {
  const text = `${song.title || "Qo'shiq"} - ${song.artist || ""}`.trim();
  if (navigator.share) {
    navigator.share({ text });
  } else if (navigator.clipboard) {
    navigator.clipboard.writeText(text);
  }
  closeMenus();
}

function nextSong() {
  if (state.playlist.length === 0) return;
  const nextIndex = Math.min(state.playlist.length - 1, state.currentIndex + 1);
  state.currentIndex = nextIndex;
  playSong(state.playlist[nextIndex], state.playlist);
}

function prevSong() {
  if (state.playlist.length === 0) return;
  const prevIndex = Math.max(0, state.currentIndex - 1);
  state.currentIndex = prevIndex;
  playSong(state.playlist[prevIndex], state.playlist);
}

function updateProgress() {
  const duration = audioPlayer.duration || 0;
  const current = audioPlayer.currentTime || 0;
  if (duration > 0) {
    sheetSeek.value = Math.min(100, Math.max(0, (current / duration) * 100));
    sheetTotal.textContent = formatDuration(duration);
  }
  sheetCurrent.textContent = formatDuration(current);
  disc.classList.toggle("playing", !audioPlayer.paused);
  miniPlay.textContent = audioPlayer.paused ? "▶" : "⏸";
}

function initEvents() {
  chipRow.addEventListener("click", (e) => {
    const target = e.target.closest(".chip");
    if (!target) return;
    setActiveView("home");
    loadTab(target.dataset.tab);
  });

  document.querySelectorAll(".nav-item").forEach((item) => {
    item.addEventListener("click", () => {
      setActiveView(item.dataset.nav);
      if (item.dataset.nav === "artists") loadArtists();
      if (item.dataset.nav === "library") renderLibrary();
    });
  });

  artistBack.addEventListener("click", () => setActiveView("artists"));
  sheetClose.addEventListener("click", closeSheet);
  sheetBackdrop.addEventListener("click", closeSheet);
  sheetFav.addEventListener("click", toggleFavorite);
  miniPlayer.addEventListener("click", openSheet);
  miniPlay.addEventListener("click", (e) => {
    e.stopPropagation();
    if (audioPlayer.paused) {
      audioPlayer.play().catch(() => {});
    } else {
      audioPlayer.pause();
    }
  });
  miniNext.addEventListener("click", (e) => {
    e.stopPropagation();
    nextSong();
  });

  sheetPrev.addEventListener("click", prevSong);
  sheetNext.addEventListener("click", nextSong);
  sheetPlay.addEventListener("click", () => {
    if (audioPlayer.paused) {
      audioPlayer.play().catch(() => {});
    } else {
      audioPlayer.pause();
    }
  });
  sheetSeek.addEventListener("input", () => {
    if (!audioPlayer.duration) return;
    audioPlayer.currentTime = (Number(sheetSeek.value) / 100) * audioPlayer.duration;
  });

  audioPlayer.addEventListener("timeupdate", updateProgress);
  audioPlayer.addEventListener("loadedmetadata", updateProgress);
  audioPlayer.addEventListener("ended", nextSong);

  searchInput.addEventListener("input", (e) => {
    clearTimeout(state.searchTimer);
    state.searchTimer = setTimeout(() => {
      handleSearch(e.target.value.trim());
    }, 400);
  });

  document.addEventListener("click", closeMenus);
}

loadFavorites();
initEvents();
loadTab("top");

if (window.Telegram && window.Telegram.WebApp) {
  window.Telegram.WebApp.ready();
  window.Telegram.WebApp.expand();
}
