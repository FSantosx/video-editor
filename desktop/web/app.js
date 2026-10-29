// Interface local do Video Editor: conversa com a mesma API do app Android.
"use strict";

const $ = (sel, root = document) => root.querySelector(sel);
const FORMAT_LABEL = { "9:16": "9:16 · Shorts/Reels/TikTok", "1:1": "1:1 · Feed" };
const FORMAT_CLASS = { "9:16": "r916", "1:1": "r11" };
const STEP_LABEL = {
  probe: "Preparando o vídeo", audio: "Extraindo o áudio", transcribe: "Transcrevendo a fala",
  analyze: "Analisando o áudio", select: "Escolhendo os melhores trechos",
};
const WINDOW_SLACK = 30;

const state = {
  system: null,
  videos: [],
  currentId: location.hash.match(/^#\/v\/(\w+)/)?.[1] ?? null,
  lastDetailKey: "",
  lastListKey: "",
  uploads: [],     // {id, name, progress, error}
  editing: null,   // {videoId, shortId, group: [...shorts], video}
};

// ---------- utilidades ----------
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) =>
  ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);

function fmtTime(sec) {
  const t = Math.round(sec);
  const h = Math.floor(t / 3600), m = Math.floor((t % 3600) / 60), s = String(t % 60).padStart(2, "0");
  return h ? `${h}:${String(m).padStart(2, "0")}:${s}` : `${m}:${s}`;
}

function toast(msg, isError = false) {
  const el = $("#toast");
  el.textContent = msg;
  el.className = `toast show${isError ? " err" : ""}`;
  clearTimeout(toast.timer);
  toast.timer = setTimeout(() => (el.className = "toast"), isError ? 6000 : 3000);
}

async function api(path, options = {}) {
  const res = await fetch(path, {
    ...options,
    headers: options.body && !(options.body instanceof FormData)
      ? { "Content-Type": "application/json", ...options.headers } : options.headers,
  });
  if (!res.ok) {
    let detail = res.statusText;
    try { detail = (await res.json()).detail ?? detail; } catch { /* sem JSON */ }
    throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
  }
  return res.status === 204 ? null : res.json();
}

const isAnalyzing = (v) => ["uploading", "queued", "analyzing"].includes(v.status);
const isRendering = (s) => ["pending", "queued", "rendering"].includes(s.render.status);
const isBusy = (v) => isAnalyzing(v) || v.shorts.some(isRendering);

function videoStatus(v) {
  if (v.status === "analyzing") return STEP_LABEL[v.step] ?? "Analisando";
  if (v.status === "queued") return "Na fila";
  if (v.status === "uploading") return "Enviando";
  if (v.status === "error") return "Falhou";
  if (!v.shorts.length) return "Nenhum trecho bom encontrado";
  const groups = new Set(v.shorts.map((s) => s.group ?? s.id)).size;
  const pending = v.shorts.filter(isRendering).length;
  return pending ? `Gerando cortes (${v.shorts.length - pending}/${v.shorts.length})`
    : `${groups} ${groups === 1 ? "corte" : "cortes"} · ${v.shorts.length} vídeos`;
}

// ---------- sistema ----------
async function loadSystem() {
  try {
    state.system = await api("/system");
  } catch { return; }
  const s = state.system;
  const gpu = s.whisper_device === "cuda";
  const nvenc = s.video_encoder === "h264_nvenc";
  $("#system").innerHTML = [
    `<span class="chip ${gpu ? "good" : "warn"}" title="Onde roda a transcrição">Whisper ${esc(s.whisper_model)} · ${gpu ? "GPU" : s.whisper_device === "auto" ? "GPU/CPU" : "CPU"}</span>`,
    `<span class="chip ${nvenc ? "good" : ""}" title="Encoder de vídeo">${nvenc ? "NVENC (GPU)" : "x264 (CPU)"}</span>`,
    `<span class="chip">${s.formats.join(" + ")}</span>`,
    `<span class="chip" title="${esc(s.data_dir)}">${s.disk_free_gb} GB livres</span>`,
  ].join("");
}

// ---------- lista ----------
function renderList() {
  const key = JSON.stringify([state.currentId, state.videos.map((v) => [v.id, videoStatus(v), v.progress])]);
  if (key === state.lastListKey) return;
  state.lastListKey = key;
  const list = $("#video-list");
  if (!state.videos.length) {
    list.innerHTML = `<li class="muted small">Nenhum vídeo ainda.</li>`;
    return;
  }
  list.innerHTML = state.videos.map((v) => `
    <li class="video-item ${v.id === state.currentId ? "active" : ""}" data-id="${v.id}" tabindex="0">
      <span class="title" title="${esc(v.filename)}">${esc(v.filename)}</span>
      <button class="icon-btn" data-delete="${v.id}" aria-label="Excluir ${esc(v.filename)}" title="Excluir">🗑</button>
      <span class="status ${v.status === "error" ? "err" : ""}">${esc(videoStatus(v))}${
        v.meta ? ` · ${fmtTime(v.meta.duration)}` : ""}</span>
      ${isAnalyzing(v) ? `<div class="bar" style="grid-column:1/-1"><i style="width:${Math.round(v.progress * 100)}%"></i></div>` : ""}
    </li>`).join("");
}

$("#video-list").addEventListener("click", async (e) => {
  const del = e.target.closest("[data-delete]");
  if (del) {
    e.stopPropagation();
    const v = state.videos.find((x) => x.id === del.dataset.delete);
    if (!confirm(`Excluir "${v?.filename}" e todos os cortes gerados?`)) return;
    try {
      await api(`/videos/${del.dataset.delete}`, { method: "DELETE" });
      if (state.currentId === del.dataset.delete) select(null);
      refresh();
    } catch (err) { toast(err.message, true); }
    return;
  }
  const item = e.target.closest(".video-item");
  if (item) select(item.dataset.id);
});
$("#video-list").addEventListener("keydown", (e) => {
  if (e.key === "Enter" && e.target.matches(".video-item")) select(e.target.dataset.id);
});

function select(id) {
  state.currentId = id;
  state.lastDetailKey = "";
  history.replaceState(null, "", id ? `#/v/${id}` : "#");
  renderList();
  renderDetail();
}

// ---------- detalhe ----------
function groupShorts(video) {
  const order = state.system?.formats ?? ["9:16", "1:1"];
  const groups = new Map();
  for (const s of video.shorts) {
    const g = s.group ?? s.id;
    if (!groups.has(g)) groups.set(g, []);
    groups.get(g).push(s);
  }
  for (const list of groups.values()) {
    list.sort((a, b) => order.indexOf(a.format ?? "9:16") - order.indexOf(b.format ?? "9:16"));
  }
  return [...groups.values()];
}

function renderDetail() {
  const el = $("#detail");
  const v = state.videos.find((x) => x.id === state.currentId);
  if (!v) {
    if (state.currentId && state.videos.length) select(null);
    state.lastDetailKey = "";
    el.innerHTML = `<div class="empty"><p>Envie um vídeo longo com alguém falando.</p>
      <p class="muted">Ele é transcrito, os melhores trechos viram cortes em <b>${
        esc((state.system?.formats ?? ["9:16", "1:1"]).join("</b> e <b>"))}</b>, com legendas e o rosto enquadrado.</p></div>`;
    return;
  }
  const key = JSON.stringify(v);
  if (key === state.lastDetailKey) return;
  state.lastDetailKey = key;

  const head = `
    <div class="detail-head">
      <div>
        <h2>${esc(v.filename)}</h2>
        <div class="meta">${v.meta ? `${fmtTime(v.meta.duration)} · ${v.meta.width}×${v.meta.height}` : ""}${
          v.analysis_seconds ? ` · analisado em ${fmtTime(v.analysis_seconds)}` : ""}</div>
      </div>
      ${state.system?.desktop ? `<button class="btn small" data-open-folder>📂 Abrir pasta dos cortes</button>` : ""}
    </div>`;

  if (v.status === "error") {
    el.innerHTML = `${head}<div class="progress-card"><p><b>Falhou.</b></p>
      <pre class="small muted" style="white-space:pre-wrap">${esc(v.error)}</pre>
      <button class="btn primary" data-reanalyze>Tentar de novo</button></div>`;
    return;
  }
  if (isAnalyzing(v)) {
    const pct = Math.round(v.progress * 100);
    el.innerHTML = `${head}<div class="progress-card">
      <p><b>${esc(videoStatus(v))}</b> · ${pct}%</p>
      <div class="bar ${pct ? "" : "indeterminate"}"><i style="width:${pct}%"></i></div>
      <p class="muted small">Pode deixar rodando: o processamento continua mesmo com esta aba fechada.</p></div>`;
    return;
  }
  if (!v.shorts.length) {
    el.innerHTML = `${head}<p class="muted">Nenhum trecho com fala suficiente foi encontrado.</p>`;
    return;
  }
  el.innerHTML = head + `<div class="groups">${groupShorts(v).map((g) => renderGroup(v, g)).join("")}</div>`;
}

function renderGroup(v, shorts) {
  const main = shorts[0];
  const formats = shorts.map((s) => {
    const r = s.render;
    const fmt = s.format ?? "9:16";
    const ver = r.version ?? 0;
    const thumb = ver ? `<img src="/videos/${v.id}/shorts/${s.id}/thumb?v=${ver}" alt="" loading="lazy">` : "";
    let overlay = "";
    if (isRendering(s)) {
      overlay = `<div class="overlay">${r.status === "rendering" ? `Renderizando ${Math.round(r.progress * 100)}%` : "Na fila"}</div>`;
    } else if (r.status === "error") {
      overlay = `<div class="overlay">Erro no render</div>`;
    }
    return `<div class="fmt">
      <button class="thumb ${FORMAT_CLASS[fmt] ?? ""}" data-edit="${s.id}" aria-label="Abrir corte ${esc(fmt)}">
        ${thumb}${overlay}<span class="badge">${fmtTime(s.duration)}</span>
      </button>
      <div class="fmt-label"><span>${esc(fmt)}</span>${ver ? `<a href="/videos/${v.id}/shorts/${s.id}/video?v=${ver}" download>Baixar</a>` : ""}</div>
    </div>`;
  }).join("");
  return `<article class="group">
    <div class="group-head"><h3>${esc(main.title)}</h3><span class="score" title="Nota da seleção">🔥 ${main.score}</span></div>
    <div class="formats">${formats}</div>
    <div class="group-actions"><button class="btn small" data-edit="${main.id}">Editar</button></div>
  </article>`;
}

$("#detail").addEventListener("click", async (e) => {
  const v = state.videos.find((x) => x.id === state.currentId);
  if (!v) return;
  if (e.target.closest("[data-open-folder]")) {
    api(`/videos/${v.id}/open-folder`, { method: "POST" }).catch((err) => toast(err.message, true));
  } else if (e.target.closest("[data-reanalyze]")) {
    try {
      await api(`/videos/${v.id}/reanalyze`, { method: "POST" });
      refresh();
    } catch (err) { toast(err.message, true); }
  } else if (e.target.closest("[data-edit]")) {
    openEditor(v, Number(e.target.closest("[data-edit]").dataset.edit));
  }
});

// ---------- editor ----------
const editor = $("#editor");
const f = {
  title: $("#f-title"), start: $("#f-start"), end: $("#f-end"), captions: $("#f-captions"),
  titleOverlay: $("#f-title-overlay"), auto: $("#f-auto"), crop: $("#f-crop"), sync: $("#f-sync"),
  cta: $("#f-cta"), ctaText: $("#f-cta-text"), teaser: $("#f-teaser"),
};

function openEditor(video, shortId) {
  const short = video.shorts.find((s) => s.id === shortId);
  const group = video.shorts.filter((s) => (s.group ?? s.id) === (short.group ?? short.id));
  state.editing = { videoId: video.id, shortId, group, video };

  $("#editor-title").textContent = `Editar corte · ${short.title}`;
  $("#editor-players").innerHTML = groupShorts({ shorts: group })[0].map((s) => {
    const fmt = s.format ?? "9:16";
    const ver = s.render.version ?? 0;
    return `<figure>${ver
      ? `<video class="${fmt === "1:1" ? "v11" : "v916"}" src="/videos/${video.id}/shorts/${s.id}/video?v=${ver}" controls preload="metadata"></video>`
      : `<div class="thumb ${FORMAT_CLASS[fmt]} ${fmt === "1:1" ? "v11" : "v916"}">Ainda não renderizado</div>`}
      <figcaption>${esc(FORMAT_LABEL[fmt] ?? fmt)}</figcaption></figure>`;
  }).join("");

  const duration = video.meta?.duration ?? short.window.end;
  const min = Math.max(0, short.window.start - WINDOW_SLACK);
  const max = Math.min(duration, short.window.end + WINDOW_SLACK);
  for (const input of [f.start, f.end]) { input.min = min; input.max = max; }
  f.title.value = short.title;
  f.start.value = short.window.start;
  f.end.value = short.window.end;
  f.captions.checked = short.captions.enabled;
  f.titleOverlay.checked = short.title_overlay.enabled;
  f.cta.checked = Boolean(short.cta?.enabled);
  f.teaser.checked = Boolean(short.teaser?.enabled);
  $("#o-teaser").textContent = short.teaser?.text ? `“${short.teaser.text}”` : "";
  f.ctaText.value = short.cta?.text ?? "";
  f.auto.checked = !short.reframe.manual;
  f.crop.value = short.reframe.centers?.[0] ?? 0.5;
  // Recorte manual só faz sentido quando o original é mais largo que a saída
  const wide = video.meta && video.meta.width / video.meta.height > 1;
  $("#reframe-box").hidden = !wide;
  f.sync.closest("label").hidden = group.length < 2;
  $("#f-text").textContent = short.text;
  updateRangeLabels();
  editor.showModal();
}

function updateRangeLabels() {
  let start = Number(f.start.value), end = Number(f.end.value);
  if (end - start < 5) {  // trecho mínimo de 5s
    if (document.activeElement === f.start) f.start.value = start = end - 5;
    else f.end.value = end = start + 5;
  }
  $("#o-start").textContent = fmtTime(start);
  $("#o-end").textContent = fmtTime(end);
  $("#o-length").textContent = `${Math.round(end - start)}s no original · pausas longas são cortadas automaticamente`;
  $("#crop-row").hidden = f.auto.checked;
  f.ctaText.hidden = !f.cta.checked;
}
for (const el of [f.start, f.end, f.auto, f.cta]) el.addEventListener("input", updateRangeLabels);

editor.addEventListener("click", (e) => {
  if (e.target.closest("[data-close]") || e.target === editor) editor.close();
});
editor.addEventListener("close", () => {
  for (const v of editor.querySelectorAll("video")) v.pause();
  $("#editor-players").innerHTML = "";
  state.editing = null;
});

$("#editor-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const { videoId, shortId, group } = state.editing;
  const short = group.find((s) => s.id === shortId);
  const patch = {};
  if (f.title.value.trim() !== short.title) patch.title = f.title.value.trim();
  const start = Number(f.start.value), end = Number(f.end.value);
  if (Math.abs(start - short.window.start) > 0.05 || Math.abs(end - short.window.end) > 0.05) {
    patch.start = Math.round(start * 100) / 100;
    patch.end = Math.round(end * 100) / 100;
  }
  if (f.captions.checked !== short.captions.enabled) patch.captions = f.captions.checked;
  if (f.titleOverlay.checked !== short.title_overlay.enabled) patch.title_overlay = f.titleOverlay.checked;
  if (f.cta.checked !== Boolean(short.cta?.enabled)) patch.cta = f.cta.checked;
  if (f.teaser.checked !== Boolean(short.teaser?.enabled)) patch.teaser = f.teaser.checked;
  if (f.cta.checked && f.ctaText.value.trim() && f.ctaText.value.trim() !== short.cta?.text) {
    patch.cta_text = f.ctaText.value.trim();
  }
  if (!$("#reframe-box").hidden) {
    if (f.auto.checked && short.reframe.mode !== "auto") patch.auto_reframe = true;
    if (!f.auto.checked) patch.crop_center = Number(f.crop.value);
  }
  if (!Object.keys(patch).length) { editor.close(); return; }
  patch.sync_group = f.sync.checked && group.length > 1;

  $("#f-save").disabled = true;
  try {
    await api(`/videos/${videoId}/shorts/${shortId}`, { method: "PATCH", body: JSON.stringify(patch) });
    editor.close();
    toast("Salvo! Gerando a nova versão…");
    refresh();
  } catch (err) {
    toast(err.message, true);
  } finally {
    $("#f-save").disabled = false;
  }
});

// ---------- upload ----------
const dropzone = $("#dropzone");
const fileInput = $("#file-input");
dropzone.addEventListener("keydown", (e) => { if (e.key === "Enter" || e.key === " ") fileInput.click(); });
fileInput.addEventListener("change", () => { enqueue([...fileInput.files]); fileInput.value = ""; });
for (const ev of ["dragenter", "dragover"]) {
  dropzone.addEventListener(ev, (e) => { e.preventDefault(); dropzone.classList.add("over"); });
}
for (const ev of ["dragleave", "drop"]) {
  dropzone.addEventListener(ev, (e) => { e.preventDefault(); dropzone.classList.remove("over"); });
}
dropzone.addEventListener("drop", (e) => enqueue([...e.dataTransfer.files]));

let uploading = false;
function enqueue(files) {
  for (const file of files.filter((x) => x.type.startsWith("video/") || /\.(mp4|mov|m4v|mkv|webm)$/i.test(x.name))) {
    state.uploads.push({ id: crypto.randomUUID(), file, name: file.name, progress: 0, error: null });
  }
  renderUploads();
  if (!uploading) nextUpload();
}

function renderUploads() {
  $("#uploads").innerHTML = state.uploads.map((u) => `
    <div class="upload ${u.error ? "error" : ""}">
      <div class="name"><span title="${esc(u.name)}">${esc(u.name)}</span>
        <span>${u.error ? "erro" : `${Math.round(u.progress * 100)}%`}</span></div>
      ${u.error ? `<div class="small">${esc(u.error)}</div>` : `<div class="bar"><i style="width:${u.progress * 100}%"></i></div>`}
    </div>`).join("");
}

function nextUpload() {
  const u = state.uploads.find((x) => !x.error && x.progress < 1);
  if (!u) { uploading = false; return; }
  uploading = true;
  const form = new FormData();
  form.append("file", u.file);
  const xhr = new XMLHttpRequest();
  xhr.open("POST", "/videos");
  xhr.upload.onprogress = (e) => { if (e.lengthComputable) { u.progress = e.loaded / e.total; renderUploads(); } };
  xhr.onload = () => {
    if (xhr.status === 201) {
      const video = JSON.parse(xhr.responseText);
      state.uploads = state.uploads.filter((x) => x !== u);
      select(video.id);
      refresh();
    } else {
      try { u.error = JSON.parse(xhr.responseText).detail; } catch { u.error = `HTTP ${xhr.status}`; }
      setTimeout(() => { state.uploads = state.uploads.filter((x) => x !== u); renderUploads(); }, 8000);
    }
    renderUploads();
    nextUpload();
  };
  xhr.onerror = () => { u.error = "Servidor não respondeu"; renderUploads(); nextUpload(); };
  xhr.send(form);
}

window.addEventListener("beforeunload", (e) => { if (uploading) e.preventDefault(); });

// ---------- atualização periódica ----------
let timer = null;
async function refresh() {
  clearTimeout(timer);
  try {
    state.videos = await api("/videos");
    renderList();
    renderDetail();
  } catch (err) {
    $("#video-list").innerHTML = `<li class="status err">Servidor indisponível: ${esc(err.message)}</li>`;
    state.lastListKey = "";
  }
  if (!["cuda", "cpu"].includes(state.system?.whisper_device)) loadSystem();  // modelo ainda carregando
  const busy = state.videos.some(isBusy) || uploading;
  timer = setTimeout(refresh, busy ? 2000 : 10000);
}

loadSystem();
refresh();
