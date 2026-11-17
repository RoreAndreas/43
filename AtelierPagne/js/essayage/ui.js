// Interface de la salle d'essayage : dock (poses + vues), tiroir « Mes mesures »,
// guide de première visite.
const STORE = 'atelier-pagne:essayage:v1';
const GUIDE = 'atelier-pagne:guide-vu';

const load = (k) => { try { return JSON.parse(localStorage.getItem(k)); } catch { return null; } };
const save = (k, v) => { try { localStorage.setItem(k, JSON.stringify(v)); } catch { /* navigation privée */ } };

// Pictogrammes des poses (viewBox 0 0 40 48).
const FIG = {
  neutre: { head: [20, 7], lines: ['20,12 20,28', '20,14 15,27', '20,14 25,27', '20,28 17,44', '20,28 23,44'] },
  hanchement: { head: [21, 7], lines: ['21,12 19,28', '21,14 16,27', '21,14 26,26', '19,28 21,44', '19,28 15,36 17,44'] },
  'mains-hanches': { head: [20, 7], lines: ['20,12 20,28', '20,14 11,20 17,25', '20,14 29,20 23,25', '20,28 17,44', '20,28 23,44'] },
  'bras-ouverts': { head: [20, 7], lines: ['20,12 20,28', '20,14 7,19', '20,14 33,19', '20,28 15,44', '20,28 25,44'] },
  defile: { head: [20, 7], lines: ['20,12 20,28', '20,14 15,26', '20,14 25,24 27,27', '20,28 13,36 12,44', '20,28 25,36 28,44'] },
  photo: { head: [22, 7], lines: ['21,12 20,28', '21,14 29,20 24,25', '21,14 15,26', '20,28 21,44', '20,28 16,36 14,44'] },
  assise: { head: [15, 7], lines: ['15,12 15,28', '15,28 28,28 28,42', '15,14 20,22 26,25', '9,31 21,31 21,44 9,44 9,31'] },
};
const figSVG = (id) => {
  const f = FIG[id] || FIG.neutre;
  return `<svg viewBox="0 0 40 48" aria-hidden="true"><circle cx="${f.head[0]}" cy="${f.head[1]}" r="4"/>${f.lines
    .map((p) => `<polyline points="${p}"/>`).join('')}</svg>`;
};
// Libellés courts pour la barre.
const SHORT = { 'mains-hanches': 'Mains hanches', 'bras-ouverts': 'Bras ouverts', photo: 'Photo' };

const MEASURES = [
  { key: 'height', label: 'Hauteur', min: 145, max: 195, help: 'Du sommet de la tête au sol, pieds nus.' },
  { key: 'bust', label: 'Tour de poitrine', min: 70, max: 135, help: 'Au plus fort de la poitrine, mètre horizontal.' },
  { key: 'waist', label: 'Tour de taille', min: 55, max: 125, help: 'Au plus creux, au-dessus du nombril.' },
  { key: 'hip', label: 'Tour de hanches', min: 80, max: 145, help: 'Au plus fort des fesses.' },
];

export function initUI({ rig, POSES, VIEWS, PRESETS, controls, goToView, orbitBy, capturePhoto, setInsets }) {
  const $ = (s) => document.querySelector(s);
  const stored = load(STORE) || {};
  const state = {
    preset: PRESETS[stored.preset] ? stored.preset : 'femme',
    pose: POSES.some((p) => p.id === stored.pose) ? stored.pose : 'neutre',
    tapes: !!stored.tapes,
    spin: false,
  };
  const defaults = (p) => ({ ...rig.base(p).cm });
  state.cm = stored.cm && stored.preset === state.preset ? { ...defaults(state.preset), ...stored.cm } : defaults(state.preset);
  const persist = () => save(STORE, { preset: state.preset, cm: state.cm, pose: state.pose, tapes: state.tapes });

  const toastEl = $('#toast');
  let toastTimer;
  const toast = (msg) => {
    toastEl.textContent = msg;
    toastEl.classList.add('is-visible');
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => toastEl.classList.remove('is-visible'), 2400);
  };

  // ---------- Poses ----------
  const poseList = $('#pose-list');
  poseList.innerHTML = POSES.map((p) => `
    <button class="pose" type="button" role="radio" aria-checked="false" data-pose="${p.id}" title="${p.hint}">
      ${figSVG(p.id)}<span>${SHORT[p.id] || p.label}</span>
    </button>`).join('');
  const setPose = (id, animate = true) => {
    state.pose = id;
    rig.setPose(id, animate ? 0.95 : 0);
    const pose = POSES.find((p) => p.id === id);
    poseList.querySelectorAll('.pose').forEach((b) => b.setAttribute('aria-checked', String(b.dataset.pose === id)));
    $('#caption-title').textContent = pose.label;
    $('#caption-hint').textContent = pose.hint;
    persist();
  };
  poseList.addEventListener('click', (e) => {
    const b = e.target.closest('.pose');
    if (b) setPose(b.dataset.pose);
  });

  // ---------- Vues ----------
  const views = $('#views');
  views.innerHTML = VIEWS.map((v) => `<button class="view" type="button" data-view="${v.id}">${v.label}</button>`).join('') + `
    <button class="view view--spin" type="button" id="btn-spin" aria-pressed="false">
      <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M20 12a8 8 0 1 1-2.3-5.6M20 4v4h-4"/></svg>Rotation
    </button>`;
  const setActiveView = (id) => views.querySelectorAll('[data-view]').forEach((b) => b.classList.toggle('is-active', b.dataset.view === id));
  const setSpin = (on) => { state.spin = on; controls.autoRotate = on; $('#btn-spin').setAttribute('aria-pressed', String(on)); if (on) setActiveView(null); };
  views.addEventListener('click', (e) => {
    const b = e.target.closest('button');
    if (!b) return;
    if (b.id === 'btn-spin') return setSpin(!state.spin);
    setSpin(false);
    goToView(b.dataset.view);
    setActiveView(b.dataset.view);
  });
  setActiveView('face');

  // ---------- Tiroir « Mes mesures » ----------
  const drawer = $('#drawer');
  const mBtn = $('#btn-measures');
  const mobile = () => window.matchMedia('(max-width: 760px)').matches;
  const setDrawer = (open) => {
    drawer.classList.toggle('is-open', open);
    document.body.classList.toggle('drawer-open', open);
    drawer.setAttribute('aria-hidden', String(!open));
    mBtn.setAttribute('aria-expanded', String(open));
    if (open) {
      if (mobile()) setInsets({ bottom: drawer.offsetHeight - $('.dock').offsetHeight });
      else setInsets({ right: drawer.offsetWidth });
      drawer.querySelector('button, input')?.focus({ preventScroll: true });
    } else setInsets({});
  };
  mBtn.addEventListener('click', () => setDrawer(!drawer.classList.contains('is-open')));
  $('#drawer-close').addEventListener('click', () => { setDrawer(false); mBtn.focus(); });

  const seg = $('#preset');
  seg.innerHTML = Object.entries(PRESETS).map(([id, p]) => `<button type="button" data-preset="${id}" aria-pressed="false">${p.label}</button>`).join('');
  const refreshPreset = () => seg.querySelectorAll('button').forEach((b) => b.setAttribute('aria-pressed', String(b.dataset.preset === state.preset)));
  const fade = $('#fade');
  seg.addEventListener('click', (e) => {
    const b = e.target.closest('button');
    if (!b || b.dataset.preset === state.preset) return;
    state.preset = b.dataset.preset;
    state.cm = defaults(state.preset);
    refreshPreset();
    syncSliders();
    persist();
    fade.classList.add('is-on');
    setTimeout(() => { rig.setBody(state.preset, state.cm); fade.classList.remove('is-on'); }, 360);
  });

  const list = $('#measures');
  list.innerHTML = MEASURES.map((m) => `
    <div class="measure" data-key="${m.key}">
      <div class="measure__head">
        <label for="m-${m.key}">${m.label}</label>
        <output id="o-${m.key}" for="m-${m.key}"></output>
      </div>
      <div class="measure__ctrl">
        <button type="button" class="step" data-step="-1" aria-label="Diminuer : ${m.label.toLowerCase()}">−</button>
        <input type="range" id="m-${m.key}" min="${m.min}" max="${m.max}" step="1" aria-describedby="h-${m.key}">
        <button type="button" class="step" data-step="1" aria-label="Augmenter : ${m.label.toLowerCase()}">+</button>
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
    if (b) setMeasure(b.closest('.measure').dataset.key, state.cm[b.closest('.measure').dataset.key] + +b.dataset.step);
  });
  $('#btn-reset').addEventListener('click', () => {
    state.cm = defaults(state.preset);
    syncSliders();
    rebuild();
    persist();
    toast('Mesures standard rétablies');
  });

  const tapesToggle = $('#toggle-tapes');
  const setTapes = (on) => {
    state.tapes = on;
    tapesToggle.setAttribute('aria-checked', String(on));
    rig.setTapesVisible(on);
    persist();
  };
  tapesToggle.addEventListener('click', () => setTapes(!state.tapes));

  // ---------- Guide ----------
  const guide = $('#guide');
  const openGuide = () => { guide.hidden = false; guide.querySelector('[data-close]').focus(); };
  const closeGuide = () => { guide.hidden = true; save(GUIDE, true); };
  $('#btn-help').addEventListener('click', openGuide);
  guide.addEventListener('click', (e) => { if (e.target === guide || e.target.closest('[data-close]')) closeGuide(); });

  $('#btn-photo').addEventListener('click', () => {
    document.body.classList.add('flash');
    setTimeout(() => document.body.classList.remove('flash'), 450);
    capturePhoto();
    toast('Photo enregistrée');
  });

  // ---------- Clavier ----------
  window.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
      if (!guide.hidden) closeGuide();
      else if (drawer.classList.contains('is-open')) { setDrawer(false); mBtn.focus(); }
      return;
    }
    if (e.target.closest('input, textarea') || !guide.hidden || e.metaKey || e.ctrlKey || e.altKey) return;
    const n = parseInt(e.key, 10);
    if (n >= 1 && n <= POSES.length) setPose(POSES[n - 1].id);
    else if (e.key === 'ArrowLeft') { setSpin(false); orbitBy(-Math.PI / 4); }
    else if (e.key === 'ArrowRight') { setSpin(false); orbitBy(Math.PI / 4); }
    else if (e.key.toLowerCase() === 'r') setSpin(!state.spin);
    else if (e.key.toLowerCase() === 'm') setTapes(!state.tapes);
    else return;
    e.preventDefault();
  });

  // ---------- Démarrage ----------
  refreshPreset();
  syncSliders();
  rig.setBody(state.preset, state.cm);
  setPose(state.pose, false);
  tapesToggle.setAttribute('aria-checked', String(state.tapes));
  if (state.tapes) setTimeout(() => setTapes(true), 1800);

  return {
    ready() {
      setTimeout(() => {
        document.body.classList.add('is-ready');
        if (!load(GUIDE)) setTimeout(openGuide, 1100);
      }, 400);
    },
    onUserOrbit() { setActiveView(null); },
  };
}
