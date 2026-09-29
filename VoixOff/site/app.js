/* ==========================================================================
   Portfolio voix off — rendu et interactions.

   Le contenu vient de contenu.js (window.PORTFOLIO) : il n'y a rien à
   modifier ici pour ajouter une vidéo ou un extrait.

   Trois sortes de médias, reconnues d'après le lien :
     - YouTube : la vignette s'agrandit en « théâtre » et la vidéo s'y lit ;
     - fichier vidéo (.mp4, .webm, .mov) : même théâtre, lecteur du navigateur ;
     - fichier audio (.mp3, .wav, .m4a…) : lu sur place, avec sa forme d'onde.
   Un seul média joue à la fois : lancer l'un éteint l'autre en fondu.
   ========================================================================== */

(() => {
  "use strict";

  const P = window.PORTFOLIO || {};
  const racine = document.documentElement;
  const mouvementReduit = matchMedia("(prefers-reduced-motion: reduce)");
  const EASE = "cubic-bezier(.22, .8, .24, 1)";

  /* Durée d'une animation, ramenée à zéro si le visiteur limite les mouvements. */
  const ms = (d) => (mouvementReduit.matches ? 0 : d);
  const attendre = (d) => new Promise((ok) => setTimeout(ok, d));
  const image = () => new Promise((ok) => requestAnimationFrame(() => ok()));
  const borner = (v, min, max) => Math.min(max, Math.max(min, v));
  const $ = (s, r = document) => r.querySelector(s);

  function el(tag, props, ...enfants) {
    const n = document.createElement(tag);
    for (const [k, v] of Object.entries(props || {})) {
      if (v == null || v === false) continue;
      if (k === "class") n.className = v;
      else if (k === "text") n.textContent = v;
      else if (k === "html") n.innerHTML = v; // icônes SVG internes uniquement
      else if (k === "style") n.style.cssText = v;
      else n.setAttribute(k, v === true ? "" : v);
    }
    for (const e of enfants.flat()) if (e != null && e !== false && e !== "") n.append(e);
    return n;
  }

  const hms = (s) => {
    if (!Number.isFinite(s)) return "–:––";
    s = Math.floor(s);
    return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
  };

  const meta = (item) => [item.client, item.categorie, item.annee].filter(Boolean).join(" · ");

  const ICONES = {
    lecture:
      '<svg class="i-lecture" viewBox="0 0 24 24" aria-hidden="true"><path d="M8.5 5.6v12.8a.9.9 0 0 0 1.37.77l10.2-6.4a.9.9 0 0 0 0-1.54l-10.2-6.4A.9.9 0 0 0 8.5 5.6z"/></svg>',
    pause:
      '<svg class="i-pause" viewBox="0 0 24 24" aria-hidden="true"><rect x="6.5" y="5" width="3.8" height="14" rx="1.1"/><rect x="13.7" y="5" width="3.8" height="14" rx="1.1"/></svg>',
  };
  const bascule = () => el("span", { class: "bascule", "aria-hidden": "true", html: ICONES.lecture + ICONES.pause });
  const egaliseur = () => el("span", { class: "egaliseur", "aria-hidden": "true", html: "<i></i><i></i><i></i>" });

  /* ------------------------------------------------------------------------
     Lecture de contenu.js
     ------------------------------------------------------------------------ */

  const EXT_AUDIO = /\.(mp3|wav|m4a|aac|ogg|oga|opus|flac)$/i;
  const EXT_VIDEO = /\.(mp4|m4v|webm|mov)$/i;

  function secondes(t) {
    if (!t) return 0;
    if (/^\d+$/.test(t)) return Number(t);
    const m = /^(?:(\d+)h)?(?:(\d+)m)?(?:(\d+)s)?$/.exec(t);
    return m ? (Number(m[1]) || 0) * 3600 + (Number(m[2]) || 0) * 60 + (Number(m[3]) || 0) : 0;
  }

  function analyserLien(lien) {
    let u;
    try {
      u = new URL(lien, location.href);
    } catch {
      return {};
    }
    const hote = u.hostname.replace(/^(www|m|music)\./, "");
    let id = null;
    if (hote === "youtu.be") id = u.pathname.split("/")[1];
    else if (hote === "youtube.com" || hote === "youtube-nocookie.com") {
      id = u.searchParams.get("v") || (u.pathname.match(/^\/(?:embed|shorts|live|v)\/([^/?#]+)/) || [])[1];
    }
    if (id) {
      return {
        type: "youtube",
        yt: id,
        debut: secondes(u.searchParams.get("t") || u.searchParams.get("start")),
        vertical: u.pathname.startsWith("/shorts/"),
      };
    }
    if (EXT_AUDIO.test(u.pathname)) return { type: "audio" };
    if (EXT_VIDEO.test(u.pathname)) return { type: "video" };
    return {};
  }

  const slugsPris = new Set();
  function slugifier(texte) {
    const base =
      String(texte || "")
        .normalize("NFD")
        .replace(/\p{Diacritic}/gu, "")
        .toLowerCase()
        .replace(/[^a-z0-9]+/g, "-")
        .replace(/^-+|-+$/g, "") || "extrait";
    let s = base;
    for (let n = 2; slugsPris.has(s); n++) s = `${base}-${n}`;
    slugsPris.add(s);
    return s;
  }

  function preparer(brut) {
    const lien = String(brut.lien || "").trim();
    const infos = analyserLien(lien);
    const type = brut.type || infos.type;
    if (!lien || !type || (type === "youtube" && !infos.yt)) {
      console.warn(`[portfolio] Lien non reconnu, travail ignoré : « ${brut.titre || lien || "sans titre"} »`);
      return null;
    }
    const vertical = brut.format === "vertical" || (brut.format !== "horizontal" && infos.vertical);
    return {
      titre: String(brut.titre || "Sans titre"),
      client: brut.client || "",
      categorie: String(brut.categorie || "").trim(),
      annee: brut.annee || "",
      description: brut.description || "",
      duree: brut.duree || "",
      image: brut.image || "",
      vedette: Boolean(brut.vedette),
      lien,
      type,
      yt: infos.yt || null,
      debut: infos.debut || 0,
      ratio: vertical ? 9 / 16 : 16 / 9,
      slug: slugifier(brut.titre),
    };
  }

  const items = new Map(); // slug → travail

  /* ------------------------------------------------------------------------
     Vignettes
     ------------------------------------------------------------------------ */

  function vignette(item, chargement) {
    if (item.image) return el("img", { src: item.image, alt: "", loading: chargement, decoding: "async" });
    if (item.type === "youtube") {
      // maxresdefault n'existe pas pour toutes les vidéos : YouTube renvoie
      // alors une image grise de 120 px, qu'on remplace par hqdefault.
      const img = el("img", {
        src: `https://i.ytimg.com/vi/${encodeURIComponent(item.yt)}/maxresdefault.jpg`,
        alt: "",
        loading: chargement,
        decoding: "async",
      });
      const repli = () => {
        if (img.dataset.repli) return;
        img.dataset.repli = "1";
        img.src = `https://i.ytimg.com/vi/${encodeURIComponent(item.yt)}/hqdefault.jpg`;
      };
      img.addEventListener("error", repli);
      img.addEventListener("load", () => img.naturalWidth <= 120 && repli());
      return img;
    }
    if (item.type === "video") {
      return el("video", { src: `${item.lien}#t=0.1`, muted: true, playsinline: true, preload: "metadata", tabindex: "-1", "aria-hidden": "true" });
    }
    return el("div");
  }

  /* Copie de la vignette affichée, pour que le théâtre parte exactement de
     l'image qu'on voit : même fichier (déjà décodé), ou image courante d'une
     vidéo recopiée dans un canevas. */
  function copieVisuelle(source, item) {
    if (source instanceof HTMLImageElement) {
      const copie = source.cloneNode();
      copie.removeAttribute("loading");
      return copie;
    }
    if (source instanceof HTMLVideoElement && source.readyState >= 2 && source.videoWidth) {
      const c = document.createElement("canvas");
      c.width = source.videoWidth;
      c.height = source.videoHeight;
      try {
        c.getContext("2d").drawImage(source, 0, 0);
        return c;
      } catch {
        /* image illisible : on retombe sur une vignette neuve */
      }
    }
    return vignette(item, "eager");
  }

  function decodee(n) {
    if (n instanceof HTMLImageElement && n.decode) return Promise.race([n.decode().catch(() => {}), attendre(120)]);
    return Promise.resolve();
  }

  /* Au premier survol d'une vignette YouTube, on ouvre les connexions dont le
     lecteur aura besoin : il démarre plus vite au clic. */
  let prechauffe = false;
  function prechauffer() {
    if (prechauffe) return;
    prechauffe = true;
    for (const href of ["https://www.youtube-nocookie.com", "https://www.youtube.com", "https://www.google.com"]) {
      document.head.append(el("link", { rel: "preconnect", href }));
    }
  }

  function mediaVideo(item, grand) {
    const bouton = el(
      "button",
      { type: "button", class: "carte-media", "data-slug": item.slug, "aria-label": `Regarder : ${item.titre}` },
      vignette(item, grand ? "eager" : "lazy"),
      el("span", { class: "pastille", "aria-hidden": "true", html: ICONES.lecture }),
      item.duree && el("span", { class: "badge-duree", text: item.duree }),
    );
    bouton.addEventListener("click", () => Theatre.ouvrir(item));
    if (item.type === "youtube") bouton.addEventListener("pointerenter", prechauffer, { once: true });
    return bouton;
  }

  /* ------------------------------------------------------------------------
     Extraits audio
     ------------------------------------------------------------------------ */

  const pistes = [];
  let courante = null; // la piste qui joue (ou jouait en dernier)
  let boucle = 0;

  function construirePiste(item, grand) {
    const audio = new Audio();
    audio.preload = "metadata";
    audio.src = item.lien;

    const bouton = el("button", { type: "button", class: "audio-bouton", "aria-label": `Écouter : ${item.titre}` }, bascule());
    const onde = el(
      "div",
      {
        class: "onde",
        role: "slider",
        tabindex: "0",
        "aria-label": `Position dans « ${item.titre} »`,
        "aria-valuemin": "0",
        "aria-valuemax": "0",
        "aria-valuenow": "0",
      },
      el("div", { class: "onde-couche onde-fond" }),
      el("div", { class: "onde-couche onde-lue" }),
    );
    const temps = el("span", { class: "audio-temps", text: item.duree || "–:––" });
    const conteneur = el(
      "div",
      { class: `carte-media audio${grand ? " audio-grand" : ""}`, "data-slug": item.slug },
      el("div", { class: "audio-tete" }, egaliseur(), el("span", { class: "etiquette", text: "Audio" })),
      onde,
      el("div", { class: "audio-pied" }, bouton, temps),
    );

    const p = { item, audio, bouton, onde, temps, conteneur, grand, n: 0, seconde: -1, fondu: 0, pauseMini: false };
    pistes.push(p);

    bouton.addEventListener("click", () => (audio.paused ? jouer(p) : audio.pause()));
    audio.addEventListener("loadedmetadata", () => {
      onde.setAttribute("aria-valuemax", String(Math.round(audio.duration)));
      p.seconde = -1;
      majProgression(p);
    });
    audio.addEventListener("play", () => surLecture(p));
    audio.addEventListener("pause", () => surPause(p));
    audio.addEventListener("ended", () => surFin(p));
    audio.addEventListener("error", () => {
      conteneur.classList.add("en-erreur");
      temps.textContent = "Fichier introuvable";
      bouton.disabled = true;
    });

    // Clic ou toucher : aller à ce moment de l'extrait et le lancer.
    onde.addEventListener("click", (e) => {
      if (bouton.disabled) return;
      positionner(p, ratioPointeur(onde, e));
      if (audio.paused) jouer(p);
    });
    // Souris : glisser pour parcourir l'extrait.
    onde.addEventListener("pointerdown", (e) => {
      if (e.pointerType !== "mouse" || e.button !== 0 || bouton.disabled) return;
      e.preventDefault();
      onde.setPointerCapture(e.pointerId);
      const suivre = (ev) => positionner(p, ratioPointeur(onde, ev));
      onde.addEventListener("pointermove", suivre);
      onde.addEventListener("lostpointercapture", () => onde.removeEventListener("pointermove", suivre), { once: true });
    });
    onde.addEventListener("keydown", (e) => {
      const d = audio.duration;
      if (!Number.isFinite(d)) return;
      const pas = { ArrowLeft: -5, ArrowDown: -5, ArrowRight: 5, ArrowUp: 5, PageDown: -30, PageUp: 30 }[e.key];
      let t;
      if (pas) t = audio.currentTime + pas;
      else if (e.key === "Home") t = 0;
      else if (e.key === "End") t = d - 0.05;
      else return;
      e.preventDefault();
      audio.currentTime = borner(t, 0, d);
      majProgression(p);
    });

    return conteneur;
  }

  const ratioPointeur = (n, e) => {
    const r = n.getBoundingClientRect();
    return borner((e.clientX - r.left) / r.width, 0, 1);
  };

  function positionner(p, k) {
    const a = p.audio;
    const appliquer = () => {
      a.currentTime = k * a.duration;
      majProgression(p);
    };
    if (Number.isFinite(a.duration) && a.duration > 0) appliquer();
    else a.addEventListener("loadedmetadata", appliquer, { once: true });
  }

  function jouer(p) {
    p.fondu++; // interrompt un fondu de sortie en cours
    p.pauseMini = false;
    p.audio.volume = 1;
    const promesse = p.audio.play();
    if (promesse) promesse.catch(() => {});
  }

  /* Baisse le son d'un média puis le met en pause : pas de coupure sèche. */
  function fondre(p, duree = 320) {
    const a = p.audio;
    p.conteneur.classList.remove("joue");
    if (a.paused) return;
    const jeton = ++p.fondu;
    const d = ms(duree);
    if (!d) return a.pause();
    const t0 = performance.now();
    const etape = (t) => {
      if (p.fondu !== jeton) return;
      const k = Math.min(1, (t - t0) / d);
      a.volume = (1 - k) ** 2;
      if (k < 1) requestAnimationFrame(etape);
      else {
        a.pause();
        a.volume = 1;
      }
    };
    requestAnimationFrame(etape);
  }

  function arreterAudio() {
    if (courante && !courante.audio.paused) fondre(courante);
  }

  function surLecture(p) {
    if (courante && courante !== p) fondre(courante);
    courante = p;
    p.conteneur.classList.add("joue");
    p.bouton.setAttribute("aria-label", `Mettre en pause : ${p.item.titre}`);
    Mini.suivre(p);
    if (!boucle) boucle = requestAnimationFrame(animer);
  }

  function surPause(p) {
    p.conteneur.classList.remove("joue");
    p.bouton.setAttribute("aria-label", `Écouter : ${p.item.titre}`);
    majProgression(p);
    Mini.maj();
  }

  function surFin(p) {
    p.audio.currentTime = 0;
    p.seconde = -1;
    majProgression(p);
    if (courante === p) {
      courante = null;
      Mini.suivre(null);
    }
  }

  /* Progression rafraîchie à chaque image, pour un curseur parfaitement fluide. */
  function animer() {
    boucle = 0;
    if (!courante) return;
    majProgression(courante);
    if (!courante.audio.paused) boucle = requestAnimationFrame(animer);
  }

  function majProgression(p) {
    const { currentTime: t, duration: d, paused } = p.audio;
    const k = Number.isFinite(d) && d > 0 ? t / d : 0;
    p.onde.style.setProperty("--p", k.toFixed(4));
    const s = Math.floor(t);
    if (s !== p.seconde) {
      p.seconde = s;
      if (!p.conteneur.classList.contains("en-erreur")) p.temps.textContent = t > 0 || !paused ? `${hms(t)} / ${hms(d)}` : hms(d);
      p.onde.setAttribute("aria-valuenow", String(s));
      p.onde.setAttribute("aria-valuetext", `${hms(t)} sur ${hms(d)}`);
    }
    if (courante === p) Mini.progression(k, t, d);
  }

  /* Forme d'onde : barres dimensionnées d'après la largeur disponible, puis
     hauteurs calculées depuis le fichier, dès qu'il approche de l'écran. */
  function dessinerBarres(p) {
    const largeur = p.onde.clientWidth || 320;
    p.n = borner(Math.round(largeur / (p.grand ? 6 : 5)), 32, 200);
    for (const couche of p.onde.children) {
      couche.replaceChildren(...Array.from({ length: p.n }, (_, i) => el("i", { style: `--i:${i}` })));
    }
  }

  async function calculerOnde(url, n) {
    const reponse = await fetch(url);
    if (!reponse.ok) throw new Error(`HTTP ${reponse.status}`);
    const donnees = await reponse.arrayBuffer();
    const Contexte = window.OfflineAudioContext || window.webkitOfflineAudioContext;
    const tampon = await new Promise((ok, ko) => {
      const r = new Contexte(1, 2, 44100).decodeAudioData(donnees, ok, ko);
      if (r && r.then) r.then(ok, ko);
    });
    const canaux = Array.from({ length: tampon.numberOfChannels }, (_, c) => tampon.getChannelData(c));
    const taille = Math.floor(tampon.length / n);
    const saut = Math.max(1, Math.floor(taille / 1500));
    const niveaux = new Array(n).fill(0);
    for (let b = 0; b < n; b++) {
      let somme = 0;
      let compte = 0;
      for (let i = b * taille, fin = (b + 1) * taille; i < fin; i += saut) {
        for (const ch of canaux) somme += ch[i] * ch[i];
        compte += canaux.length;
      }
      niveaux[b] = compte ? Math.sqrt(somme / compte) : 0;
    }
    const max = Math.max(...niveaux) || 1;
    return niveaux.map((v) => Math.max(0.05, (v / max) ** 0.7));
  }

  function chargerOnde(p) {
    calculerOnde(p.item.lien, p.n).then(
      (hauteurs) => {
        p.conteneur.classList.add("onde-prete");
        p.onde.getBoundingClientRect(); // la transition doit exister avant les nouvelles hauteurs
        for (const couche of p.onde.children) {
          [...couche.children].forEach((b, i) => b.style.setProperty("--h", hauteurs[i].toFixed(3)));
        }
      },
      (err) => {
        console.info(`[portfolio] Forme d'onde indisponible pour « ${p.item.titre} » (${err.message || err}).`);
        p.conteneur.classList.add("onde-plate");
      },
    );
  }

  /* ------------------------------------------------------------------------
     Lecteur flottant
     ------------------------------------------------------------------------ */

  const Mini = {
    piste: null,
    carteVisible: true,
    temps: "",

    init() {
      this.racine = $(".mini");
      this.bouton = $(".mini-bouton");
      this.titre = $(".mini-titre");
      this.horloge = $(".mini-temps");
      this.bouton.addEventListener("click", () => {
        const p = this.piste;
        if (!p) return;
        if (p.audio.paused) jouer(p);
        else {
          p.pauseMini = true;
          p.audio.pause();
        }
      });
      this.titre.addEventListener("click", () => this.revenir());
      this.obs = new IntersectionObserver(
        ([e]) => {
          this.carteVisible = e.isIntersecting;
          this.maj();
        },
        { threshold: 0.2 },
      );
    },

    suivre(p) {
      if (p !== this.piste) {
        if (this.piste) this.obs.unobserve(this.piste.conteneur);
        this.piste = p;
        if (p) {
          this.titre.textContent = p.item.titre;
          this.carteVisible = true;
          this.obs.observe(p.conteneur);
        }
      }
      this.maj();
    },

    maj() {
      const p = this.piste;
      const joue = Boolean(p) && !p.audio.paused;
      const visible = Boolean(p) && !this.carteVisible && !Theatre.actif && (joue || p.pauseMini);
      this.racine.classList.toggle("visible", visible);
      this.racine.classList.toggle("joue", joue);
      this.racine.inert = !visible;
      this.bouton.setAttribute("aria-label", joue ? "Mettre en pause" : "Reprendre la lecture");
    },

    progression(k, t, d) {
      this.racine.style.setProperty("--p", k.toFixed(4));
      const texte = `${hms(t)} / ${hms(d)}`;
      if (texte !== this.temps) this.horloge.textContent = this.temps = texte;
    },

    /* Ramène à l'extrait, en réaffichant tout s'il est masqué par un filtre. */
    async revenir() {
      const p = this.piste;
      if (!p) return;
      if (p.conteneur.closest("[hidden]")) {
        filtrer(TOUT);
        await attendre(ms(700));
      }
      p.conteneur.scrollIntoView({ behavior: ms(1) ? "smooth" : "auto", block: "center" });
    },
  };

  /* ------------------------------------------------------------------------
     Théâtre : la vignette s'envole et devient le lecteur
     ------------------------------------------------------------------------ */

  const px = (r) => ({ top: `${r.top}px`, left: `${r.left}px`, width: `${r.width}px`, height: `${r.height}px` });

  const Theatre = {
    actif: false, // ouvert, ou en train de s'ouvrir / se fermer
    occupe: false, // une animation est en cours
    aFermer: false, // fermeture demandée pendant une animation
    pousse: false, // l'ouverture a ajouté une entrée à l'historique
    item: null,
    media: null,
    liste: [],
    lecteur: null,

    init() {
      this.racine = $(".theatre");
      this.fond = $(".theatre-fond");
      this.scene = $(".scene");
      this.legende = $(".legende");
      this.lgTitre = $(".legende-titre");
      this.lgCompteur = $(".legende-compteur");
      this.lgMeta = $(".legende-meta");
      this.lgTexte = $(".legende-texte");
      this.btnFermer = $(".theatre-fermer");
      this.chargeur = el("div", { class: "chargeur", "aria-hidden": "true" });

      // detail vaut 0 quand le bouton est actionné au clavier.
      this.btnFermer.addEventListener("click", (e) => this.demanderFermeture(e.detail === 0));
      this.fond.addEventListener("click", () => this.demanderFermeture());
      $(".theatre-prec").addEventListener("click", () => this.naviguer(-1));
      $(".theatre-suiv").addEventListener("click", () => this.naviguer(1));

      document.addEventListener("keydown", (e) => {
        if (!this.actif) return;
        if (e.key === "Escape") {
          e.preventDefault();
          this.demanderFermeture(true);
        } else if ((e.key === "ArrowLeft" || e.key === "ArrowRight") && e.target.tagName !== "VIDEO") {
          e.preventDefault();
          this.naviguer(e.key === "ArrowLeft" ? -1 : 1);
        }
      });

      // Mobile : glisser à gauche / à droite pour changer, vers le bas pour fermer.
      let x0 = null;
      let y0 = 0;
      this.racine.addEventListener(
        "touchstart",
        (e) => {
          x0 = e.target.closest(".scene-lecteur") ? null : e.touches[0].clientX;
          y0 = e.touches[0].clientY;
        },
        { passive: true },
      );
      this.racine.addEventListener(
        "touchend",
        (e) => {
          if (x0 == null) return;
          const dx = e.changedTouches[0].clientX - x0;
          const dy = e.changedTouches[0].clientY - y0;
          x0 = null;
          if (Math.abs(dx) > 50 && Math.abs(dx) > Math.abs(dy) * 1.4) this.naviguer(dx < 0 ? 1 : -1);
          else if (dy > 90 && dy > Math.abs(dx) * 1.4) this.demanderFermeture();
        },
        { passive: true },
      );

      let attente = 0;
      addEventListener("resize", () => {
        cancelAnimationFrame(attente);
        attente = requestAnimationFrame(() => this.replacer());
      });
      addEventListener("popstate", () => this.surHistorique());
    },

    /* Place de la scène : la plus grande possible, légende comprise, centrée. */
    cible(ratio) {
      const vw = innerWidth;
      const vh = innerHeight;
      const etroit = vw < 720;
      const marge = etroit ? 16 : borner(vw * 0.08, 72, 140);
      const haut = etroit ? 64 : 72;
      const bas = etroit ? 84 : 24;
      const legende = etroit ? 132 : 124;
      let l = Math.min(vw - 2 * marge, 1500);
      let h = l / ratio;
      const hMax = Math.max(160, vh - haut - bas - legende);
      if (h > hMax) {
        h = hMax;
        l = h * ratio;
      }
      const top = haut + Math.max(0, (vh - haut - bas - legende - h) / 2);
      return { top, left: (vw - l) / 2, width: l, height: h };
    },

    placerLegende(g) {
      const l = Math.min(Math.max(g.width, 480), innerWidth - 32);
      Object.assign(this.legende.style, {
        top: `${g.top + g.height + 20}px`,
        left: `${g.left + g.width / 2 - l / 2}px`,
        width: `${l}px`,
      });
      this.racine.style.setProperty("--sy", `${g.top + g.height / 2}px`);
    },

    remplirLegende(item) {
      this.lgTitre.textContent = item.titre;
      this.lgMeta.textContent = meta(item);
      this.lgMeta.hidden = !meta(item);
      this.lgTexte.textContent = item.description;
      this.lgTexte.hidden = !item.description;
      const n = this.liste.length;
      const i = this.liste.indexOf(item);
      this.lgCompteur.textContent = n > 1 ? `${String(i + 1).padStart(2, "0")} / ${String(n).padStart(2, "0")}` : "";
      this.racine.classList.toggle("seul", n < 2);
    },

    /* Vidéos visibles, dans l'ordre de la page : la vedette puis la grille filtrée. */
    videos() {
      return [...document.querySelectorAll("button.carte-media[data-slug]")]
        .filter((b) => !b.closest("[hidden]"))
        .map((b) => items.get(b.dataset.slug));
    },

    mediaDe(item) {
      const b = document.querySelector(`button.carte-media[data-slug="${CSS.escape(item.slug)}"]`);
      return b && !b.closest("[hidden]") ? b : null;
    },

    verrouiller(oui) {
      if (oui) {
        racine.style.setProperty("--compense", `${innerWidth - racine.clientWidth}px`);
        racine.classList.add("verrou");
      } else {
        racine.classList.remove("verrou");
        racine.style.removeProperty("--compense");
      }
      for (const n of document.body.children) {
        if (n !== this.racine && n.tagName !== "SCRIPT") n.inert = oui;
      }
      if (!oui) Mini.maj();
    },

    voler(de, vers, duree) {
      Object.assign(this.scene.style, px(vers));
      const d = ms(duree);
      if (this.vol) this.vol.cancel();
      if (!d) return Promise.resolve();
      this.vol = this.scene.animate([px(de), px(vers)], { duration: d, easing: EASE });
      return this.vol.finished.catch(() => {});
    },

    monterLecteur(item, g) {
      let l;
      if (item.type === "youtube") {
        const q = new URLSearchParams({ autoplay: "1", rel: "0", playsinline: "1", modestbranding: "1" });
        if (item.debut) q.set("start", String(item.debut));
        l = el("iframe", {
          class: "scene-lecteur",
          src: `https://www.youtube-nocookie.com/embed/${encodeURIComponent(item.yt)}?${q}`,
          title: item.titre,
          allow: "autoplay; encrypted-media; picture-in-picture; fullscreen",
          referrerpolicy: "strict-origin-when-cross-origin",
        });
        l.addEventListener("load", () => this.lecteurPret(l), { once: true });
      } else {
        l = el("video", { class: "scene-lecteur", src: item.lien, controls: true, playsinline: true, preload: "auto" });
        if (item.image) l.poster = item.image;
        l.addEventListener("loadeddata", () => this.lecteurPret(l), { once: true });
        l.addEventListener("error", () => this.lecteurEnErreur(l), { once: true });
      }
      l.style.width = `${g.width}px`;
      l.style.height = `${g.height}px`;
      this.lecteur = l;
      this.scene.classList.add("charge");
      this.scene.append(l);
      // Appelé dans la foulée du clic : le navigateur autorise le son.
      if (l instanceof HTMLVideoElement) {
        const promesse = l.play();
        if (promesse) promesse.catch(() => {});
      }
    },

    lecteurPret(l) {
      if (this.lecteur !== l) return;
      this.scene.classList.add("pret");
      this.scene.classList.remove("charge");
    },

    lecteurEnErreur(l) {
      if (this.lecteur !== l) return;
      this.scene.classList.remove("charge");
      this.scene.append(el("div", { class: "scene-erreur", text: "Cette vidéo n'a pas pu être chargée." }));
    },

    /* Le lecteur quitte la scène : fondu de l'image et du son, puis retrait. */
    demonterLecteur(duree) {
      const l = this.lecteur;
      this.lecteur = null;
      this.scene.querySelector(".scene-erreur")?.remove();
      if (!l) return;
      const r = l.getBoundingClientRect();
      l.style.width = `${r.width}px`;
      l.style.height = `${r.height}px`;
      if (l instanceof HTMLVideoElement) {
        const t0 = performance.now();
        const d = ms(duree);
        const etape = (t) => {
          const k = d ? Math.min(1, (t - t0) / d) : 1;
          l.volume = (1 - k) ** 2;
          if (k < 1) requestAnimationFrame(etape);
          else l.pause();
        };
        requestAnimationFrame(etape);
      }
      l.animate([{ opacity: getComputedStyle(l).opacity }, { opacity: 0 }], { duration: ms(duree), easing: "ease-out", fill: "forwards" })
        .finished.catch(() => {})
        .then(() => l.remove());
    },

    async ouvrir(item, { historique = true, depuisCarte = true } = {}) {
      if (this.actif || !item) return;
      this.actif = this.occupe = true;
      this.aFermer = this.clavier = false;
      if (historique) {
        history.pushState({ theatre: item.slug }, "", `#/${item.slug}`);
        this.pousse = true;
      }
      arreterAudio();

      this.item = item;
      this.liste = this.videos();
      // Ouvert par un lien direct, le théâtre naît au centre ; il reviendra
      // tout de même se poser sur sa carte à la fermeture.
      const media = this.mediaDe(item);
      const envol = depuisCarte && media;
      this.media = media;

      this.verrouiller(true);
      const g = this.cible(item.ratio);
      this.remplirLegende(item);
      this.placerLegende(g);

      const source = media && media.querySelector("img, video");
      const visuel = copieVisuelle(source, item);
      this.scene.className = "scene";
      this.scene.replaceChildren(el("div", { class: "scene-visuel" }, visuel), this.chargeur);
      this.monterLecteur(item, g);
      await decodee(visuel);

      const depart = envol
        ? media.getBoundingClientRect()
        : { top: g.top + g.height * 0.04, left: g.left + g.width * 0.04, width: g.width * 0.92, height: g.height * 0.92 };
      Object.assign(this.scene.style, px(depart));
      this.racine.hidden = false;
      this.racine.getBoundingClientRect(); // point de départ des transitions CSS
      this.racine.classList.add("ouvert");
      if (media) media.classList.add("souleve");
      Mini.maj();

      // La vignette survolée était légèrement zoomée : on part de ce zoom.
      const zoom = envol && getComputedStyle(source).transform;
      if (zoom && zoom !== "none") visuel.animate([{ transform: zoom }, { transform: "none" }], { duration: ms(640), easing: EASE });
      if (!envol) this.scene.animate([{ opacity: 0 }, { opacity: 1 }], { duration: ms(420), easing: "ease-out" });

      await this.voler(depart, g, 640);
      this.poser();
      this.btnFermer.focus({ preventScroll: true });
      this.finAnimation();
    },

    /* La scène a atteint sa place : le lecteur en épouse désormais la taille. */
    poser() {
      if (this.lecteur) this.lecteur.style.width = this.lecteur.style.height = "";
      this.scene.classList.add("pose");
    },

    finAnimation() {
      this.occupe = false;
      if (this.aFermer) {
        this.aFermer = false;
        this.fermer();
      }
    },

    async fermer() {
      if (!this.actif) return;
      if (this.occupe) {
        this.aFermer = true;
        return;
      }
      this.occupe = true;
      const media = this.media;
      const de = this.scene.getBoundingClientRect();
      this.scene.classList.remove("pose", "charge");
      this.demonterLecteur(220);

      // La carte d'origine a pu sortir de l'écran (navigation entre vidéos) :
      // on la ramène d'un coup, invisible derrière le fond, avant d'y revoler.
      let vers = null;
      if (media && media.isConnected && !media.closest("[hidden]")) {
        // Carte jamais apparue (lien direct) : elle doit être là à l'atterrissage.
        const cachee = media.closest(".a-reveler");
        if (cachee) cachee.classList.remove("a-reveler");
        let r = media.getBoundingClientRect();
        if (r.bottom < 0 || r.top > innerHeight) {
          racine.style.scrollBehavior = "auto";
          media.scrollIntoView({ block: "center" });
          racine.style.scrollBehavior = "";
          r = media.getBoundingClientRect();
        }
        vers = r;
      }

      this.racine.classList.remove("ouvert");
      if (vers) await this.voler(de, vers, 560);
      else {
        await this.scene
          .animate([{ opacity: 1, transform: "none" }, { opacity: 0, transform: "scale(.96)" }], { duration: ms(320), easing: EASE, fill: "forwards" })
          .finished.catch(() => {});
      }

      if (media) media.classList.remove("souleve");
      await image(); // la carte réapparaît sous la scène avant que celle-ci parte
      this.racine.hidden = true;
      this.scene.getAnimations().forEach((a) => a.cancel());
      this.scene.replaceChildren();
      this.scene.className = "scene";
      this.actif = false;
      this.verrouiller(false);
      this.occupe = false;
      this.aFermer = false;
      // Le focus revient à la carte ; son contour n'est montré qu'au clavier.
      if (media) media.focus({ preventScroll: true, focusVisible: this.clavier });
    },

    async naviguer(sens) {
      if (!this.actif || this.occupe || this.liste.length < 2) return;
      this.occupe = true;
      const i = this.liste.indexOf(this.item);
      const item = this.liste[(i + sens + this.liste.length) % this.liste.length];
      history.replaceState({ theatre: item.slug }, "", `#/${item.slug}`);

      // L'ancienne carte reprend sa place, la nouvelle se « soulève » : c'est
      // vers elle que la scène reviendra à la fermeture.
      if (this.media) this.media.classList.remove("souleve");
      this.media = this.mediaDe(item);
      if (this.media) this.media.classList.add("souleve");
      this.item = item;

      const de = this.scene.getBoundingClientRect();
      const g = this.cible(item.ratio);
      const anciens = [...this.scene.querySelectorAll(".scene-visuel")];
      this.demonterLecteur(180);
      this.scene.classList.remove("pret", "pose");

      const visuel = copieVisuelle(this.media && this.media.querySelector("img, video"), item);
      const calque = el("div", { class: "scene-visuel" }, visuel);
      this.scene.insertBefore(calque, this.chargeur);
      this.monterLecteur(item, g);
      await decodee(visuel);

      const d = ms(560);
      const dx = 48 * sens;
      for (const c of anciens) {
        c.animate([{ opacity: 1, transform: "none" }, { opacity: 0, transform: `translateX(${-dx}px)` }], { duration: d, easing: EASE, fill: "forwards" })
          .finished.catch(() => {})
          .then(() => c.remove());
      }
      calque.animate([{ opacity: 0, transform: `translateX(${dx}px)` }, { opacity: 1, transform: "none" }], { duration: d, easing: EASE });
      this.changerLegende(item, g);

      await this.voler(de, g, 560);
      this.poser();
      this.finAnimation();
    },

    changerLegende(item, g) {
      const lg = this.legende;
      lg.getAnimations().forEach((a) => a.cancel());
      lg.animate([{ opacity: 1 }, { opacity: 0 }], { duration: ms(160), fill: "forwards" })
        .finished.catch(() => {})
        .then(() => {
          this.remplirLegende(item);
          this.placerLegende(g);
          lg.getAnimations().forEach((a) => a.cancel());
          lg.animate([{ opacity: 0, transform: "translateY(6px)" }, { opacity: 1, transform: "none" }], { duration: ms(480), easing: EASE });
        });
    },

    replacer() {
      if (!this.actif || this.occupe) return;
      const g = this.cible(this.item.ratio);
      Object.assign(this.scene.style, px(g));
      this.placerLegende(g);
    },

    lireSlug() {
      const m = /^#\/(.+)$/.exec(location.hash);
      return m ? decodeURIComponent(m[1]) : null;
    },

    /* Fermer revient en arrière dans l'historique quand l'ouverture y avait
       ajouté une entrée : le bouton « retour » du téléphone ferme aussi. */
    demanderFermeture(clavier = false) {
      if (!this.actif) return;
      this.clavier = clavier;
      if (this.pousse && this.lireSlug()) {
        history.back();
      } else {
        if (this.lireSlug()) history.replaceState(null, "", location.pathname + location.search);
        this.pousse = false;
        this.fermer();
      }
    },

    surHistorique() {
      const slug = this.lireSlug();
      if (this.actif && !slug) {
        this.pousse = false;
        this.fermer();
      } else if (!this.actif && slug) {
        const item = items.get(slug);
        if (item && item.type !== "audio") {
          this.pousse = true;
          this.ouvrir(item, { historique: false });
        }
      }
    },
  };

  /* ------------------------------------------------------------------------
     Filtres par catégorie
     ------------------------------------------------------------------------ */

  const TOUT = "*";
  let filtreActif = TOUT;
  let jetonFiltre = 0;

  function construireFiltres(liste) {
    const nav = $(".filtres");
    const categories = [...new Set(liste.map((x) => x.categorie).filter(Boolean))];
    if (categories.length < 2) return;
    const compte = (c) => liste.filter((x) => c === TOUT || x.categorie === c).length;
    nav.replaceChildren(
      ...[TOUT, ...categories].map((c) =>
        el(
          "button",
          { type: "button", class: "filtre", "data-categorie": c, "aria-pressed": String(c === TOUT) },
          c === TOUT ? "Tout" : c,
          el("sup", { text: String(compte(c)) }),
        ),
      ),
      el("span", { class: "filtres-trait", "aria-hidden": "true" }),
    );
    nav.hidden = false;
    nav.addEventListener("click", (e) => {
      const b = e.target.closest(".filtre");
      if (b) filtrer(b.dataset.categorie);
    });
    addEventListener("resize", () => placerTrait());
  }

  function placerTrait() {
    const b = $('.filtre[aria-pressed="true"]');
    const trait = $(".filtres-trait");
    if (!b || !trait) return;
    trait.style.width = `${b.offsetWidth}px`;
    trait.style.transform = `translate(${b.offsetLeft}px, ${b.offsetTop + b.offsetHeight - 1}px)`;
  }

  /* Les cartes qui sortent s'effacent, celles qui restent glissent vers leur
     nouvelle place (technique FLIP), les nouvelles apparaissent en cascade. */
  async function filtrer(categorie) {
    if (categorie === filtreActif) return;
    filtreActif = categorie;
    const jeton = ++jetonFiltre;
    for (const b of document.querySelectorAll(".filtre")) b.setAttribute("aria-pressed", String(b.dataset.categorie === categorie));
    $(".filtres-trait")?.classList.add("anime");
    placerTrait();

    const cartes = [...document.querySelectorAll(".grille > .carte")];
    cartes.forEach((c) => c.getAnimations().forEach((a) => a.cancel()));
    const retenue = (c) => categorie === TOUT || c.dataset.categorie === categorie;
    const visibles = cartes.filter((c) => !c.hidden);
    const sortantes = visibles.filter((c) => !retenue(c));
    const restantes = visibles.filter(retenue);
    const entrantes = cartes.filter((c) => c.hidden && retenue(c));

    if (sortantes.length && ms(1)) {
      await Promise.all(
        sortantes.map((c) =>
          c
            .animate([{ opacity: 1, transform: "none" }, { opacity: 0, transform: "scale(.97)" }], { duration: 220, easing: "ease-in", fill: "forwards" })
            .finished.catch(() => {}),
        ),
      );
      if (jeton !== jetonFiltre) return;
    }

    const avant = new Map(restantes.map((c) => [c, c.getBoundingClientRect()]));
    for (const c of sortantes) {
      c.hidden = true;
      c.getAnimations().forEach((a) => a.cancel());
    }
    for (const c of [...entrantes, ...restantes]) {
      c.hidden = false;
      c.classList.remove("a-reveler");
    }
    if (!ms(1)) return;

    for (const c of restantes) {
      const a = avant.get(c);
      const b = c.getBoundingClientRect();
      const dx = a.left - b.left;
      const dy = a.top - b.top;
      if (dx || dy) c.animate([{ transform: `translate(${dx}px, ${dy}px)` }, { transform: "none" }], { duration: 640, easing: EASE });
    }
    entrantes.forEach((c, i) => {
      c.animate([{ opacity: 0, transform: "translateY(18px)" }, { opacity: 1, transform: "none" }], {
        duration: 640,
        delay: 140 + i * 55,
        easing: EASE,
        fill: "backwards",
      });
    });
  }

  /* ------------------------------------------------------------------------
     Construction de la page
     ------------------------------------------------------------------------ */

  function carte(item) {
    const m = meta(item);
    return el(
      "li",
      { class: "carte a-reveler", "data-categorie": item.categorie },
      item.type === "audio" ? construirePiste(item, false) : mediaVideo(item, false),
      el("div", { class: "carte-texte" }, el("h3", { class: "carte-titre", text: item.titre }), m && el("p", { class: "carte-meta", text: m })),
    );
  }

  function rendre() {
    const nom = String(P.nom || "").trim();
    document.title = [nom, P.metier].filter(Boolean).join(" — ") || document.title;
    $(".barre-nom").textContent = nom;
    $(".surtitre").textContent = P.metier || "";
    $(".accroche").textContent = P.accroche || "";

    // Le nom monte mot par mot, chacun glissant hors d'un cache.
    const mots = nom.split(/\s+/).filter(Boolean);
    $(".nom").replaceChildren(
      el("span", { class: "sr", text: nom }),
      ...mots.flatMap((mot, i) => [
        ...(i ? [" "] : []),
        el("span", { class: "mot", "aria-hidden": "true" }, el("span", { style: `--i:${i}`, text: mot })),
      ]),
    );

    const travaux = (Array.isArray(P.travaux) ? P.travaux : []).map(preparer).filter(Boolean);
    travaux.forEach((t) => items.set(t.slug, t));
    const vedette = travaux.find((t) => t.vedette);
    const grille = travaux.filter((t) => t !== vedette);

    if (vedette) {
      const section = $(".vedette");
      section.replaceChildren(
        vedette.type === "audio" ? construirePiste(vedette, true) : mediaVideo(vedette, true),
        el(
          "div",
          { class: "vedette-texte" },
          el("div", {}, el("h2", { class: "vedette-titre", text: vedette.titre }), meta(vedette) && el("p", { class: "carte-meta", text: meta(vedette) })),
          vedette.description && el("p", { class: "vedette-description", text: vedette.description }),
        ),
      );
      section.hidden = false;
    }

    if (grille.length) {
      $(".travaux").hidden = false;
      $(".travaux-titre").append(el("sup", { text: String(grille.length) }));
      $(".grille").replaceChildren(...grille.map(carte));
      construireFiltres(grille);
    }

    const apropos = [].concat(P.apropos || []).filter(Boolean);
    if (apropos.length) {
      $(".apropos-texte").replaceChildren(...apropos.map((t) => el("p", { text: t })));
      $(".apropos").hidden = false;
    }

    $(".contact-invite").textContent = P.invitation || "Parlons de votre projet";
    const email = $(".contact-email");
    if (P.email) {
      email.textContent = P.email;
      email.href = `mailto:${P.email}`;
    } else email.hidden = true;
    const lignes = [];
    if (P.telephone) lignes.push(el("li", {}, el("a", { href: `tel:${String(P.telephone).replace(/[^\d+]/g, "")}`, text: P.telephone })));
    for (const l of Array.isArray(P.liens) ? P.liens : []) {
      if (l && l.url) lignes.push(el("li", {}, el("a", { href: l.url, target: "_blank", rel: "noopener", text: l.libelle || l.url })));
    }
    $(".contact-lignes").replaceChildren(...lignes);
    $(".pied-mention").textContent = `© ${new Date().getFullYear()} ${nom}`.trim();

    for (const p of pistes) dessinerBarres(p);
  }

  /* Apparitions au défilement : sections et cartes montent en fondu, en
     cascade quand plusieurs entrent ensemble. */
  function observerApparitions() {
    const cibles = [...document.querySelectorAll(".a-reveler")];
    if (!("IntersectionObserver" in window) || !ms(1)) {
      cibles.forEach((n) => n.classList.remove("a-reveler"));
      return;
    }
    let premiere = true;
    const obs = new IntersectionObserver(
      (entrees) => {
        const base = premiere ? 520 : 0;
        premiere = false;
        let k = 0;
        for (const e of entrees) {
          if (!e.isIntersecting) continue;
          obs.unobserve(e.target);
          if (!e.target.classList.contains("a-reveler")) continue;
          e.target.classList.remove("a-reveler");
          e.target.animate([{ opacity: 0, transform: "translateY(24px)" }, { opacity: 1, transform: "none" }], {
            duration: 950,
            delay: base + k++ * 90,
            easing: EASE,
            fill: "backwards",
          });
        }
      },
      { rootMargin: "0px 0px -6% 0px" },
    );
    cibles.forEach((n) => obs.observe(n));
  }

  function observerOndes() {
    if (!("IntersectionObserver" in window)) return pistes.forEach(chargerOnde);
    const obs = new IntersectionObserver(
      (entrees) => {
        for (const e of entrees) {
          if (!e.isIntersecting) continue;
          obs.unobserve(e.target);
          const p = pistes.find((x) => x.conteneur === e.target);
          if (p) chargerOnde(p);
        }
      },
      { rootMargin: "400px 0px" },
    );
    pistes.forEach((p) => obs.observe(p.conteneur));
  }

  function demarrer() {
    if (!window.PORTFOLIO) console.warn("[portfolio] contenu.js est introuvable ou contient une erreur.");
    rendre();
    Mini.init();
    Theatre.init();

    // La barre du haut prend un fond et affiche le nom une fois le titre passé.
    const barre = $(".barre");
    new IntersectionObserver(([e]) => barre.classList.toggle("defile", !e.isIntersecting && e.boundingClientRect.top < 0)).observe($(".nom"));

    // On attend les polices (au plus une seconde) pour que rien ne saute
    // pendant l'entrée en scène.
    const polices = document.fonts && document.fonts.ready ? Promise.race([document.fonts.ready, attendre(1000)]) : Promise.resolve();
    polices.then(() => {
      racine.classList.add("pret");
      placerTrait();
      observerApparitions();
      observerOndes();
      const slug = Theatre.lireSlug();
      const item = slug && items.get(slug);
      if (item && item.type !== "audio") Theatre.ouvrir(item, { historique: false, depuisCarte: false });
    });
  }

  demarrer();
})();
