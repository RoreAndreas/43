// Interface de la salle d'essayage : poses, vues, morphologie et mesures.
const STORE = 'atelier-pagne:essayage:v1';

const load = () => { try { return JSON.parse(localStorage.getItem(STORE)) || {}; } catch { return {}; } };
const save = (s) => { try { localStorage.setItem(STORE, JSON.stringify(s)); } catch { /* navigation privée */ } };

// Pictogrammes « bonhomme » des poses (viewBox 0 0 40 48).
const FIG = {
  neutre: { head: [20, 7], lines: ['20,12 20,28', '20,14 15,27', '20,14 25,27', '20,28 17,44', '20,28 23,44'] },
  hanchement: { head: [21, 7], lines: ['21,12 19,28', '21,14 16,27', '21,14 26,26', '19,28 21,44', '19,28 15,36 17,44'] },
  'mains-hanches': { head: [20, 7], lines: ['20,12 20,28', '20,14 11,20 17,25', '20,14 29,20 23,25', '20,28 17,44', '20,28 23,44'] },
  'bras-ouverts': { head: [20, 7], lines: ['20,12 20,28', '20,14 7,19', '20,14 33,19', '20,28 15,44', '20,28 25,44'] },
  defile: { head: [20, 7], lines: ['20,12 20,28', '20,14 15,26', '20,14 25,24 27,27', '20,28 13,36 12,44', '20,28 25,36 28,44'] },
  photo: { head: [22, 7], lines: ['21,12 20,28', '21,14 29,20 24,25', '21,14 15,26', '20,28 21,44', '20,28 16,36 14,44'] },
  assise: { head: [15, 7], lines: ['15,12 15,28', '15,28 28,28 28,42', '15,14 20,22 26,25', '10,31 24,31', '13,31 12,44', '21,31 22,44'] },
};
const figSVG = (id) => {
  const f = FIG[id] || FIG.neutre;
  return `<svg viewBox="0 0 40 48" aria-hidden="true"><circle cx="${f.head[0]}" cy="${f.head[1]}" r="4.2"/>${f.lines
    .map((p) => `<polyline points="${p}"/>`).join('')}</svg>`;
};

const VIEW_ICONS = {
  face: '<circle cx="12" cy="7" r="3"/><path d="M7 21v-5a5 5 0 0 1 10 0v5"/>',
  'trois-quarts': '<circle cx="13" cy="7" r="3"/><path d="M8 21v-5c0-3 2-5 5-5s4 2 4 5v5"/>',
  profil: '<path d="M13 4a3 3 0 0 1 0 6"/><path d="M11 21v-6c0-2 1-4 3-4s3 2 3 4v6"/>',
  dos: '<circle cx="12" cy="7" r="3" fill="currentColor"/><path d="M7 21v-5a5 5 0 0 1 10 0v5"/>',
  dessus: '<ellipse cx="12" cy="15" rx="7" ry="3"/><path d="M12 3v7m-3-3 3 3 3-3"/>',
  buste: '<circle cx="11" cy="11" r="6"/><path d="m15.5 15.5 5 5"/>',
};

const MEASURES = [
  { key: 'height', label: 'Hauteur', min: 145, max: 195, help: 'Du sommet de la tête au sol, pieds nus.' },
  { key: 'bust', label: 'Tour de poitrine', min: 70, max: 135, help: 'Au plus fort de la poitrine, mètre bien horizontal.' },
  { key: 'waist', label: 'Tour de taille', min: 55, max: 125, help: 'Au plus creux, au-dessus du nombril.' },
  { key: 'hip', label: 'Tour de hanches', min: 80, max: 145, help: 'Au plus fort des fesses.' },
];

export function initUI({ rig, POSES, VIEWS, PRESETS, controls, goToView, orbitBy, capturePhoto }) {
  const $ = (s) => document.querySelector(s);
  const stored = load();
  const state = {
    preset: PRESETS[stored.preset] ? stored.preset : 'femme',
    cm: null,
    pose: POSES.some((p) => p.id === stored.pose) ? stored.pose : 'neutre',
    tapes: !!stored.tapes,
    autoRotate: false,
  };
  const defaults = (p) => ({ ...rig.base(p).cm });
  state.cm = stored.cm && stored.preset === state.preset ? { ...defaults(state.preset), ...stored.cm } : defaults(state.preset);
  const persist = () => save({ preset: state.preset, cm: state.cm, pose: state.pose, tapes: state.tapes });

  // ---------- Toast ----------
  const toastEl = $('#toast');
  let toastTimer;
  const toast = (msg) => {
    toastEl.textContent = msg;
    toastEl.classList.add('is-visible');
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => toastEl.classList.remove('is-visible'), 2600);
  };

  // ---------- Poses ----------
  const poseList = $('#pose-list');
  poseList.innerHTML = POSES.map((p, i) => `
    <li><button class="pose" type="button" data-pose="${p.id}" aria-pressed="false">
      <span class="pose__fig">${figSVG(p.id)}</span>
      <span class="pose__txt"><strong>${p.label}</strong><small>${p.hint}</small></span>
      <kbd class="pose__key" aria-hidden="true">${i + 1}</kbd>
    </button></li>`).join('');
  const setPose = (id, animate = true) => {
    state.pose = id;
    rig.setPose(id, animate ? 0.95 : 0);
    poseList.querySelectorAll('.pose').forEach((b) => b.setAttribute('aria-pressed', String(b.dataset.pose === id)));
    $('#current-pose').textContent = POSES.find((p) => p.id === id).label;
    persist();
  };
  poseList.addEventListener('click', (e) => {
    const b = e.target.closest('.pose');
    if (!b) return;
    setPose(b.dataset.pose);
    closeSheet();
  });

  // ---------- Vues ----------
  const views = $('#views');
  views.innerHTML = VIEWS.map((v) => `
    <button class="view" type="button" data-view="${v.id}">
      <svg viewBox="0 0 24 24" aria-hidden="true">${VIEW_ICONS[v.id]}</svg><span>${v.label}</span>
    </button>`).join('') + `
    <span class="views__sep" aria-hidden="true"></span>
    <button class="view view--spin" type="button" id="btn-spin" aria-pressed="false">
      <svg viewBox="0 0 24 24" aria-hidden="true" class="spool"><path d="M7 4h10M7 20h10"/><rect x="8" y="6" width="8" height="12" rx="1.5"/><path d="M8 9.5 16 8M8 13l8-1.5M8 16.5 16 15"/></svg><span>Tourner</span>
    </button>`;
  const setActiveView = (id) => views.querySelectorAll('[data-view]').forEach((b) => b.classList.toggle('is-active', b.dataset.view === id));
  views.addEventListener('click', (e) => {
    const b = e.target.closest('button');
    if (!b) return;
    if (b.id === 'btn-spin') return toggleSpin();
    setSpin(false);
    goToView(b.dataset.view);
    setActiveView(b.dataset.view);
  });
  const setSpin = (on) => {
    state.autoRotate = on;
    controls.autoRotate = on;
    $('#btn-spin').setAttribute('aria-pressed', String(on));
  };
  const toggleSpin = () => { setSpin(!state.autoRotate); if (state.autoRotate) setActiveView(null); };
  setActiveView('face');

  // ---------- Morphologie ----------
  const seg = $('#preset');
  seg.innerHTML = Object.entries(PRESETS).map(([id, p]) => `<button type="button" data-preset="${id}" aria-pressed="false">${p.label}</button>`).join('');
  const refreshPreset = () => seg.querySelectorAll('button').forEach((b) => b.setAttribute('aria-pressed', String(b.dataset.preset === state.preset)));
  seg.addEventListener('click', (e) => {
    const b = e.target.closest('button');
    if (!b || b.dataset.preset === state.preset) return;
    state.preset = b.dataset.preset;
    state.cm = defaults(state.preset);
    refreshPreset();
    syncSliders();
    swapBody();
    persist();
  });

  const list = $('#measures');
  list.innerHTML = MEASURES.map((m) => `
    <div class="measure" data-key="${m.key}">
      <div class="measure__head">
        <label for="m-${m.key}">${m.label}</label>
        <output id="o-${m.key}" for="m-${m.key}"></output>
      </div>
      <div class="measure__ctrl">
        <button type="button" class="step" data-step="-1" aria-label="Diminuer ${m.label.toLowerCase()}">−</button>
        <input type="range" id="m-${m.key}" min="${m.min}" max="${m.max}" step="1" aria-describedby="h-${m.key}">
        <button type="button" class="step" data-step="1" aria-label="Augmenter ${m.label.toLowerCase()}">+</button>
      </div>
      <p class="measure__help" id="h-${m.key}">${m.help}</p>
    </div>`).join('');
  const syncSliders = () => {
    for (const m of MEASURES) {
      $(`#m-${m.key}`).value = state.cm[m.key];
      $(`#o-${m.key}`).textContent = `${state.cm[m.key]} cm`;
    }
  };
  let pending = false;
  const rebuild = () => {
    if (pending) return;
    pending = true;
    requestAnimationFrame(() => { pending = false; rig.setBody(state.preset, state.cm); });
  };
  const setMeasure = (key, v) => {
    const m = MEASURES.find((x) => x.key === key);
    state.cm[key] = Math.max(m.min, Math.min(m.max, Math.round(v)));
    syncSliders();
    rebuild();
    persist();
  };
  list.addEventListener('input', (e) => {
    if (e.target.type === 'range') setMeasure(e.target.closest('.measure').dataset.key, +e.target.value);
  });
  list.addEventListener('click', (e) => {
    const b = e.target.closest('.step');
    if (!b) return;
    const key = b.closest('.measure').dataset.key;
    setMeasure(key, state.cm[key] + +b.dataset.step);
  });
  list.addEventListener('change', () => toast('Mesures enregistrées sur cet appareil'));
  $('#btn-reset').addEventListener('click', () => {
    state.cm = defaults(state.preset);
    syncSliders();
    rebuild();
    persist();
    toast('Mesures du mannequin standard rétablies');
  });

  const tapesToggle = $('#toggle-tapes');
  const setTapes = (on) => {
    state.tapes = on;
    tapesToggle.setAttribute('aria-checked', String(on));
    rig.setTapesVisible(on);
    persist();
  };
  tapesToggle.addEventListener('click', () => setTapes(!state.tapes));

  // Changement de morphologie : petit fondu « rideau de cabine ».
  const curtain = $('#curtain');
  const swapBody = () => {
    curtain.classList.add('is-closing');
    setTimeout(() => {
      rig.setBody(state.preset, state.cm);
      curtain.classList.remove('is-closing');
      curtain.classList.add('is-opening');
      setTimeout(() => curtain.classList.remove('is-opening'), 650);
    }, 420);
  };

  // ---------- Feuilles (mobile) ----------
  const tabs = document.querySelectorAll('.tabbar [data-sheet]');
  const closeSheet = () => {
    document.body.dataset.sheet = '';
    tabs.forEach((t) => t.setAttribute('aria-expanded', 'false'));
  };
  tabs.forEach((t) => t.addEventListener('click', () => {
    const open = document.body.dataset.sheet === t.dataset.sheet;
    closeSheet();
    if (!open) { document.body.dataset.sheet = t.dataset.sheet; t.setAttribute('aria-expanded', 'true'); }
  }));
  document.querySelectorAll('[data-close-sheet]').forEach((b) => b.addEventListener('click', closeSheet));

  // ---------- Aide ----------
  const help = $('#help');
  $('#btn-help').addEventListener('click', () => help.showModal());
  help.addEventListener('click', (e) => { if (e.target === help || e.target.closest('[data-close]')) help.close(); });

  $('#btn-photo').addEventListener('click', () => {
    document.body.classList.add('flash');
    setTimeout(() => document.body.classList.remove('flash'), 400);
    capturePhoto();
    toast('Photo enregistrée dans vos téléchargements');
  });

  // ---------- Clavier ----------
  window.addEventListener('keydown', (e) => {
    if (e.target.closest('input, textarea, dialog[open]') || e.metaKey || e.ctrlKey || e.altKey) return;
    const n = parseInt(e.key, 10);
    if (n >= 1 && n <= POSES.length) setPose(POSES[n - 1].id);
    else if (e.key === 'ArrowLeft') { setSpin(false); orbitBy(-Math.PI / 4); }
    else if (e.key === 'ArrowRight') { setSpin(false); orbitBy(Math.PI / 4); }
    else if (e.key.toLowerCase() === 'r') toggleSpin();
    else if (e.key.toLowerCase() === 'm') setTapes(!state.tapes);
    else return;
    e.preventDefault();
  });

  // ---------- Démarrage ----------
  refreshPreset();
  syncSliders();
  rig.setBody(state.preset, state.cm);
  setPose(state.pose, false);
  if (state.tapes) setTimeout(() => setTapes(true), 2200);
  tapesToggle.setAttribute('aria-checked', String(state.tapes));

  const hint = $('#hint');
  return {
    ready() {
      setTimeout(() => document.body.classList.add('is-ready'), 600);
      setTimeout(() => hint.classList.add('is-hidden'), 9000);
    },
    onUserOrbit() {
      hint.classList.add('is-hidden');
      setActiveView(null);
    },
  };
}
