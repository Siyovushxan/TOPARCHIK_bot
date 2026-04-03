const sectionView = document.getElementById("section-view");
const listView = document.getElementById("list-view");
const listTitle = document.getElementById("list-title");
const listSubtitle = document.getElementById("list-subtitle");
const listContent = document.getElementById("list-content");
const backButton = document.getElementById("backButton");
const playerCard = document.getElementById("player-card");
const playerTitle = document.getElementById("player-title");
const playerMeta = document.getElementById("player-meta");
const audioPlayer = document.getElementById("audio-player");

const sections = {
  top: {
    title: "Top yuklanganlar",
    subtitle: "Eng mashhur va tez-tez tinglangan qo'shiqlar.",
    endpoint: "/api/top",
    type: "songs",
  },
  youtube: {
    title: "YouTube",
    subtitle: "YouTube orqali yuklangan audio va videolar.",
    endpoint: "/api/platform/youtube",
    type: "songs",
  },
  instagram: {
    title: "Instagram",
    subtitle: "Instagram Reels va musiqiy kontent bo'limi.",
    endpoint: "/api/platform/instagram",
    type: "songs",
  },
  tiktok: {
    title: "TikTok",
    subtitle: "TikTokdan olingan eng yangi musiqalar.",
    endpoint: "/api/platform/tiktok",
    type: "songs",
  },
  artists: {
    title: "Artistlar",
    subtitle: "Ijrochilar ro'yxatini tanlang.",
    endpoint: "/api/artists",
    type: "artists",
  },
  genres: {
    title: "Janrlar",
    subtitle: "Janrni tanlang, shu nom bo'yicha qo'shiqlar chiqadi.",
    type: "genres",
  },
};

const genreList = [
  { label: "Pop", query: "pop" },
  { label: "Rap", query: "rap" },
  { label: "Dance", query: "dance" },
  { label: "Rock", query: "rock" },
  { label: "Lofi", query: "lofi" },
];

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
  listContent.innerHTML =
    '<div class="empty-state">Yuklanmoqda...</div>';
}

function setEmpty(message) {
  listContent.innerHTML =
    `<div class="empty-state">${message}</div>`;
}

function formatDuration(seconds) {
  const total = Number(seconds || 0);
  if (!total) return "";
  const mins = Math.floor(total / 60);
  const secs = Math.floor(total % 60);
  return `${mins}:${secs.toString().padStart(2, "0")}`;
}

async function fetchJSON(url) {
  const response = await fetch(url);
  if (!response.ok) {
    throw new Error("Request failed");
  }
  return response.json();
}

function renderSongs(items) {
  if (!items || items.length === 0) {
    setEmpty("Hozircha qo'shiqlar topilmadi.");
    return;
  }

  listContent.innerHTML = "";
  items.forEach((song) => {
    const card = document.createElement("div");
    card.className = "song-card";

    const info = document.createElement("div");
    const title = document.createElement("p");
    title.className = "song-title";
    title.textContent = song.title || "Unknown";

    const meta = document.createElement("p");
    meta.className = "song-meta";
    const duration = formatDuration(song.duration);
    const artist = song.artist ? ` • ${song.artist}` : "";
    meta.textContent = duration ? `${duration}${artist}` : artist;

    info.appendChild(title);
    if (meta.textContent) {
      info.appendChild(meta);
    }

    const actions = document.createElement("div");
    actions.className = "song-actions";
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
  items.forEach((artist) => {
    const card = document.createElement("div");
    card.className = "song-card";
    const title = document.createElement("p");
    title.className = "song-title";
    title.textContent = artist;
    card.appendChild(title);
    card.addEventListener("click", () => loadArtist(artist));
    listContent.appendChild(card);
  });
}

function renderGenres() {
  listContent.innerHTML = "";
  genreList.forEach((genre) => {
    const card = document.createElement("div");
    card.className = "song-card";
    const title = document.createElement("p");
    title.className = "song-title";
    title.textContent = genre.label;
    card.appendChild(title);
    card.addEventListener("click", () => loadGenre(genre));
    listContent.appendChild(card);
  });
}

function playSong(song) {
  if (!song.file_id) return;
  const src = `/api/audio/${encodeURIComponent(song.file_id)}?t=${Date.now()}`;
  audioPlayer.src = src;
  playerTitle.textContent = song.title || "Ijro";
  playerMeta.textContent = song.artist || "";
  playerCard.classList.remove("hidden");
  audioPlayer.play().catch(() => {});
}

async function loadSection(sectionId) {
  const section = sections[sectionId];
  if (!section) return;

  listTitle.textContent = section.title;
  listSubtitle.textContent = section.subtitle || "";
  showListView();

  if (section.type === "genres") {
    renderGenres();
    return;
  }

  setLoading();

  try {
    const data = await fetchJSON(section.endpoint);
    if (section.type === "artists") {
      renderArtists(data.items || []);
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

  try {
    const data = await fetchJSON(`/api/artist/${encodeURIComponent(artist)}`);
    renderSongs(data.items || []);
  } catch (err) {
    setEmpty("Artist qo'shiqlarini yuklashda xato.");
  }
}

async function loadGenre(genre) {
  listTitle.textContent = genre.label;
  listSubtitle.textContent = "Janr bo'yicha qo'shiqlar";
  setLoading();

  try {
    const data = await fetchJSON(`/api/search?q=${encodeURIComponent(genre.query)}`);
    renderSongs(data.items || []);
  } catch (err) {
    setEmpty("Janr bo'yicha natija topilmadi.");
  }
}

document.querySelectorAll("[data-section]").forEach((item) => {
  item.addEventListener("click", () => loadSection(item.dataset.section));
});

backButton.addEventListener("click", showSectionView);

if (window.Telegram && window.Telegram.WebApp) {
  window.Telegram.WebApp.ready();
  window.Telegram.WebApp.expand();
}
