/*
 * Affiche PNG d'un parcours (1080 × 1350, format portrait des réseaux).
 *
 * Le tracé est dessiné par nous, en projection Web Mercator. Avec le fond de
 * carte, l'image vient de Maps Static API, demandée avec le même centre et le
 * même zoom que notre projection : le tracé tombe pile sur les rues.
 */
window.FouleePoster = (() => {
  'use strict';

  const W = 1080, H = 1350;
  const MAP = { x: 40, y: 236, w: 1000, h: 640, r: 36 };
  const DISPLAY = '"Unbounded", "Space Grotesk", system-ui, sans-serif';
  const BODY = '"Space Grotesk", system-ui, sans-serif';
  const imgCache = new Map();

  const nf2 = new Intl.NumberFormat('fr-FR', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  const pad = n => String(n).padStart(2, '0');
  const fmtDur = s => {
    if (!(s > 0)) return '—';
    s = Math.round(s);
    const h = Math.floor(s / 3600), m = Math.floor(s % 3600 / 60), x = s % 60;
    return h ? `${h}:${pad(m)}:${pad(x)}` : `${m}:${pad(x)}`;
  };
  const fmtPace = s => (s > 0 ? `${Math.floor(Math.round(s) / 60)}:${pad(Math.round(s) % 60)}` : '—');

  // ---------- projection ----------
  const mx = lng => (lng + 180) / 360;
  const my = lat => { const s = Math.sin(lat * Math.PI / 180); return 0.5 - Math.log((1 + s) / (1 - s)) / (4 * Math.PI); };
  const unLat = y => Math.atan(Math.sinh(Math.PI * (1 - 2 * y))) * 180 / Math.PI;
  const unLng = x => x * 360 - 180;

  function frame(path, w, h, padFrac) {
    let x0 = Infinity, y0 = Infinity, x1 = -Infinity, y1 = -Infinity;
    path.forEach(p => { const x = mx(p.lng), y = my(p.lat); x0 = Math.min(x0, x); x1 = Math.max(x1, x); y0 = Math.min(y0, y); y1 = Math.max(y1, y); });
    const dx = Math.max(x1 - x0, 1e-7), dy = Math.max(y1 - y0, 1e-7);
    return { cx: (x0 + x1) / 2, cy: (y0 + y1) / 2, dx, dy, fit: Math.min(w * (1 - 2 * padFrac) / dx, h * (1 - 2 * padFrac) / dy) };
  }

  // ---------- fond de carte (Maps Static API) ----------
  const STATIC_STYLE = [
    'element:geometry|color:0x12161f',
    'element:labels.text.fill|color:0x6b7385',
    'element:labels.text.stroke|color:0x0b0d12',
    'element:labels.icon|visibility:off',
    'feature:administrative|element:geometry|visibility:off',
    'feature:poi|visibility:off',
    'feature:poi.park|element:geometry|visibility:on|color:0x102419',
    'feature:road|element:geometry|color:0x252c3b',
    'feature:road.highway|element:geometry|color:0x30384a',
    'feature:transit|visibility:off',
    'feature:water|element:geometry|color:0x0a1724',
  ];

  function staticMap(path, key) {
    const lw = MAP.w / 2, lh = MAP.h / 2; // taille logique ; scale=2 donne la taille réelle
    const f = frame(path, lw, lh, 0.14);
    const zoom = Math.max(1, Math.min(18, Math.floor(Math.log2(f.fit / 256))));
    // le zoom est entier : on agrandit un peu l'image (≤ 1,6×) pour que le tracé remplisse le cadre
    const up = Math.max(1, Math.min(1.6, f.fit / (256 * 2 ** zoom)));
    const url = 'https://maps.googleapis.com/maps/api/staticmap?' +
      `center=${unLat(f.cy).toFixed(6)},${unLng(f.cx).toFixed(6)}&zoom=${zoom}&size=${lw}x${lh}&scale=2&maptype=roadmap&language=fr` +
      STATIC_STYLE.map(s => '&style=' + encodeURIComponent(s)).join('') + '&key=' + encodeURIComponent(key);
    return { url, up, project: { cx: f.cx, cy: f.cy, k: 256 * 2 ** zoom * 2 * up } };
  }

  function loadImage(url, timeout = 10000) {
    if (imgCache.has(url)) return imgCache.get(url);
    const p = new Promise(resolve => {
      const img = new Image();
      img.crossOrigin = 'anonymous';
      const t = setTimeout(() => resolve(null), timeout);
      img.onload = () => { clearTimeout(t); resolve(img.naturalWidth > 1 ? img : null); };
      img.onerror = () => { clearTimeout(t); resolve(null); };
      img.src = url;
    });
    imgCache.set(url, p);
    p.then(img => { if (!img) imgCache.delete(url); });
    return p;
  }

  async function fontsReady() {
    if (!document.fonts?.load) return;
    const wait = Promise.all([
      document.fonts.load(`800 72px ${DISPLAY}`), document.fonts.load(`600 40px ${DISPLAY}`),
      document.fonts.load(`700 24px ${BODY}`), document.fonts.load(`500 24px ${BODY}`),
    ]).catch(() => {});
    await Promise.race([wait, new Promise(r => setTimeout(r, 2500))]);
  }

  // ---------- utilitaires de dessin ----------
  function rr(ctx, x, y, w, h, r) {
    ctx.beginPath();
    ctx.moveTo(x + r, y);
    ctx.arcTo(x + w, y, x + w, y + h, r);
    ctx.arcTo(x + w, y + h, x, y + h, r);
    ctx.arcTo(x, y + h, x, y, r);
    ctx.arcTo(x, y, x + w, y, r);
    ctx.closePath();
  }
  function fitText(ctx, text, maxW, size, weight, family, min = 18) {
    let s = size;
    do { ctx.font = `${weight} ${s}px ${family}`; } while (ctx.measureText(text).width > maxW && (s -= 2) >= min);
    if (ctx.measureText(text).width <= maxW) return text;
    let t = text;
    while (t.length > 1 && ctx.measureText(t + '…').width > maxW) t = t.slice(0, -1);
    return t + '…';
  }
  function hexA(hex, a) {
    const n = parseInt(hex.slice(1), 16);
    return `rgba(${n >> 16 & 255},${n >> 8 & 255},${n & 255},${a})`;
  }

  // ---------- rendu ----------
  async function render(canvas, d, opts) {
    const t = opts.theme;
    canvas.width = W; canvas.height = H;
    const ctx = canvas.getContext('2d');
    await fontsReady();

    let bg = null, up = 1, proj;
    if (opts.withMap && d.path.length > 1) {
      const sm = staticMap(d.path, opts.apiKey);
      bg = await loadImage(sm.url);
      if (bg) { proj = sm.project; up = sm.up; }
    }
    if (!proj) {
      const f = frame(d.path.length ? d.path : d.points, MAP.w, MAP.h, 0.12);
      proj = { cx: f.cx, cy: f.cy, k: f.fit };
    }
    const P = p => [MAP.x + MAP.w / 2 + (mx(p.lng) - proj.cx) * proj.k, MAP.y + MAP.h / 2 + (my(p.lat) - proj.cy) * proj.k];

    // fond
    const g = ctx.createLinearGradient(0, 0, 0, H);
    g.addColorStop(0, '#0a0c12'); g.addColorStop(1, '#05060a');
    ctx.fillStyle = g; ctx.fillRect(0, 0, W, H);
    [[880, 120, 520, t.b, 0.22], [120, 1180, 560, t.a, 0.18], [980, 1240, 380, t.b, 0.10]].forEach(([x, y, r, c, a]) => {
      const rg = ctx.createRadialGradient(x, y, 0, x, y, r);
      rg.addColorStop(0, hexA(c, a)); rg.addColorStop(1, hexA(c, 0));
      ctx.fillStyle = rg; ctx.fillRect(0, 0, W, H);
    });
    ctx.fillStyle = 'rgba(255,255,255,0.05)';
    for (let y = 18; y < H; y += 36) for (let x = 18; x < W; x += 36) ctx.fillRect(x, y, 2, 2);

    // en-tête
    ctx.textBaseline = 'alphabetic';
    ctx.fillStyle = t.a;
    ctx.font = `600 22px ${DISPLAY}`;
    ctx.fillText('FOULÉE', 44, 74);
    const brandW = ctx.measureText('FOULÉE').width;
    ctx.fillStyle = '#8a93a6';
    ctx.font = `500 22px ${BODY}`;
    ctx.fillText('  ·  trace · cours · répète', 44 + brandW, 74);
    ctx.textAlign = 'right';
    ctx.fillText(d.date.toLocaleDateString('fr-FR', { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' }), W - 44, 74);
    ctx.textAlign = 'left';

    const title = fitText(ctx, d.name, W - 88, 70, 800, DISPLAY, 36);
    const tg = ctx.createLinearGradient(44, 0, 44 + ctx.measureText(title).width, 0);
    tg.addColorStop(0, '#ffffff'); tg.addColorStop(1, hexA(t.a, 1));
    ctx.fillStyle = tg;
    ctx.fillText(title, 44, 160);

    const start = d.points[0];
    const sub = start?.label ? `📍 ${start.label}${d.loop ? '  ·  boucle ↺' : ''}` : (d.loop ? 'Boucle ↺' : '');
    if (sub) {
      ctx.fillStyle = '#a3abbd';
      ctx.fillText(fitText(ctx, sub, W - 88, 26, 500, BODY), 44, 206);
    }

    // carte
    ctx.save();
    rr(ctx, MAP.x, MAP.y, MAP.w, MAP.h, MAP.r);
    ctx.fillStyle = '#0d1018';
    ctx.fill();
    ctx.clip();
    if (bg) {
      ctx.drawImage(bg, MAP.x + MAP.w * (1 - up) / 2, MAP.y + MAP.h * (1 - up) / 2, MAP.w * up, MAP.h * up);
      const v = ctx.createRadialGradient(W / 2, MAP.y + MAP.h / 2, MAP.h * 0.35, W / 2, MAP.y + MAP.h / 2, MAP.w * 0.75);
      v.addColorStop(0, 'rgba(5,6,10,0)'); v.addColorStop(1, 'rgba(5,6,10,0.55)');
      ctx.fillStyle = v; ctx.fillRect(MAP.x, MAP.y, MAP.w, MAP.h);
    } else {
      ctx.strokeStyle = 'rgba(255,255,255,0.045)';
      ctx.lineWidth = 1;
      for (let x = MAP.x; x < MAP.x + MAP.w; x += 50) { ctx.beginPath(); ctx.moveTo(x + 0.5, MAP.y); ctx.lineTo(x + 0.5, MAP.y + MAP.h); ctx.stroke(); }
      for (let y = MAP.y; y < MAP.y + MAP.h; y += 50) { ctx.beginPath(); ctx.moveTo(MAP.x, y + 0.5); ctx.lineTo(MAP.x + MAP.w, y + 0.5); ctx.stroke(); }
      const c = d.path.length ? P(d.path[Math.floor(d.path.length / 2)]) : [W / 2, MAP.y + MAP.h / 2];
      const rg = ctx.createRadialGradient(c[0], c[1], 0, c[0], c[1], 420);
      rg.addColorStop(0, hexA(t.a, 0.12)); rg.addColorStop(1, hexA(t.a, 0));
      ctx.fillStyle = rg; ctx.fillRect(MAP.x, MAP.y, MAP.w, MAP.h);
    }

    if (d.path.length > 1) {
      const pts = d.path.map(P);
      const trace = () => { ctx.beginPath(); pts.forEach(([x, y], i) => (i ? ctx.lineTo(x, y) : ctx.moveTo(x, y))); };
      ctx.lineJoin = 'round'; ctx.lineCap = 'round';
      const [sx, sy] = pts[0];
      const far = pts.reduce((best, p) => (Math.hypot(p[0] - sx, p[1] - sy) > Math.hypot(best[0] - sx, best[1] - sy) ? p : best), pts[0]);
      const lg = ctx.createLinearGradient(sx, sy, far[0] === sx && far[1] === sy ? sx + 1 : far[0], far[1]);
      lg.addColorStop(0, t.a); lg.addColorStop(1, t.b);

      ctx.save();
      ctx.shadowColor = t.b; ctx.shadowBlur = 40;
      ctx.strokeStyle = hexA(t.b, 0.35); ctx.lineWidth = 22;
      trace(); ctx.stroke();
      ctx.restore();
      ctx.strokeStyle = 'rgba(5,6,10,0.85)'; ctx.lineWidth = 13;
      trace(); ctx.stroke();
      ctx.strokeStyle = lg; ctx.lineWidth = 8;
      if (d.straight) ctx.setLineDash([2, 16]);
      trace(); ctx.stroke();
      ctx.setLineDash([]);

      // bornes kilométriques
      kmPoints(d.path, kmStep(d.distance)).forEach(k => {
        const [x, y] = P(k);
        ctx.fillStyle = '#05060a'; ctx.strokeStyle = '#fff'; ctx.lineWidth = 2.5;
        ctx.beginPath(); ctx.arc(x, y, 15, 0, Math.PI * 2); ctx.fill(); ctx.stroke();
        ctx.fillStyle = '#fff'; ctx.font = `700 ${k.km >= 10 ? 12 : 15}px ${BODY}`;
        ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
        ctx.fillText(String(Math.round(k.km)), x, y + 1);
      });
      ctx.textAlign = 'left'; ctx.textBaseline = 'alphabetic';
    }

    // points
    const ordered = [...d.points.filter(p => p.role === 'via'), ...d.points.filter(p => p.role === 'finish'), ...d.points.filter(p => p.role === 'start')];
    ordered.forEach(p => drawPin(ctx, P(p), p, d.loop));
    ctx.restore();

    ctx.strokeStyle = 'rgba(255,255,255,0.10)'; ctx.lineWidth = 2;
    rr(ctx, MAP.x, MAP.y, MAP.w, MAP.h, MAP.r); ctx.stroke();

    // pastille d'ambiance sur la carte
    const vb = `${d.vibe.emoji} ${d.vibe.label}`;
    ctx.font = `700 26px ${BODY}`;
    const vw = ctx.measureText(vb).width + 40;
    ctx.fillStyle = 'rgba(5,6,10,0.78)';
    rr(ctx, MAP.x + 24, MAP.y + 24, vw, 52, 26); ctx.fill();
    ctx.strokeStyle = hexA(t.a, 0.6); ctx.lineWidth = 2; ctx.stroke();
    ctx.fillStyle = '#fff'; ctx.textBaseline = 'middle';
    ctx.fillText(vb, MAP.x + 44, MAP.y + 51);
    ctx.textBaseline = 'alphabetic';

    // statistiques
    const stats = [
      ['DISTANCE', nf2.format(d.distance / 1000), 'km'],
      ['TEMPS VISÉ', fmtDur(d.targetSec), ''],
      ['ALLURE', fmtPace(d.paceSec), '/km'],
      ['VITESSE', d.paceSec ? (3600 / d.paceSec).toLocaleString('fr-FR', { maximumFractionDigits: 1, minimumFractionDigits: 1 }) : '—', d.paceSec ? 'km/h' : ''],
    ];
    const sy = 908, sh = 150, gap = 20, sw = (MAP.w - gap * 3) / 4;
    stats.forEach(([label, value, unit], i) => {
      const x = MAP.x + i * (sw + gap);
      ctx.fillStyle = 'rgba(255,255,255,0.045)';
      rr(ctx, x, sy, sw, sh, 24); ctx.fill();
      ctx.strokeStyle = i === 0 ? hexA(t.a, 0.55) : 'rgba(255,255,255,0.08)'; ctx.lineWidth = 2; ctx.stroke();
      ctx.fillStyle = '#8a93a6'; ctx.font = `700 19px ${BODY}`;
      ctx.fillText(label, x + 22, sy + 40);
      const val = fitText(ctx, value, sw - 44 - (unit ? 0 : 0), 46, 800, DISPLAY, 24);
      if (i === 0) {
        const vg = ctx.createLinearGradient(x, 0, x + sw, 0);
        vg.addColorStop(0, t.a); vg.addColorStop(1, t.b);
        ctx.fillStyle = vg;
      } else ctx.fillStyle = '#fff';
      ctx.fillText(val, x + 22, sy + 102);
      if (unit) { ctx.fillStyle = '#8a93a6'; ctx.font = `700 20px ${BODY}`; ctx.fillText(unit, x + 22, sy + 132); }
    });

    // profil altimétrique ou étapes
    const by = 1080, bh = 170;
    ctx.fillStyle = 'rgba(255,255,255,0.045)';
    rr(ctx, MAP.x, by, MAP.w, bh, 24); ctx.fill();
    ctx.strokeStyle = 'rgba(255,255,255,0.08)'; ctx.lineWidth = 2; ctx.stroke();
    if (d.elevation && d.elevation.profile.length > 1) {
      const e = d.elevation, px = MAP.x + 250, pw = MAP.w - 280, py = by + 26, ph = bh - 52;
      ctx.fillStyle = '#8a93a6'; ctx.font = `700 19px ${BODY}`;
      ctx.fillText('DÉNIVELÉ', MAP.x + 22, by + 44);
      ctx.fillStyle = '#fff'; ctx.font = `800 40px ${DISPLAY}`;
      ctx.fillText(`+${Math.round(e.gain)} m`, MAP.x + 22, by + 100);
      ctx.fillStyle = '#8a93a6'; ctx.font = `600 20px ${BODY}`;
      ctx.fillText(`−${Math.round(e.loss)} m · max ${Math.round(e.max)} m`, MAP.x + 22, by + 136);
      const lo = e.min, span = Math.max(10, e.max - lo);
      const xy = (v, i) => [px + i / (e.profile.length - 1) * pw, py + ph - (v - lo) / span * ph];
      ctx.beginPath();
      e.profile.forEach((v, i) => { const [x, y] = xy(v, i); i ? ctx.lineTo(x, y) : ctx.moveTo(x, y); });
      ctx.lineTo(px + pw, py + ph); ctx.lineTo(px, py + ph); ctx.closePath();
      const fg = ctx.createLinearGradient(0, py, 0, py + ph);
      fg.addColorStop(0, hexA(t.a, 0.45)); fg.addColorStop(1, hexA(t.a, 0));
      ctx.fillStyle = fg; ctx.fill();
      ctx.beginPath();
      e.profile.forEach((v, i) => { const [x, y] = xy(v, i); i ? ctx.lineTo(x, y) : ctx.moveTo(x, y); });
      const sg = ctx.createLinearGradient(px, 0, px + pw, 0);
      sg.addColorStop(0, t.a); sg.addColorStop(1, t.b);
      ctx.strokeStyle = sg; ctx.lineWidth = 4; ctx.stroke();
    } else {
      ctx.fillStyle = '#8a93a6'; ctx.font = `700 19px ${BODY}`;
      ctx.fillText('PARCOURS', MAP.x + 22, by + 44);
      const names = d.points.map(p => (p.role === 'start' ? '▶ ' : p.role === 'finish' ? '🏁 ' : `${p.index}. `) + (p.label || '').split(',')[0]);
      if (d.loop && d.points.length > 1) names.push('↺ retour');
      const lines = wrap(ctx, names.join('  →  '), MAP.w - 44, `600 24px ${BODY}`, 3);
      ctx.fillStyle = '#e6e9f0';
      lines.forEach((l, i) => ctx.fillText(l, MAP.x + 22, by + 86 + i * 32));
    }

    // pied
    ctx.fillStyle = '#5d6578'; ctx.font = `500 20px ${BODY}`;
    const stops = Math.max(0, d.points.length - (d.loop ? 1 : 2));
    ctx.fillText(`${stops} étape${stops > 1 ? 's' : ''}${d.straight ? ' · à vol d’oiseau' : ''}`, 44, 1306);
    ctx.textAlign = 'right';
    ctx.fillText(bg ? 'Carte © Google · tracé avec Foulée' : 'tracé avec Foulée', W - 44, 1306);
    ctx.textAlign = 'left';

    return { mapUsed: !!bg };
  }

  function drawPin(ctx, [x, y], p, loop) {
    ctx.save();
    if (p.role === 'via') {
      ctx.fillStyle = '#8b5cf6'; ctx.strokeStyle = '#05060a'; ctx.lineWidth = 4;
      ctx.beginPath(); ctx.arc(x, y, 18, 0, Math.PI * 2); ctx.fill(); ctx.stroke();
      ctx.fillStyle = '#fff'; ctx.font = `800 18px ${BODY}`; ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
      ctx.fillText(String(p.index), x, y + 1);
    } else if (p.role === 'finish') {
      ctx.shadowColor = '#ff3d81'; ctx.shadowBlur = 24;
      ctx.fillStyle = '#ff3d81'; ctx.beginPath(); ctx.arc(x, y, 26, 0, Math.PI * 2); ctx.fill();
      ctx.shadowBlur = 0;
      ctx.beginPath(); ctx.arc(x, y, 20, 0, Math.PI * 2); ctx.clip();
      const s = 8;
      for (let i = -3; i < 3; i++) for (let j = -3; j < 3; j++) {
        ctx.fillStyle = (i + j) % 2 === 0 ? '#fff' : '#111';
        ctx.fillRect(x + i * s, y + j * s, s, s);
      }
    } else {
      ctx.shadowColor = '#c6ff3d'; ctx.shadowBlur = 26;
      ctx.fillStyle = '#c6ff3d'; ctx.strokeStyle = '#05060a'; ctx.lineWidth = 5;
      ctx.beginPath(); ctx.arc(x, y, 26, 0, Math.PI * 2); ctx.fill(); ctx.shadowBlur = 0; ctx.stroke();
      ctx.fillStyle = '#05060a'; ctx.strokeStyle = '#05060a';
      if (loop) {
        ctx.lineWidth = 4; ctx.lineCap = 'round';
        ctx.beginPath(); ctx.arc(x, y, 11, -0.3, Math.PI * 1.55); ctx.stroke();
        ctx.beginPath(); ctx.moveTo(x + 13, y - 12); ctx.lineTo(x + 13, y - 1); ctx.lineTo(x + 3, y - 5); ctx.fill();
      } else {
        ctx.beginPath(); ctx.moveTo(x - 7, y - 11); ctx.lineTo(x + 12, y); ctx.lineTo(x - 7, y + 11); ctx.closePath(); ctx.fill();
      }
    }
    ctx.restore();
  }

  function wrap(ctx, text, maxW, font, maxLines) {
    ctx.font = font;
    const words = text.split(' '), lines = [];
    let line = '';
    for (const w of words) {
      const test = line ? line + ' ' + w : w;
      if (ctx.measureText(test).width > maxW && line) { lines.push(line); line = w; } else line = test;
    }
    if (line) lines.push(line);
    if (lines.length > maxLines) {
      const kept = lines.slice(0, maxLines);
      let last = kept[maxLines - 1];
      while (last.length > 1 && ctx.measureText(last + '…').width > maxW) last = last.slice(0, -1);
      kept[maxLines - 1] = last + '…';
      return kept;
    }
    return lines;
  }

  /** Pas des bornes kilométriques : au plus une douzaine sur l'affiche. */
  function kmStep(dist) {
    return [1000, 2000, 5000, 10000, 20000, 50000].find(s => dist / s <= 12) || 100000;
  }

  function kmPoints(path, every) {
    const R = 6371008.8, r = Math.PI / 180;
    const dist = (a, b) => {
      const h = Math.sin((b.lat - a.lat) * r / 2) ** 2 + Math.cos(a.lat * r) * Math.cos(b.lat * r) * Math.sin((b.lng - a.lng) * r / 2) ** 2;
      return 2 * R * Math.asin(Math.min(1, Math.sqrt(h)));
    };
    const out = [];
    let acc = 0, next = every;
    for (let i = 1; i < path.length; i++) {
      const seg = dist(path[i - 1], path[i]);
      while (seg > 0 && acc + seg >= next) {
        const t = (next - acc) / seg;
        out.push({ lat: path[i - 1].lat + (path[i].lat - path[i - 1].lat) * t, lng: path[i - 1].lng + (path[i].lng - path[i - 1].lng) * t, km: next / 1000 });
        next += every;
      }
      acc += seg;
    }
    return out;
  }

  return { render };
})();
