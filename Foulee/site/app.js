/*
 * Foulée — planificateur de runs sur Google Maps.
 *
 * Un parcours = une liste de points : le premier est le départ, le dernier
 * l'arrivée, ceux du milieu des étapes. En mode « Boucle », l'arrivée revient
 * au départ et tous les points ajoutés sont des étapes.
 *
 * Itinéraire piéton : Routes API (REST), puis le DirectionsService historique
 * si la première n'est pas activée, puis la ligne droite en dernier recours.
 */
(() => {
  'use strict';

  const CFG = Object.assign(
    { googleMapsApiKey: '', defaultCenter: { lat: 5.3364, lng: -4.0267 }, defaultZoom: 14 },
    window.FOULEE_CONFIG || {}
  );

  // ---------- stockage local ----------
  const LS = {
    get(k, d) { try { const v = localStorage.getItem('foulee.' + k); return v == null ? d : JSON.parse(v); } catch { return d; } },
    set(k, v) { try { localStorage.setItem('foulee.' + k, JSON.stringify(v)); } catch { /* navigation privée */ } },
    del(k) { try { localStorage.removeItem('foulee.' + k); } catch { /* idem */ } },
  };

  const THEMES = {
    neon:  { name: 'Néon',  a: '#22d3ee', b: '#ff3d81' },
    lave:  { name: 'Lave',  a: '#ffb020', b: '#ff3d3d' },
    acide: { name: 'Acide', a: '#c6ff3d', b: '#22d3ee' },
    ultra: { name: 'Ultra', a: '#a78bfa', b: '#ff3d81' },
  };
  const PRESETS = [
    { label: '🐢 7:00', pace: 420 }, { label: '😎 6:00', pace: 360 }, { label: '🔥 5:15', pace: 315 },
    { label: '⚡ 4:30', pace: 270 }, { label: '🚀 3:45', pace: 225 },
  ];
  const MAX_POINTS = 27; // départ + arrivée + 25 étapes (limite Google en marche à pied)

  const DARK_STYLE = [
    { elementType: 'geometry', stylers: [{ color: '#11151d' }] },
    { elementType: 'labels.text.fill', stylers: [{ color: '#7d8699' }] },
    { elementType: 'labels.text.stroke', stylers: [{ color: '#0b0d12' }] },
    { elementType: 'labels.icon', stylers: [{ saturation: -80 }, { lightness: -30 }] },
    { featureType: 'administrative', elementType: 'geometry', stylers: [{ color: '#2a3140' }] },
    { featureType: 'administrative.land_parcel', stylers: [{ visibility: 'off' }] },
    { featureType: 'poi', elementType: 'geometry', stylers: [{ color: '#151a24' }] },
    { featureType: 'poi.business', stylers: [{ visibility: 'off' }] },
    { featureType: 'poi.park', elementType: 'geometry', stylers: [{ color: '#0f2219' }] },
    { featureType: 'poi.park', elementType: 'labels.text.fill', stylers: [{ color: '#4f8a63' }] },
    { featureType: 'poi.sports_complex', elementType: 'geometry', stylers: [{ color: '#132a20' }] },
    { featureType: 'road', elementType: 'geometry', stylers: [{ color: '#232a38' }] },
    { featureType: 'road', elementType: 'geometry.stroke', stylers: [{ color: '#161b25' }] },
    { featureType: 'road.highway', elementType: 'geometry', stylers: [{ color: '#2e3647' }] },
    { featureType: 'road.highway', elementType: 'labels.icon', stylers: [{ visibility: 'off' }] },
    { featureType: 'road.local', elementType: 'labels.text.fill', stylers: [{ color: '#5d6578' }] },
    { featureType: 'transit', stylers: [{ visibility: 'off' }] },
    { featureType: 'water', elementType: 'geometry', stylers: [{ color: '#08182a' }] },
    { featureType: 'water', elementType: 'labels.text.fill', stylers: [{ color: '#3a5a7a' }] },
  ];

  // ---------- état ----------
  const saved = LS.get('state', {});
  const state = {
    points: Array.isArray(saved.points) ? saved.points.filter(p => p && isFinite(p.lat) && isFinite(p.lng)) : [],
    loop: !!saved.loop,
    mode: saved.mode === 'straight' ? 'straight' : 'roads',
    name: typeof saved.name === 'string' ? saved.name : '',
    theme: THEMES[saved.theme] ? saved.theme : 'neon',
    targetSec: saved.targetSec > 0 ? saved.targetSec : null,
    paceSec: saved.paceSec > 0 ? saved.paceSec : null,
    lastEdited: saved.lastEdited === 'pace' ? 'pace' : 'time',
    withMap: saved.withMap !== false,
  };
  let route = null;      // { path:[{lat,lng}], distance, legs:[m], source }
  let elevation = null;  // { gain, loss, min, max, profile:[m] }
  let map = null, geocoder = null, meOverlay = null, myPos = null;
  let markers = [], lines = [], kmMarkers = [];
  let routeToken = 0, routeTimer = null, warnedStraight = false;
  const history = [];

  const $ = s => document.querySelector(s);
  const $$ = s => Array.from(document.querySelectorAll(s));
  const uid = () => Math.random().toString(36).slice(2, 9);

  function save() {
    LS.set('state', {
      points: state.points, loop: state.loop, mode: state.mode, name: state.name, theme: state.theme,
      targetSec: state.targetSec, paceSec: state.paceSec, lastEdited: state.lastEdited, withMap: state.withMap,
    });
  }

  // ---------- formats ----------
  const nf2 = new Intl.NumberFormat('fr-FR', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  const nf1 = new Intl.NumberFormat('fr-FR', { minimumFractionDigits: 1, maximumFractionDigits: 1 });
  const pad = n => String(n).padStart(2, '0');
  function fmtDur(sec) {
    if (!(sec > 0)) return '—';
    sec = Math.round(sec);
    const h = Math.floor(sec / 3600), m = Math.floor(sec % 3600 / 60), s = sec % 60;
    return h ? `${h}h${pad(m)}'${pad(s)}` : `${m}'${pad(s)}`;
  }
  function fmtPace(sec) {
    if (!(sec > 0) || !isFinite(sec)) return '—';
    sec = Math.round(sec);
    return `${Math.floor(sec / 60)}:${pad(sec % 60)}`;
  }
  const km = () => (route ? route.distance / 1000 : 0);

  function vibe(pace) {
    if (!(pace > 0)) return { emoji: '🎯', label: 'Fixe un objectif' };
    if (pace <= 225) return { emoji: '🚀', label: 'Fusée' };
    if (pace <= 270) return { emoji: '⚡', label: 'Éclair' };
    if (pace <= 315) return { emoji: '🔥', label: 'Tempo' };
    if (pace <= 375) return { emoji: '😎', label: 'Footing' };
    if (pace <= 450) return { emoji: '🌴', label: 'Cool' };
    return { emoji: '🐢', label: 'Balade' };
  }

  // ---------- géométrie ----------
  function haversine(a, b) {
    const R = 6371008.8, r = Math.PI / 180;
    const dLat = (b.lat - a.lat) * r, dLng = (b.lng - a.lng) * r;
    const h = Math.sin(dLat / 2) ** 2 + Math.cos(a.lat * r) * Math.cos(b.lat * r) * Math.sin(dLng / 2) ** 2;
    return 2 * R * Math.asin(Math.min(1, Math.sqrt(h)));
  }
  function decodePolyline(str) {
    const out = [];
    let i = 0, lat = 0, lng = 0;
    while (i < str.length) {
      for (const k of [0, 1]) {
        let shift = 0, result = 0, b;
        do { b = str.charCodeAt(i++) - 63; result |= (b & 0x1f) << shift; shift += 5; } while (b >= 0x20);
        const d = (result & 1) ? ~(result >> 1) : (result >> 1);
        if (k === 0) lat += d; else lng += d;
      }
      out.push({ lat: lat / 1e5, lng: lng / 1e5 });
    }
    return out;
  }
  function downsample(path, max) {
    if (path.length <= max) return path;
    const step = (path.length - 1) / (max - 1), out = [];
    for (let i = 0; i < max; i++) out.push(path[Math.round(i * step)]);
    return out;
  }
  /** Points tous les `every` mètres le long du tracé. */
  function pointsEvery(path, every) {
    const out = [];
    let acc = 0, next = every;
    for (let i = 1; i < path.length; i++) {
      const seg = haversine(path[i - 1], path[i]);
      while (seg > 0 && acc + seg >= next) {
        const t = (next - acc) / seg;
        out.push({ lat: path[i - 1].lat + (path[i].lat - path[i - 1].lat) * t, lng: path[i - 1].lng + (path[i].lng - path[i - 1].lng) * t, km: next / 1000 });
        next += every;
      }
      acc += seg;
    }
    return out;
  }
  const ll = v => (typeof v === 'function' ? v() : v);
  const toLit = p => ({ lat: ll(p.lat), lng: ll(p.lng) });

  // ---------- rôles des points ----------
  function role(i, n = state.points.length) {
    if (i === 0) return 'start';
    if (!state.loop && i === n - 1) return 'finish';
    return 'via';
  }
  function roleLabel(i) {
    const r = role(i);
    if (r === 'start') return state.loop ? 'Départ & arrivée' : 'Départ';
    if (r === 'finish') return 'Arrivée';
    return `Étape ${i}`;
  }
  function stops() {
    const p = state.points;
    if (p.length < 2) return [];
    return state.loop ? [...p, p[0]] : p.slice();
  }

  // ---------- historique ----------
  function snapshot() {
    history.push(JSON.stringify({ points: state.points, loop: state.loop }));
    if (history.length > 50) history.shift();
  }
  function undo() {
    const last = history.pop();
    if (!last) return toast('Rien à annuler');
    const s = JSON.parse(last);
    state.points = s.points; state.loop = s.loop;
    $('#loop').checked = state.loop;
    refresh();
  }

  // ---------- actions sur les points ----------
  function addPoint(lat, lng, label = '') {
    if (state.points.length >= MAX_POINTS) return toast(`Maximum ${MAX_POINTS} points par parcours`);
    snapshot();
    const p = { id: uid(), lat, lng, label };
    state.points.push(p);
    if (!label) reverseGeocode(p);
    refresh();
    if (state.points.length === 1) toast('Départ posé 🟢 À toi de jouer !');
  }
  function setStart(lat, lng, label = '') {
    snapshot();
    if (state.points.length) {
      Object.assign(state.points[0], { lat, lng, label });
    } else {
      state.points.push({ id: uid(), lat, lng, label });
    }
    if (!label) reverseGeocode(state.points[0]);
    refresh();
  }
  function removePoint(id) {
    snapshot();
    state.points = state.points.filter(p => p.id !== id);
    refresh();
  }
  function movePoint(id, dir) {
    const i = state.points.findIndex(p => p.id === id), j = i + dir;
    if (i < 0 || j < 0 || j >= state.points.length) return;
    snapshot();
    [state.points[i], state.points[j]] = [state.points[j], state.points[i]];
    refresh();
  }
  function reverse() {
    if (state.points.length < 2) return;
    snapshot();
    if (state.loop) state.points = [state.points[0], ...state.points.slice(1).reverse()];
    else state.points.reverse();
    refresh();
    toast('Sens inversé ⇅');
  }
  function clearAll() {
    if (!state.points.length) return;
    snapshot();
    state.points = [];
    refresh();
    toast('Parcours effacé — ↶ pour annuler');
  }

  function refresh() {
    save();
    renderMarkers();
    renderPoints();
    updateHint();
    scheduleRoute();
  }

  // ---------- Google Maps : chargement ----------
  function apiKey() { return (CFG.googleMapsApiKey || LS.get('key', '') || '').trim(); }

  function loadMaps(key) {
    return new Promise((resolve, reject) => {
      window.__fouleeReady = resolve;
      window.gm_authFailure = () => {
        reject(new Error('auth'));
        onAuthFailure();
      };
      const s = document.createElement('script');
      s.src = 'https://maps.googleapis.com/maps/api/js?key=' + encodeURIComponent(key) +
        '&v=weekly&language=fr&libraries=geometry&loading=async&callback=__fouleeReady';
      s.async = true;
      s.onerror = () => reject(new Error('network'));
      document.head.appendChild(s);
    });
  }

  function onAuthFailure() {
    $('#map-empty').hidden = false;
    if (!CFG.googleMapsApiKey) LS.del('key');
    openKeyDialog('Google a refusé cette clé. Vérifie qu’elle est correcte, que Maps JavaScript API est activée et que ce site est autorisé.');
  }

  async function initMap() {
    const key = apiKey();
    if (!key) { $('#map-empty').hidden = false; openKeyDialog(); return; }
    try {
      await loadMaps(key);
      if (google.maps.importLibrary) {
        await Promise.all(['maps', 'marker', 'geocoding', 'elevation', 'routes', 'geometry']
          .map(l => google.maps.importLibrary(l).catch(() => null)));
      }
    } catch (e) {
      if (e.message === 'network') { $('#map-empty').hidden = false; toast('Impossible de joindre Google Maps — connexion ?'); }
      return;
    }
    $('#map-empty').hidden = true;

    const center = state.points[0] || CFG.defaultCenter;
    map = new google.maps.Map($('#map'), {
      center, zoom: CFG.defaultZoom, styles: DARK_STYLE, backgroundColor: '#07080c',
      disableDefaultUI: true, zoomControl: true, clickableIcons: false, gestureHandling: 'greedy',
      zoomControlOptions: { position: google.maps.ControlPosition.RIGHT_BOTTOM },
    });
    geocoder = new google.maps.Geocoder();
    map.addListener('click', e => addPoint(e.latLng.lat(), e.latLng.lng()));

    renderMarkers();
    scheduleRoute(true);
    startWatch();
    if (!state.points.length) locate(false);
  }

  // ---------- marqueurs ----------
  function iconFor(i) {
    const r = role(i), size = r === 'via' ? 30 : 38, c = size / 2;
    let svg;
    if (r === 'start') {
      svg = `<svg xmlns="http://www.w3.org/2000/svg" width="${size}" height="${size}"><circle cx="${c}" cy="${c}" r="${c - 2}" fill="#c6ff3d" stroke="#07080c" stroke-width="3"/>` +
        (state.loop ? `<path d="M${c + 6} ${c - 5}a7 7 0 1 0 1 7" fill="none" stroke="#07080c" stroke-width="3" stroke-linecap="round"/><path d="M${c + 3} ${c - 9}l4 4-5 2z" fill="#07080c"/>`
          : `<path d="M${c - 4} ${c - 7}l10 7-10 7z" fill="#07080c"/>`) + '</svg>';
    } else if (r === 'finish') {
      const s = 6, cells = [];
      for (let y = 0; y < size; y += s) for (let x = 0; x < size; x += s) if (((x + y) / s) % 2 === 0) cells.push(`<rect x="${x}" y="${y}" width="${s}" height="${s}"/>`);
      svg = `<svg xmlns="http://www.w3.org/2000/svg" width="${size}" height="${size}"><defs><clipPath id="c"><circle cx="${c}" cy="${c}" r="${c - 4}"/></clipPath></defs>` +
        `<circle cx="${c}" cy="${c}" r="${c - 2}" fill="#ff3d81"/><g clip-path="url(#c)"><rect width="${size}" height="${size}" fill="#fff"/><g fill="#111">${cells.join('')}</g></g></svg>`;
    } else {
      svg = `<svg xmlns="http://www.w3.org/2000/svg" width="${size}" height="${size}"><circle cx="${c}" cy="${c}" r="${c - 2}" fill="#8b5cf6" stroke="#07080c" stroke-width="3"/>` +
        `<text x="${c}" y="${c + 5}" text-anchor="middle" font-family="Arial,sans-serif" font-weight="700" font-size="14" fill="#fff">${i}</text></svg>`;
    }
    return {
      url: 'data:image/svg+xml;charset=UTF-8,' + encodeURIComponent(svg),
      scaledSize: new google.maps.Size(size, size),
      anchor: new google.maps.Point(c, c),
    };
  }

  function renderMarkers() {
    if (!map) return;
    markers.forEach(m => m.setMap(null));
    markers = state.points.map((p, i) => {
      const m = new google.maps.Marker({
        map, position: { lat: p.lat, lng: p.lng }, icon: iconFor(i), draggable: true,
        title: `${roleLabel(i)}${p.label ? ' — ' + p.label : ''}`, zIndex: role(i) === 'via' ? 10 : 20,
      });
      m.addListener('dragend', e => {
        snapshot();
        p.lat = e.latLng.lat(); p.lng = e.latLng.lng(); p.label = '';
        reverseGeocode(p);
        refresh();
      });
      return m;
    });
  }

  function drawRoute() {
    if (!map) return;
    lines.forEach(l => l.setMap(null));
    kmMarkers.forEach(m => m.setMap(null));
    lines = []; kmMarkers = [];
    if (!route) return;
    const t = THEMES[state.theme];
    const dashed = route.source === 'straight';
    lines.push(new google.maps.Polyline({ map, path: route.path, strokeColor: t.b, strokeOpacity: 0.25, strokeWeight: 14, clickable: false, zIndex: 1 }));
    lines.push(new google.maps.Polyline({
      map, path: route.path, clickable: false, zIndex: 2,
      strokeColor: t.a, strokeOpacity: dashed ? 0 : 1, strokeWeight: 5,
      icons: [
        ...(dashed ? [{ icon: { path: 'M 0,-1 0,1', strokeOpacity: 1, strokeColor: t.a, strokeWeight: 4, scale: 3 }, offset: '0', repeat: '14px' }] : []),
        { icon: { path: google.maps.SymbolPath.FORWARD_OPEN_ARROW, scale: 2.6, strokeColor: '#ffffff', strokeWeight: 2, strokeOpacity: 0.9 }, offset: '60px', repeat: '140px' },
      ],
    }));
    const every = [1000, 2000, 5000, 10000, 20000].find(x => route.distance / x <= 25) || 50000;
    kmMarkers = pointsEvery(route.path, every).map(k => new google.maps.Marker({
      map, position: k, clickable: false, zIndex: 5,
      icon: {
        url: 'data:image/svg+xml;charset=UTF-8,' + encodeURIComponent(
          `<svg xmlns="http://www.w3.org/2000/svg" width="26" height="26"><circle cx="13" cy="13" r="11" fill="#07080c" stroke="${t.a}" stroke-width="2"/>` +
          `<text x="13" y="17.5" text-anchor="middle" font-family="Arial,sans-serif" font-weight="700" font-size="${k.km >= 10 ? 10 : 12}" fill="#fff">${Math.round(k.km)}</text></svg>`),
        scaledSize: new google.maps.Size(26, 26), anchor: new google.maps.Point(13, 13),
      },
    }));
  }

  function fitAll() {
    if (!map) return;
    const pts = route ? route.path : state.points;
    if (!pts.length) { if (myPos) map.panTo(myPos); return; }
    if (pts.length === 1) { map.panTo(pts[0]); map.setZoom(16); return; }
    const b = new google.maps.LatLngBounds();
    pts.forEach(p => b.extend(p));
    const mobile = window.innerWidth <= 760;
    const panelW = $('#panel').offsetWidth;
    map.fitBounds(b, mobile
      ? { top: 70, left: 30, right: 70, bottom: $('#panel').offsetHeight + 30 }
      : { top: 70, left: panelW + 50, right: 90, bottom: 50 });
  }

  // ---------- itinéraire ----------
  function scheduleRoute(fitAfter = false) {
    clearTimeout(routeTimer);
    routeTimer = setTimeout(() => computeRoute(fitAfter), 250);
  }

  async function computeRoute(fitAfter) {
    const s = stops();
    const token = ++routeToken;
    if (s.length < 2) {
      route = null; elevation = null;
      drawRoute(); renderStats();
      return;
    }
    setBusy(true);
    let r = null, failed = false;
    if (state.mode === 'roads' && map) {
      try { r = await routesApi(s); }
      catch (e1) {
        console.warn('Routes API :', e1.message);
        try { r = await directionsApi(s); }
        catch (e2) { console.warn('DirectionsService :', e2.message); failed = true; }
      }
    }
    if (!r) r = straightRoute(s);
    if (token !== routeToken) return;
    route = r; elevation = null;
    setBusy(false);
    drawRoute(); renderStats();
    if (fitAfter) fitAll();
    if (failed && !warnedStraight) {
      warnedStraight = true;
      toast('Itinéraire piéton indisponible (active Routes API dans Google Cloud) — tracé en ligne droite.', 6000);
    }
    fetchElevation(token);
  }

  async function routesApi(s) {
    const wp = p => ({ location: { latLng: { latitude: p.lat, longitude: p.lng } } });
    const res = await fetch('https://routes.googleapis.com/directions/v2:computeRoutes', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-Goog-Api-Key': apiKey(),
        'X-Goog-FieldMask': 'routes.distanceMeters,routes.polyline.encodedPolyline,routes.legs.distanceMeters',
      },
      body: JSON.stringify({
        origin: wp(s[0]), destination: wp(s[s.length - 1]), intermediates: s.slice(1, -1).map(wp),
        travelMode: 'WALK', languageCode: 'fr', units: 'METRIC',
      }),
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.error?.message || 'HTTP ' + res.status);
    const r = data.routes?.[0];
    if (!r?.polyline?.encodedPolyline) throw new Error('aucun itinéraire');
    const legs = (r.legs || []).map(l => l.distanceMeters || 0);
    return { path: decodePolyline(r.polyline.encodedPolyline), distance: r.distanceMeters || legs.reduce((a, b) => a + b, 0), legs, source: 'roads' };
  }

  async function directionsApi(s) {
    const svc = new google.maps.DirectionsService();
    const res = await svc.route({
      origin: s[0], destination: s[s.length - 1],
      waypoints: s.slice(1, -1).map(p => ({ location: { lat: p.lat, lng: p.lng }, stopover: true })),
      travelMode: google.maps.TravelMode.WALKING,
    });
    const rt = res.routes[0], path = [];
    rt.legs.forEach(l => l.steps.forEach(st => (st.path || st.lat_lngs || []).forEach(p => path.push(toLit(p)))));
    const legs = rt.legs.map(l => l.distance?.value || 0);
    return { path: path.length ? path : rt.overview_path.map(toLit), distance: legs.reduce((a, b) => a + b, 0), legs, source: 'roads' };
  }

  function straightRoute(s) {
    const legs = [];
    for (let i = 1; i < s.length; i++) legs.push(haversine(s[i - 1], s[i]));
    return { path: s.map(p => ({ lat: p.lat, lng: p.lng })), distance: legs.reduce((a, b) => a + b, 0), legs, source: 'straight' };
  }

  async function fetchElevation(token) {
    if (!map || !route || !google.maps.ElevationService) return;
    try {
      const samples = Math.max(16, Math.min(256, Math.round(route.distance / 40)));
      const res = await new google.maps.ElevationService().getElevationAlongPath({ path: downsample(route.path, 180), samples });
      if (token !== routeToken) return;
      const prof = (res.results || res).map(r => r.elevation).filter(Number.isFinite);
      if (prof.length < 2) return;
      // dénivelé avec hystérésis de 2 m pour ignorer le bruit du modèle de terrain
      let gain = 0, loss = 0, ref = prof[0];
      for (const e of prof) {
        if (e - ref >= 2) { gain += e - ref; ref = e; } else if (ref - e >= 2) { loss += ref - e; ref = e; }
      }
      elevation = { gain, loss, min: Math.min(...prof), max: Math.max(...prof), profile: prof };
      renderStats();
    } catch (e) {
      console.warn('Elevation :', e.message);
    }
  }

  // ---------- recherche & adresses ----------
  async function search(q) {
    q = q.trim();
    const box = $('#search-results');
    if (!q) { box.hidden = true; return; }
    if (!map) return toast('Configure d’abord ta clé Google Maps');
    box.hidden = false;
    box.innerHTML = '<li class="muted small">Recherche…</li>';
    let results = [];
    try { results = await placesSearch(q); } catch (e) { console.warn('Places :', e.message); }
    if (!results.length) { try { results = await geocodeSearch(q); } catch (e) { console.warn('Geocoder :', e.message); } }
    if (!results.length) { box.innerHTML = '<li class="muted small">Aucun résultat 🤷</li>'; return; }
    box.innerHTML = '';
    results.slice(0, 6).forEach(r => {
      const li = document.createElement('li');
      li.innerHTML = '<div class="r-main"><b></b><small></small></div><button class="btn btn--ghost r-add" type="button">＋ Ajouter</button>';
      li.querySelector('b').textContent = r.name;
      li.querySelector('small').textContent = r.address || '';
      li.querySelector('.r-main').onclick = () => { map.panTo(r); map.setZoom(16); box.hidden = true; };
      li.querySelector('.r-add').onclick = () => { addPoint(r.lat, r.lng, r.name); map.panTo(r); box.hidden = true; $('#search-input').value = ''; };
      box.appendChild(li);
    });
  }

  async function placesSearch(q) {
    const c = map.getCenter();
    const res = await fetch('https://places.googleapis.com/v1/places:searchText', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-Goog-Api-Key': apiKey(),
        'X-Goog-FieldMask': 'places.displayName,places.formattedAddress,places.location',
      },
      body: JSON.stringify({
        textQuery: q, languageCode: 'fr', maxResultCount: 6,
        locationBias: { circle: { center: { latitude: c.lat(), longitude: c.lng() }, radius: 30000 } },
      }),
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.error?.message || 'HTTP ' + res.status);
    return (data.places || []).map(p => ({
      name: p.displayName?.text || p.formattedAddress, address: p.formattedAddress,
      lat: p.location.latitude, lng: p.location.longitude,
    }));
  }

  async function geocodeSearch(q) {
    const { results } = await geocoder.geocode({ address: q, bounds: map.getBounds() || undefined });
    return results.map(r => {
      const parts = r.formatted_address.split(',');
      return { name: parts[0], address: parts.slice(1).join(',').trim(), ...toLit(r.geometry.location) };
    });
  }

  async function reverseGeocode(p) {
    const fallback = `${p.lat.toFixed(4)}, ${p.lng.toFixed(4)}`;
    if (!geocoder) { p.label = p.label || fallback; return; }
    try {
      const { results } = await geocoder.geocode({ location: { lat: p.lat, lng: p.lng } });
      const best = results.find(r => !r.types.includes('plus_code')) || results[0];
      p.label = best ? best.formatted_address.split(',').slice(0, 2).join(',').trim() : fallback;
    } catch {
      p.label = fallback;
    }
    if (state.points.includes(p)) { save(); renderPoints(); renderMarkers(); }
  }

  // ---------- géolocalisation ----------
  function makeMeOverlay() {
    class Me extends google.maps.OverlayView {
      constructor() { super(); this.pos = null; this.div = document.createElement('div'); this.div.className = 'me-dot'; }
      onAdd() { this.getPanes().overlayLayer.appendChild(this.div); }
      draw() {
        const proj = this.getProjection();
        if (!proj || !this.pos) return;
        const px = proj.fromLatLngToDivPixel(new google.maps.LatLng(this.pos.lat, this.pos.lng));
        if (px) { this.div.style.left = px.x + 'px'; this.div.style.top = px.y + 'px'; }
      }
      onRemove() { this.div.remove(); }
      set(pos) { this.pos = pos; this.draw(); }
    }
    return new Me();
  }
  function showMe() {
    if (!map || !myPos) return;
    if (!meOverlay) { meOverlay = makeMeOverlay(); meOverlay.setMap(map); }
    meOverlay.set(myPos);
  }
  function startWatch() {
    if (!navigator.geolocation) return;
    navigator.geolocation.watchPosition(
      pos => { myPos = { lat: pos.coords.latitude, lng: pos.coords.longitude }; showMe(); },
      () => {},
      { enableHighAccuracy: true, maximumAge: 15000, timeout: 30000 }
    );
  }
  function locate(asStart) {
    if (!navigator.geolocation) return toast('Ton appareil ne donne pas sa position');
    if (asStart) toast('📡 Recherche de ta position…', 2500);
    navigator.geolocation.getCurrentPosition(
      pos => {
        myPos = { lat: pos.coords.latitude, lng: pos.coords.longitude };
        showMe();
        if (map) { map.panTo(myPos); if (map.getZoom() < 15) map.setZoom(15); }
        if (asStart) { setStart(myPos.lat, myPos.lng); toast('Départ = ta position 📍'); }
      },
      err => {
        const msg = err.code === 1 ? 'Localisation refusée — autorise-la dans ton navigateur, ou tape sur la carte.'
          : 'Position introuvable pour le moment — tape sur la carte.';
        if (asStart || err.code === 1) toast(msg, 5000);
      },
      { enableHighAccuracy: true, timeout: 15000, maximumAge: 30000 }
    );
  }

  // ---------- rendu du panneau ----------
  function renderPoints() {
    const ol = $('#points');
    ol.innerHTML = '';
    $('#points-empty').hidden = state.points.length > 0;
    const legs = route && route.legs.length === stops().length - 1 ? route.legs : null;
    state.points.forEach((p, i) => {
      if (i > 0) {
        const leg = document.createElement('li');
        leg.className = 'pt__leg';
        leg.textContent = legs ? `${nf2.format(legs[i - 1] / 1000)} km` : '';
        ol.appendChild(leg);
      }
      const r = role(i);
      const li = document.createElement('li');
      li.className = `pt pt--${r}`;
      li.innerHTML = `<button class="pt__badge" type="button" title="Centrer la carte"></button>
        <div class="pt__body"><small></small><input class="pt__name" type="text" maxlength="60"></div>
        <div class="pt__acts">
          <button type="button" data-m="-1" title="Monter">↑</button>
          <button type="button" data-m="1" title="Descendre">↓</button>
          <button type="button" data-del title="Supprimer">✕</button>
        </div>`;
      li.querySelector('.pt__badge').textContent = r === 'start' ? '▶' : r === 'finish' ? '' : String(i);
      li.querySelector('small').textContent = roleLabel(i);
      const input = li.querySelector('.pt__name');
      input.value = p.label || '';
      input.placeholder = 'Localisation…';
      input.addEventListener('change', () => { p.label = input.value.trim(); save(); renderMarkers(); });
      li.querySelector('.pt__badge').onclick = () => map && map.panTo(p);
      li.querySelector('[data-m="-1"]').disabled = i === 0;
      li.querySelector('[data-m="1"]').disabled = i === state.points.length - 1;
      li.querySelectorAll('[data-m]').forEach(b => (b.onclick = () => movePoint(p.id, +b.dataset.m)));
      li.querySelector('[data-del]').onclick = () => removePoint(p.id);
      ol.appendChild(li);
    });
    if (state.loop && state.points.length >= 2) {
      const leg = document.createElement('li');
      leg.className = 'pt__leg';
      leg.textContent = legs ? `${nf2.format(legs[legs.length - 1] / 1000)} km · retour au départ ↺` : 'retour au départ ↺';
      ol.appendChild(leg);
    }
  }

  function renderStats() {
    const d = km();
    $('#st-dist').textContent = nf2.format(d);
    $('#sum-dist').textContent = nf2.format(d) + ' km';
    $('#st-stops').textContent = Math.max(0, state.points.length - (state.loop ? 1 : 2));
    const src = $('#st-source');
    src.hidden = !route;
    if (route) src.textContent = route.source === 'roads' ? '🛣️ chemins piétons' : '📏 à vol d’oiseau';
    $('#st-gain').textContent = elevation ? Math.round(elevation.gain) : '—';
    renderProfile();
    renderPoints();
    updatePace();
  }

  function renderProfile() {
    const svg = $('#st-profile');
    if (!elevation) { svg.hidden = true; return; }
    const prof = elevation.profile, W = 300, H = 60;
    const lo = elevation.min, span = Math.max(10, elevation.max - lo);
    const pts = prof.map((e, i) => `${(i / (prof.length - 1) * W).toFixed(1)},${(H - 4 - (e - lo) / span * (H - 10)).toFixed(1)}`);
    const t = THEMES[state.theme];
    svg.innerHTML = `<defs><linearGradient id="pf" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="${t.a}" stop-opacity=".45"/><stop offset="1" stop-color="${t.a}" stop-opacity="0"/></linearGradient>
      <linearGradient id="ps" x1="0" x2="1"><stop offset="0" stop-color="${t.a}"/><stop offset="1" stop-color="${t.b}"/></linearGradient></defs>
      <polygon points="0,${H} ${pts.join(' ')} ${W},${H}" fill="url(#pf)"/>
      <polyline points="${pts.join(' ')}" fill="none" stroke="url(#ps)" stroke-width="2" vector-effect="non-scaling-stroke"/>`;
    svg.hidden = false;
  }

  // ---------- allure ----------
  const timeInputs = ['#t-h', '#t-m', '#t-s'].map($);
  const paceInputs = ['#p-m', '#p-s'].map($);
  const readNum = el => Math.max(0, parseInt(el.value, 10) || 0);

  function updatePace() {
    const d = km();
    if (d > 0) {
      if (state.lastEdited === 'time' && state.targetSec) state.paceSec = state.targetSec / d;
      else if (state.lastEdited === 'pace' && state.paceSec) state.targetSec = state.paceSec * d;
    }
    save();
    const active = document.activeElement;
    if (!timeInputs.includes(active)) {
      const t = state.targetSec ? Math.round(state.targetSec) : 0;
      timeInputs[0].value = t ? Math.floor(t / 3600) : '';
      timeInputs[1].value = t ? pad(Math.floor(t % 3600 / 60)) : '';
      timeInputs[2].value = t ? pad(t % 60) : '';
    }
    if (!paceInputs.includes(active)) {
      const p = state.paceSec ? Math.round(state.paceSec) : 0;
      paceInputs[0].value = p ? Math.floor(p / 60) : '';
      paceInputs[1].value = p ? pad(p % 60) : '';
    }
    const pace = state.paceSec, total = d > 0 ? state.targetSec : null;
    const v = vibe(pace);
    $('#vibe').textContent = `${v.emoji} ${v.label}`;
    $('#speed').textContent = pace ? nf1.format(3600 / pace) + ' km/h' : '—';
    $('#half').textContent = total ? fmtDur(total / 2) : '—';
    $('#eta').textContent = total ? new Date(Date.now() + total * 1000).toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' }) : '—';
    $('#sum-pace').textContent = pace ? `${fmtPace(pace)} /km · ${fmtDur(total)}` : 'allure —';
    $$('#pace-presets .chip').forEach(c => c.classList.toggle('is-on', pace && Math.abs(+c.dataset.pace - pace) < 1));

    const ol = $('#splits');
    ol.innerHTML = '';
    if (pace && d > 0) {
      const full = Math.floor(d);
      for (let i = 1; i <= Math.min(full, 200); i++) ol.insertAdjacentHTML('beforeend', `<li><span>km ${i}</span><b>${fmtDur(i * pace)}</b></li>`);
      if (d - full > 0.01) ol.insertAdjacentHTML('beforeend', `<li><span>🏁 ${nf2.format(d)}</span><b>${fmtDur(d * pace)}</b></li>`);
    } else {
      ol.innerHTML = '<li><span>Trace un parcours et fixe un objectif</span></li>';
    }
  }

  timeInputs.forEach(el => el.addEventListener('input', () => {
    const t = readNum(timeInputs[0]) * 3600 + readNum(timeInputs[1]) * 60 + readNum(timeInputs[2]);
    state.targetSec = t || null;
    state.lastEdited = 'time';
    if (!t) state.paceSec = null;
    updatePace();
  }));
  paceInputs.forEach(el => el.addEventListener('input', () => {
    const p = readNum(paceInputs[0]) * 60 + readNum(paceInputs[1]);
    state.paceSec = p || null;
    state.lastEdited = 'pace';
    if (!p) state.targetSec = null;
    updatePace();
  }));
  [...timeInputs, ...paceInputs].forEach(el => el.addEventListener('blur', () => setTimeout(updatePace)));

  // ---------- export PNG / GPX ----------
  function posterData() {
    const s = stops();
    return {
      name: state.name.trim() || defaultName(),
      date: new Date(),
      path: route ? route.path : [],
      distance: route ? route.distance : 0,
      straight: route?.source === 'straight',
      loop: state.loop,
      points: state.points.map((p, i) => ({ lat: p.lat, lng: p.lng, label: p.label, role: role(i), index: i })),
      targetSec: s.length ? state.targetSec : null,
      paceSec: state.paceSec,
      vibe: vibe(state.paceSec),
      elevation,
    };
  }
  function defaultName() {
    const h = new Date().getHours();
    const moment = h < 11 ? 'du matin' : h < 17 ? 'de l’après-midi' : 'du soir';
    return `Run ${moment}`;
  }
  const slug = s => s.normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '') || 'run';

  async function renderPoster() {
    const note = $('#export-note');
    note.textContent = '';
    const res = await window.FouleePoster.render($('#poster'), posterData(), {
      theme: THEMES[state.theme], withMap: state.withMap && !!apiKey(), apiKey: apiKey(),
    });
    if (state.withMap && !res.mapUsed) note.textContent = 'Fond de carte indisponible (active Maps Static API) — version stylisée.';
  }

  function openExport() {
    if (!route) return toast('Pose au moins un départ et une arrivée 🏁');
    $('#with-map').checked = state.withMap;
    renderThemes('#themes');
    $('#share-btn').hidden = !(navigator.canShare && window.File);
    $('#export-dialog').showModal();
    renderPoster();
  }

  function posterBlob() {
    return new Promise(res => $('#poster').toBlob(res, 'image/png'));
  }
  function fileName(ext) {
    const d = posterData();
    return `foulee-${slug(d.name)}-${(d.distance / 1000).toFixed(1)}km.${ext}`;
  }
  async function download(blob, name) {
    const url = URL.createObjectURL(blob);
    const a = Object.assign(document.createElement('a'), { href: url, download: name });
    document.body.appendChild(a); a.click(); a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 2000);
  }
  async function downloadPng() {
    const blob = await posterBlob();
    if (!blob) return toast('Export impossible 😕');
    download(blob, fileName('png'));
    toast('Affiche téléchargée 🎉');
  }
  async function sharePng() {
    const blob = await posterBlob();
    const file = new File([blob], fileName('png'), { type: 'image/png' });
    if (!navigator.canShare?.({ files: [file] })) return downloadPng();
    try { await navigator.share({ files: [file], title: posterData().name }); } catch { /* annulé */ }
  }

  function exportGpx() {
    if (!route) return toast('Pas encore de parcours à exporter');
    const esc = s => String(s).replace(/[<>&"']/g, c => ({ '<': '&lt;', '>': '&gt;', '&': '&amp;', '"': '&quot;', "'": '&apos;' }[c]));
    const name = esc(state.name.trim() || defaultName());
    const wpts = state.points.map((p, i) =>
      `  <wpt lat="${p.lat.toFixed(6)}" lon="${p.lng.toFixed(6)}"><name>${esc(roleLabel(i))}</name>${p.label ? `<desc>${esc(p.label)}</desc>` : ''}</wpt>`).join('\n');
    const trk = route.path.map(p => `      <trkpt lat="${p.lat.toFixed(6)}" lon="${p.lng.toFixed(6)}"/>`).join('\n');
    const gpx = `<?xml version="1.0" encoding="UTF-8"?>
<gpx version="1.1" creator="Foulée" xmlns="http://www.topografix.com/GPX/1/1">
  <metadata><name>${name}</name><time>${new Date().toISOString()}</time></metadata>
${wpts}
  <trk>
    <name>${name}</name>
    <type>running</type>
    <trkseg>
${trk}
    </trkseg>
  </trk>
</gpx>
`;
    download(new Blob([gpx], { type: 'application/gpx+xml' }), fileName('gpx'));
    toast('GPX téléchargé ⌚');
  }

  // ---------- thèmes ----------
  function applyTheme() {
    const t = THEMES[state.theme];
    document.documentElement.style.setProperty('--a', t.a);
    document.documentElement.style.setProperty('--b', t.b);
  }
  function renderThemes(sel) {
    const box = $(sel);
    box.innerHTML = '';
    Object.entries(THEMES).forEach(([id, t]) => {
      const b = document.createElement('button');
      b.type = 'button';
      b.className = 'chip' + (id === state.theme ? ' is-on' : '');
      b.innerHTML = `<span class="chip__swatch" style="background:linear-gradient(135deg,${t.a},${t.b})"></span>${t.name}`;
      b.onclick = () => {
        state.theme = id; save(); applyTheme(); drawRoute(); renderProfile();
        renderThemes(sel);
        if ($('#export-dialog').open) renderPoster();
      };
      box.appendChild(b);
    });
  }

  // ---------- divers UI ----------
  let toastTimer;
  function toast(msg, ms = 3000) {
    const t = $('#toast');
    t.textContent = msg;
    t.classList.add('is-on');
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => t.classList.remove('is-on'), ms);
  }
  function setBusy(on) { $('#busy').hidden = !on; }
  function updateHint() {
    const n = state.points.length, h = $('#hint');
    h.textContent = n === 0 ? '👆 Tape sur la carte pour poser ton départ — ou 📍 pour partir d’ici'
      : n === 1 ? (state.loop ? '👆 Ajoute des étapes : la boucle te ramènera au départ ↺' : '👆 Tape pour ajouter ton arrivée 🏁')
        : '✋ Glisse les repères pour ajuster · tape pour prolonger';
  }
  function openKeyDialog(error) {
    const d = $('#key-dialog');
    $('#key-input').value = LS.get('key', '') || CFG.googleMapsApiKey || '';
    $('#key-error').hidden = !error;
    $('#key-error').textContent = error || '';
    if (!d.open) d.showModal();
  }

  function bindUI() {
    $('#run-name').value = state.name;
    $('#run-name').addEventListener('input', e => { state.name = e.target.value; save(); });
    $('#loop').checked = state.loop;
    $('#loop').addEventListener('change', e => { snapshot(); state.loop = e.target.checked; refresh(); });
    const syncSeg = () => $$('.seg__btn').forEach(b => { const on = b.dataset.mode === state.mode; b.classList.toggle('is-on', on); b.setAttribute('aria-checked', on); });
    $$('.seg__btn').forEach(b => (b.onclick = () => { state.mode = b.dataset.mode; syncSeg(); save(); scheduleRoute(); }));
    syncSeg();

    PRESETS.forEach(p => {
      const b = document.createElement('button');
      b.type = 'button'; b.className = 'chip'; b.textContent = p.label; b.dataset.pace = p.pace;
      b.onclick = () => { state.paceSec = p.pace; state.lastEdited = 'pace'; if (!km()) state.targetSec = null; updatePace(); };
      $('#pace-presets').appendChild(b);
    });

    $('#search').addEventListener('submit', e => { e.preventDefault(); search($('#search-input').value); });
    $('#search-input').addEventListener('input', e => { if (!e.target.value) $('#search-results').hidden = true; });

    $('#key-form').addEventListener('submit', () => {
      const k = $('#key-input').value.trim();
      if (!k) return;
      LS.set('key', k);
      location.reload();
    });
    $('#with-map').addEventListener('change', e => { state.withMap = e.target.checked; save(); renderPoster(); });
    $('#export-dialog').addEventListener('click', e => { if (e.target === e.currentTarget) e.currentTarget.close(); });

    const actions = {
      'open-key': () => openKeyDialog(),
      'forget-key': () => { LS.del('key'); $('#key-input').value = ''; toast('Clé oubliée'); },
      locate: () => locate(false),
      'start-here': () => locate(true),
      fit: fitAll, undo, clear: clearAll, reverse,
      'toggle-sheet': () => $('#panel').classList.toggle('is-collapsed'),
      'open-export': openExport,
      'close-export': () => $('#export-dialog').close(),
      download: downloadPng, share: sharePng, gpx: exportGpx,
    };
    document.addEventListener('click', e => {
      const el = e.target.closest('[data-action]');
      if (el && actions[el.dataset.action]) { e.preventDefault(); actions[el.dataset.action](); }
    });
    document.addEventListener('keydown', e => {
      if ((e.ctrlKey || e.metaKey) && e.key === 'z' && !/INPUT|TEXTAREA/.test(document.activeElement.tagName)) { e.preventDefault(); undo(); }
    });
  }

  // ---------- démarrage ----------
  applyTheme();
  bindUI();
  renderPoints();
  renderStats();
  updateHint();
  initMap();

  // accès pour le débogage dans la console
  window.Foulee = { state, get route() { return route; }, addPoint, fitAll };
})();
