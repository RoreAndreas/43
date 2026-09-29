/* ==========================================================================
   Portfolio voix off — rendu et interactions.

   Les réglages viennent de contenu.js (window.PORTFOLIO), les réalisations
   de catalogue.json, qu'écrit inventaire.py à partir du dossier
   realisations/ (les fichiers déposés) et de realisations/youtube.txt (les
   liens YouTube) : rien à modifier ici.

   Accueil : une photo par rubrique. Au clic, la photo s'envole et devient
   l'illustration de la rubrique, à droite, pendant que les autres se fondent
   dans le noir et que le cadre des réalisations apparaît à gauche, sur la
   même ligne. Choisir une réalisation la lit dans le même cadre, à la place
   de la photo. « Retour », Échap ou le retour du navigateur ramènent la
   photo à sa place. Un seul média joue à la fois.
   ========================================================================== */

(() => {
  "use strict";

  const P = window.PORTFOLIO || {};
  const racine = document.documentElement;
  const reduit = matchMedia("(prefers-reduced-motion: reduce)");
  const EASE = "cubic-bezier(.22, .8, .24, 1)";
  // La photo qui vole : départ en douceur, longue arrivée.
  const VOL = "cubic-bezier(.6, 0, .15, 1)";
  const DUREE_VOL = 900;

  /* Durée d'une animation, ramenée à zéro si le visiteur limite les mouvements. */
  const ms = (d) => (reduit.matches ? 0 : d);
  const attendre = (d) => new Promise((ok) => setTimeout(ok, d));
  const image = () => new Promise((ok) => requestAnimationFrame(() => ok()));
  const borner = (v, min, max) => Math.min(max, Math.max(min, v));
  const $ = (s, r = document) => r.querySelector(s);
  const $$ = (s, r = document) => [...r.querySelectorAll(s)];
  const deux = (n) => String(n).padStart(2, "0");
  const pluriel = (n, mot) => `${n} ${mot}${n > 1 ? "s" : ""}`;

  /* Une image clé marquée offset 0 part de là et arrive sur l'état réel de
     l'élément ; sans offset, elle part de l'état réel pour y arriver. */
  function anim(n, images, opts) {
    const a = n.animate(images, { easing: EASE, ...opts, duration: ms(opts.duration || 0), delay: ms(opts.delay || 0) });
    return a.finished.catch(() => {});
  }
  const annuler = (...noeuds) => noeuds.forEach((n) => n && n.getAnimations().forEach((a) => a.cancel()));

  function el(tag, props, ...enfants) {
    const n = document.createElement(tag);
    for (const [k, v] of Object.entries(props || {})) {
      if (v == null || v === false) continue;
      if (k === "class") n.className = v;
      else if (k === "text") n.textContent = v;
      else n.setAttribute(k, v === true ? "" : v);
    }
    for (const e of enfants.flat()) if (e != null && e !== false && e !== "") n.append(e);
    return n;
  }

  const hms = (s) => {
    if (!Number.isFinite(s)) return "–:––";
    s = Math.floor(s);
    return `${Math.floor(s / 60)}:${deux(s % 60)}`;
  };

  const rect = (n) => {
    const r = n.getBoundingClientRect();
    return { top: r.top, left: r.left, width: r.width, height: r.height };
  };
  const px = (r) => ({ top: `${r.top}px`, left: `${r.left}px`, width: `${r.width}px`, height: `${r.height}px` });

  /* ------------------------------------------------------------------------
     Les réalisations : catalogue.json
     ------------------------------------------------------------------------ */

  function slugifier(texte, pris) {
    const base =
      String(texte || "")
        .normalize("NFD")
        .replace(/\p{Diacritic}/gu, "")
        .toLowerCase()
        .replace(/[^a-z0-9]+/g, "-")
        .replace(/^-+|-+$/g, "") || "element";
    let s = base;
    for (let n = 2; pris.has(s); n++) s = `${base}-${n}`;
    pris.add(s);
    return s;
  }

  /* Illustration de repli, pour une rubrique sans photo : dégradé bleu et
     barres d'onde, toujours les mêmes pour une même rubrique. */
  function artOnde(graine) {
    let h = 2166136261;
    for (const c of graine) h = Math.imul(h ^ c.charCodeAt(0), 16777619);
    const alea = () => {
      h = Math.imul(h ^ (h >>> 15), 2246822507);
      h ^= h >>> 13;
      return (h >>> 0) / 4294967296;
    };
    const W = 1600;
    const n = 56;
    const pas = W / n;
    let barres = "";
    for (let i = 0; i < n; i++) {
      const bh = (0.12 + 0.88 * alea()) * Math.sin((Math.PI * (i + 0.5)) / n) ** 0.7 * W * 0.36;
      barres += `<rect x="${(i * pas + pas * 0.32).toFixed(1)}" y="${(W / 2 - bh / 2).toFixed(1)}" width="${(pas * 0.36).toFixed(1)}" height="${bh.toFixed(1)}" rx="${(pas * 0.18).toFixed(1)}"/>`;
    }
    const svg =
      `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${W} ${W}">` +
      `<defs><radialGradient id="g" cx="40%" cy="30%" r="85%"><stop offset="0" stop-color="#a9bcff"/>` +
      `<stop offset=".5" stop-color="#2d52dc"/><stop offset="1" stop-color="#050505"/></radialGradient></defs>` +
      `<rect width="100%" height="100%" fill="url(#g)"/><g fill="#fff" fill-opacity=".82">${barres}</g></svg>`;
    return { src: `data:image/svg+xml;charset=utf-8,${encodeURIComponent(svg)}` };
  }

  /* Même comparaison que inventaire.py : sans accents, casse ni espaces en trop. */
  const cle = (t) =>
    String(t || "")
      .normalize("NFD")
      .replace(/\p{Diacritic}/gu, "")
      .toLowerCase()
      .split(/\s+/)
      .filter(Boolean)
      .join(" ");

  async function chargerCatalogue() {
    try {
      const r = await fetch("catalogue.json", { cache: "no-store" });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      return await r.json();
    } catch (erreur) {
      console.warn(`[portfolio] catalogue.json illisible (${erreur.message || erreur}) : lancez « python serve.py » ou « python inventaire.py ».`);
      return {};
    }
  }

  function realisation(brut, rub, pris) {
    const titre = String(brut.titre || "Sans titre");
    const commun = { titre, rub, slug: slugifier(titre, pris), auteur: brut.auteur || "" };
    if (brut.type === "youtube" && brut.youtube) return { ...commun, type: "youtube", yt: brut.youtube, debut: brut.debut || 0 };
    if ((brut.type === "video" || brut.type === "audio") && brut.fichier) return { ...commun, type: brut.type, lien: brut.fichier };
    return null;
  }

  /* Les rubriques de contenu.js, garnies des réalisations de leur dossier. */
  function preparerRubriques(catalogue) {
    const parDossier = new Map(Object.entries((catalogue && catalogue.rubriques) || {}).map(([nom, liste]) => [cle(nom), liste]));
    const idsPris = new Set();
    return (Array.isArray(P.rubriques) ? P.rubriques : []).map((r, index) => {
      const rub = { titre: String(r.titre || "Rubrique"), intro: r.intro || "", index, cadrage: r.cadrage || "50% 50%" };
      rub.id = slugifier(r.id || r.titre, idsPris);
      const pris = new Set();
      const liste = parDossier.get(cle(r.dossier || r.titre)) || [];
      rub.travaux = liste.map((t) => realisation(t, rub, pris)).filter(Boolean);
      const yt = rub.travaux.find((t) => t.yt);
      rub.image = r.image
        ? { src: r.image }
        : yt
          ? { src: `https://i.ytimg.com/vi/${encodeURIComponent(yt.yt)}/maxresdefault.jpg`, yt: yt.yt }
          : artOnde(rub.id);
      return rub;
    });
  }

  let rubriques = [];

  /* Photo recadrée sur son point d'intérêt. `fondu` : elle apparaît en
     fondu une fois chargée (photos de l'accueil). */
  function creerImg(a, cadrage, fondu = false) {
    const img = el("img", { src: a.src, alt: "", decoding: "async", draggable: "false" });
    img.style.objectPosition = cadrage;
    if (a.yt) {
      // maxresdefault n'existe pas pour toutes les vidéos YouTube, qui
      // renvoie alors une image grise de 120 px.
      const repli = () => {
        if (img.dataset.repli) return;
        img.dataset.repli = "1";
        img.src = `https://i.ytimg.com/vi/${encodeURIComponent(a.yt)}/hqdefault.jpg`;
      };
      img.addEventListener("error", repli);
      img.addEventListener("load", () => img.naturalWidth <= 120 && repli());
    }
    if (fondu) {
      img.classList.add("fondu");
      const vue = () => img.classList.add("vue");
      if (img.complete && img.naturalWidth) vue();
      else {
        img.addEventListener("load", vue, { once: true });
        img.addEventListener("error", vue, { once: true });
      }
    }
    return img;
  }

  const decodee = (img) => Promise.race([img.decode ? img.decode().catch(() => {}) : Promise.resolve(), attendre(700)]);

  /* ------------------------------------------------------------------------
     Éléments de la page
     ------------------------------------------------------------------------ */

  const accueil = $(".accueil");
  const bande = $(".bande");
  const focus = $(".focus");
  const barre = $(".barre");
  const retour = $(".retour");
  const carte = $(".carte");
  const liste = $(".liste");
  const cadre = $(".cadre");
  const illustration = $(".cadre-image");
  const scene = $(".scene");
  const cartel = $(".cartel");
  const enteteCarte = () => [$(".carte-tete"), $(".carte-titre"), $(".carte-intro")];

  const etat = {
    ouvert: false, // une rubrique est ouverte (ou s'ouvre, ou se ferme)
    occupe: false, // une transition est en cours
    aFermer: false, // fermeture demandée pendant une transition
    pousse: false, // l'ouverture a ajouté une entrée à l'historique
    clavier: false, // la dernière commande venait du clavier
    rub: null,
    choix: null, // la réalisation choisie
    lecteur: null, // le lecteur vidéo monté dans le cadre
  };

  function construire() {
    const nom = String(P.nom || "").trim();
    document.title = [nom, P.metier].filter(Boolean).join(" — ") || document.title;
    $(".barre-nom-texte").textContent = nom;
    $(".barre-metier").textContent = P.metier || "";

    const droite = [];
    for (const l of Array.isArray(P.liens) ? P.liens : []) {
      if (l && l.url) droite.push(el("a", { href: l.url, target: "_blank", rel: "noopener", text: l.libelle || l.url }));
    }
    if (P.email) {
      // Sur mobile, le mot « Contact » laisse place à une enveloppe.
      const enveloppe = document.createElementNS("http://www.w3.org/2000/svg", "svg");
      enveloppe.setAttribute("class", "contact-icone");
      enveloppe.setAttribute("viewBox", "0 0 24 24");
      enveloppe.setAttribute("aria-hidden", "true");
      enveloppe.innerHTML = '<rect x="3.5" y="5.5" width="17" height="13" rx="2"/><path d="m4.5 7.5 7.5 5.5 7.5-5.5"/>';
      droite.push(el("a", { class: "contact", href: `mailto:${P.email}`, "aria-label": "Contact" }, enveloppe, el("span", { class: "contact-texte", text: "Contact" })));
    }
    $(".barre-droite").replaceChildren(...droite);

    bande.replaceChildren(
      ...rubriques.map((r) => {
        const n = pluriel(r.travaux.length, "réalisation");
        const b = el(
          "button",
          { type: "button", class: "panneau", "data-id": r.id, "aria-label": `${r.titre} — ${n}` },
          el(
            "span",
            { class: "visuel" },
            creerImg(r.image, r.cadrage, true),
            el("span", { class: "voile", "aria-hidden": "true" }),
            // Le titre, en grand, monte de derrière un cache au survol.
            el(
              "span",
              { class: "visuel-texte", "aria-hidden": "true" },
              el("span", { class: "visuel-titre" }, el("span", { text: r.titre })),
              el("span", { class: "visuel-compte", text: n }),
            ),
          ),
        );
        b.addEventListener("click", (e) => ouvrir(r, { clavier: e.detail === 0 }));
        r.panneau = b;
        return b;
      }),
    );
  }

  /* Le bouton retour s'affiche dans une rubrique, et seulement là. */
  function majRetour(r) {
    retour.classList.toggle("visible", Boolean(r));
    barre.classList.toggle("en-rubrique", Boolean(r));
  }

  /* L'en-tête fixe : sa hauteur réelle sert au lecteur collant du mobile. */
  const mesurerBarre = () => racine.style.setProperty("--barre", `${barre.offsetHeight}px`);

  /* ------------------------------------------------------------------------
     Le cadre des réalisations
     ------------------------------------------------------------------------ */

  function remplirFocus(r) {
    annuler(...enteteCarte(), ...$$(".oeuvre", liste));
    $(".carte-titre").textContent = r.titre;
    $(".carte-compte").textContent = deux(r.travaux.length);
    const intro = $(".carte-intro");
    intro.textContent = r.intro;
    intro.hidden = !r.intro;
    liste.replaceChildren(...r.travaux.map((item, i) => el("li", {}, ligne(item, i))));
    liste.hidden = !r.travaux.length;
    $(".carte-vide").hidden = r.travaux.length > 0;
    liste.scrollTop = 0;
    requestAnimationFrame(majDebord);
    return $$(".oeuvre", liste);
  }

  function ligne(item, i) {
    const info = el("span", { class: "oeuvre-info", text: item.type === "youtube" ? "YouTube" : item.dureeTexte || "" });
    const b = el(
      "button",
      { type: "button", class: "oeuvre", "data-slug": item.slug, "aria-current": "false", title: item.titre },
      el("span", { class: "oeuvre-num", text: deux(i + 1) }),
      el("span", { class: "oeuvre-titre", text: item.titre }),
      el(
        "span",
        { class: "oeuvre-fin" },
        el("span", { class: "egaliseur", "aria-hidden": "true" }, el("i"), el("i"), el("i")),
        info,
      ),
    );
    b.addEventListener("click", () => choisir(item, { auto: true }));
    if (item.yt) b.addEventListener("pointerenter", prechauffer, { once: true });
    else if (!item.dureeTexte) mesurerDuree(item, info);
    return b;
  }

  /* Durée d'un fichier, lue dans ses métadonnées : quelques kilo-octets, pas
     le fichier entier. */
  function mesurerDuree(item, cible) {
    const m = item.type === "audio" ? audioDe(item) : el("video", { preload: "metadata", muted: true, src: item.lien });
    const lire = () => {
      if (!Number.isFinite(m.duration) || m.duration <= 0) return false;
      item.dureeTexte = hms(m.duration);
      cible.textContent = item.dureeTexte;
      if (m instanceof HTMLVideoElement) {
        m.removeAttribute("src");
        m.load(); // libère la connexion
      }
      return true;
    };
    if (!lire()) m.addEventListener("loadedmetadata", lire, { once: true });
  }

  /* La liste s'efface vers le bas quand des lignes restent cachées. Mesuré
     sur la mise en page (offsetTop) : les lignes, décalées pendant leur
     apparition, fausseraient scrollHeight. */
  function majDebord() {
    const derniere = liste.lastElementChild;
    const deborde =
      Boolean(derniere) &&
      getComputedStyle(liste).overflowY !== "visible" &&
      derniere.offsetTop + derniere.offsetHeight - liste.scrollTop > liste.clientHeight + 2;
    liste.classList.toggle("deborde", deborde);
  }
  liste.addEventListener("scroll", majDebord, { passive: true });

  liste.addEventListener("keydown", (e) => {
    if (e.key !== "ArrowDown" && e.key !== "ArrowUp") return;
    const lignes = $$(".oeuvre", liste);
    const i = lignes.indexOf(document.activeElement);
    if (i < 0) return;
    e.preventDefault();
    lignes[borner(i + (e.key === "ArrowDown" ? 1 : -1), 0, lignes.length - 1)].focus();
  });

  /* Au premier survol d'une réalisation YouTube, on ouvre les connexions
     dont le lecteur aura besoin : il démarre plus vite au clic. */
  let prechauffe = false;
  function prechauffer() {
    if (prechauffe) return;
    prechauffe = true;
    for (const href of ["https://www.youtube-nocookie.com", "https://www.youtube.com", "https://i.ytimg.com"]) {
      document.head.append(el("link", { rel: "preconnect", href }));
    }
  }

  /* ------------------------------------------------------------------------
     Le lecteur : la photo de la rubrique, puis la réalisation choisie
     ------------------------------------------------------------------------ */

  /* Pose la photo d'une rubrique dans le lecteur, en fondu enchaîné. Rend une
     promesse tenue quand la photo est prête à s'afficher. */
  function montrerIllustration(r, instant = false) {
    if (illustration.dataset.cle === r.image.src) return Promise.resolve();
    illustration.dataset.cle = r.image.src;
    const img = creerImg(r.image, r.cadrage);
    const prete = decodee(img);
    const anciennes = [...illustration.children];
    if (instant || !ms(1)) {
      illustration.replaceChildren(img);
      return prete;
    }
    img.style.opacity = "0";
    illustration.append(img);
    prete.then(() => {
      if (!img.isConnected) return;
      img.style.opacity = "";
      img.animate([{ opacity: 0, transform: "scale(1.02)" }, { opacity: 1, transform: "none" }], { duration: 800, easing: EASE })
        .finished.then(() => anciennes.forEach((n) => n.remove()))
        .catch(() => {});
    });
    return prete;
  }

  function enLecture() {
    const it = etat.choix;
    if (!it) return false;
    return it.type === "audio" ? Boolean(it.audio) && !it.audio.paused : Boolean(etat.lecteur && etat.lecteur._joue);
  }

  function marquer() {
    const joue = enLecture();
    for (const b of $$(".oeuvre", liste)) {
      const actif = Boolean(etat.choix) && b.dataset.slug === etat.choix.slug;
      b.setAttribute("aria-current", String(actif));
      b.classList.toggle("joue", actif && joue);
    }
  }

  function majCartel(item, instant = false) {
    const remplir = () => {
      cartel.classList.toggle("vide", !item);
      if (!item) return;
      $(".cartel-titre").textContent = item.titre;
      const meta = (item.type === "youtube" ? [item.auteur, "YouTube"] : [item.type === "audio" ? "Audio" : "Vidéo", item.dureeTexte])
        .filter(Boolean)
        .join(" · ");
      $(".cartel-meta").textContent = meta;
      $(".cartel-meta").hidden = !meta;
      $(".cartel-texte").hidden = true;
    };
    annuler(cartel);
    if (instant || !ms(1)) return remplir();
    cartel
      .animate([{ opacity: 1 }, { opacity: 0 }], { duration: 160, fill: "forwards" })
      .finished.then(() => {
        remplir();
        annuler(cartel);
        cartel.animate([{ opacity: 0, transform: "translateY(6px)" }, { opacity: 1, transform: "none" }], { duration: 500, easing: EASE });
      })
      .catch(() => {});
  }

  function majHash() {
    const r = etat.rub;
    if (r) history.replaceState(null, "", `#/${r.id}${etat.choix ? `/${etat.choix.slug}` : ""}`);
  }

  /* Choisir une réalisation la lit dans le lecteur. `auto` : le choix vient
     d'un clic, la lecture peut démarrer avec le son. */
  function choisir(item, { auto = false } = {}) {
    if (!item || !etat.ouvert) return;
    if (etat.choix === item) {
      if (item.type === "audio") basculerAudio();
      return;
    }
    arreter();
    etat.choix = item;
    majCartel(item);
    majHash();
    if (item.type === "audio") {
      cadre.classList.add("mode-audio");
      lierAudio(item);
      if (auto) jouerAudio(item);
    } else {
      monterLecteur(item, auto);
    }
    marquer();
  }

  /* Coupe ce qui joue, en fondu ; la photo de la rubrique réapparaît. */
  function arreter() {
    if (etat.lecteur) demonterLecteur();
    const it = Audio_.item;
    Audio_.item = null;
    if (it && it.audio && !it.audio.paused) fondreAudio(it.audio);
    cadre.classList.remove("mode-audio", "charge");
  }

  function monterLecteur(item, auto) {
    let l;
    if (item.type === "youtube") {
      const q = new URLSearchParams({ rel: "0", playsinline: "1", modestbranding: "1" });
      if (auto) q.set("autoplay", "1");
      if (item.debut) q.set("start", String(item.debut));
      l = el("iframe", {
        class: "lecteur",
        src: `https://www.youtube-nocookie.com/embed/${encodeURIComponent(item.yt)}?${q}`,
        title: item.titre,
        allow: "autoplay; encrypted-media; picture-in-picture; fullscreen",
        referrerpolicy: "strict-origin-when-cross-origin",
      });
      l.addEventListener("load", () => pret(l), { once: true });
    } else {
      l = el("video", { class: "lecteur", src: item.lien, controls: true, playsinline: true, preload: "auto" });
      l.addEventListener("loadeddata", () => pret(l), { once: true });
      l.addEventListener(
        "error",
        () => {
          if (etat.lecteur !== l) return;
          cadre.classList.remove("charge");
          const erreur = el("div", { class: "scene-erreur pret", text: "Cette vidéo n'a pas pu être chargée." });
          l.replaceWith(erreur);
          etat.lecteur = erreur;
        },
        { once: true },
      );
    }
    // YouTube ne dit pas s'il joue : on le suppose quand la lecture a été
    // lancée d'un clic. Le lecteur du navigateur, lui, le signale.
    l._joue = auto && item.type === "youtube";
    if (l instanceof HTMLVideoElement) {
      l.addEventListener("play", () => ((l._joue = true), marquer()));
      l.addEventListener("pause", () => ((l._joue = false), marquer()));
    }
    etat.lecteur = l;
    cadre.classList.add("charge");
    scene.append(l);
    // Dans la foulée du clic : le navigateur autorise le son.
    if (auto && l instanceof HTMLVideoElement) l.play().catch(() => {});
  }

  function pret(l) {
    if (etat.lecteur !== l) return;
    l.classList.add("pret");
    cadre.classList.remove("charge");
  }

  function demonterLecteur() {
    const l = etat.lecteur;
    etat.lecteur = null;
    if (!l) return;
    if (l instanceof HTMLVideoElement) fondreAudio(l);
    l.style.pointerEvents = "none";
    l.animate([{ opacity: getComputedStyle(l).opacity }, { opacity: 0 }], { duration: ms(300), easing: "ease-out", fill: "forwards" })
      .finished.catch(() => {})
      .then(() => l.remove());
  }

  /* Baisse le son puis met en pause : pas de coupure sèche. */
  function fondreAudio(a, duree = 300) {
    const d = ms(duree);
    if (!d) return a.pause();
    const v0 = a.volume;
    const t0 = performance.now();
    const jeton = (a._fondu = (a._fondu || 0) + 1);
    const etape = (t) => {
      if (a._fondu !== jeton) return;
      // L'horodatage de l'image peut précéder t0 : k doit rester dans [0, 1].
      const k = borner((t - t0) / d, 0, 1);
      a.volume = borner(v0 * (1 - k) ** 2, 0, 1);
      if (k < 1) requestAnimationFrame(etape);
      else {
        a.pause();
        a.volume = 1;
      }
    };
    requestAnimationFrame(etape);
  }

  /* ------------------------------------------------------------------------
     Pistes audio : une barre de lecture posée au bas de la photo
     ------------------------------------------------------------------------ */

  const Audio_ = {
    item: null,
    n: 0,
    boucle: 0,
    ondes: new Map(), // lien|barres → promesse des hauteurs
    ui: $(".audio-ui"),
    onde: $(".onde"),
    bouton: $(".audio-bouton"),
    temps: $(".audio-temps"),
  };

  function audioDe(item) {
    if (item.audio) return item.audio;
    const a = new Audio();
    a.preload = "metadata";
    a.src = item.lien;
    item.audio = a;
    const courant = () => Audio_.item === item;
    a.addEventListener("play", () => {
      if (courant()) {
        Audio_.ui.classList.add("joue");
        Audio_.bouton.setAttribute("aria-label", "Mettre en pause");
        if (!Audio_.boucle) Audio_.boucle = requestAnimationFrame(animerAudio);
      }
      marquer();
    });
    a.addEventListener("pause", () => {
      if (courant()) {
        Audio_.ui.classList.remove("joue");
        Audio_.bouton.setAttribute("aria-label", "Écouter");
        majAudio();
      }
      marquer();
    });
    a.addEventListener("ended", () => {
      a.currentTime = 0;
      if (courant()) majAudio();
    });
    a.addEventListener("loadedmetadata", () => courant() && majAudio());
    a.addEventListener("error", () => {
      item.enErreur = true;
      if (courant()) majAudio();
    });
    return a;
  }

  function lierAudio(item) {
    Audio_.item = item;
    const a = audioDe(item);
    Audio_.ui.classList.toggle("joue", !a.paused);
    const n = borner(Math.round((Audio_.onde.clientWidth || 560) / 5), 32, 160);
    if (n !== Audio_.n) {
      Audio_.n = n;
      for (const couche of Audio_.onde.children) {
        couche.replaceChildren(...Array.from({ length: n }, (_, i) => el("i", { style: `--i:${i}` })));
      }
    }
    poserOnde(null);
    const cle = `${item.lien}|${n}`;
    if (!Audio_.ondes.has(cle)) Audio_.ondes.set(cle, calculerOnde(item.lien, n).catch(() => null));
    Audio_.ondes.get(cle).then((h) => h && Audio_.item === item && poserOnde(h));
    majAudio();
  }

  function poserOnde(hauteurs) {
    for (const couche of Audio_.onde.children) {
      [...couche.children].forEach((b, i) => b.style.setProperty("--h", hauteurs ? hauteurs[i].toFixed(3) : ".06"));
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
    return niveaux.map((v) => Math.max(0.06, (v / max) ** 0.7));
  }

  function jouerAudio(item) {
    const a = audioDe(item);
    if (item.enErreur) return;
    a._fondu = (a._fondu || 0) + 1; // interrompt un fondu de sortie
    a.volume = 1;
    a.play().catch(() => {});
  }

  function basculerAudio() {
    const it = Audio_.item;
    if (!it) return;
    if (it.audio && !it.audio.paused) it.audio.pause();
    else jouerAudio(it);
  }

  function animerAudio() {
    Audio_.boucle = 0;
    const it = Audio_.item;
    if (!it || !it.audio) return;
    majAudio();
    if (!it.audio.paused) Audio_.boucle = requestAnimationFrame(animerAudio);
  }

  function majAudio() {
    const it = Audio_.item;
    if (!it) return;
    if (it.enErreur) {
      Audio_.temps.textContent = "Fichier introuvable";
      Audio_.bouton.disabled = true;
      return;
    }
    Audio_.bouton.disabled = false;
    const { currentTime: t, duration: d, paused } = audioDe(it);
    const k = Number.isFinite(d) && d > 0 ? t / d : 0;
    Audio_.onde.style.setProperty("--p", k.toFixed(4));
    Audio_.temps.textContent = t > 0 || !paused ? `${hms(t)} / ${hms(d)}` : hms(d);
    Audio_.onde.setAttribute("aria-valuemax", String(Math.round(d) || 0));
    Audio_.onde.setAttribute("aria-valuenow", String(Math.floor(t)));
    Audio_.onde.setAttribute("aria-valuetext", `${hms(t)} sur ${hms(d)}`);
  }

  function aller(k) {
    const it = Audio_.item;
    if (!it || it.enErreur) return;
    const a = audioDe(it);
    const appliquer = () => {
      a.currentTime = k * a.duration;
      majAudio();
    };
    if (Number.isFinite(a.duration) && a.duration > 0) appliquer();
    else a.addEventListener("loadedmetadata", appliquer, { once: true });
  }

  const ratio = (e) => {
    const r = Audio_.onde.getBoundingClientRect();
    return borner((e.clientX - r.left) / r.width, 0, 1);
  };

  Audio_.bouton.addEventListener("click", basculerAudio);
  Audio_.onde.addEventListener("click", (e) => {
    const it = Audio_.item;
    if (!it) return;
    aller(ratio(e));
    if (it.audio.paused) jouerAudio(it);
  });
  // Souris : glisser pour parcourir l'extrait.
  Audio_.onde.addEventListener("pointerdown", (e) => {
    if (e.pointerType !== "mouse" || e.button !== 0) return;
    e.preventDefault();
    Audio_.onde.setPointerCapture(e.pointerId);
    const suivre = (ev) => aller(ratio(ev));
    Audio_.onde.addEventListener("pointermove", suivre);
    Audio_.onde.addEventListener("lostpointercapture", () => Audio_.onde.removeEventListener("pointermove", suivre), { once: true });
  });
  Audio_.onde.addEventListener("keydown", (e) => {
    const a = Audio_.item && Audio_.item.audio;
    if (!a || !Number.isFinite(a.duration)) return;
    const pas = { ArrowLeft: -5, ArrowRight: 5, PageDown: -30, PageUp: 30 }[e.key];
    if (!pas && e.key !== "Home" && e.key !== "End") return;
    e.preventDefault();
    const t = pas ? a.currentTime + pas : e.key === "Home" ? 0 : a.duration - 0.05;
    a.currentTime = borner(t, 0, a.duration);
    majAudio();
  });

  /* ------------------------------------------------------------------------
     Transitions entre l'accueil et une rubrique
     ------------------------------------------------------------------------ */

  const panneaux = () => rubriques.map((r) => r.panneau);

  /* Les autres photos se fondent dans le noir, sur place. */
  function sortirPanneaux(p) {
    panneaux().forEach((n) => {
      if (n !== p) anim(n, [{ opacity: 0, transform: "scale(.96)" }], { duration: 650, fill: "forwards" });
    });
  }

  /* Au retour, elles en ressortent, de la plus proche à la plus lointaine. */
  function entrerPanneaux(p, delai) {
    const k = panneaux().indexOf(p);
    panneaux().forEach((n, i) => {
      annuler(n);
      if (n !== p) anim(n, [{ opacity: 0, transform: "scale(.96)", offset: 0 }], { duration: 900, delay: delai + Math.abs(i - k) * 90, fill: "backwards" });
    });
  }

  /* Le cadre des réalisations apparaît pendant que la photo s'installe, puis
     ses lignes se déroulent. `complet` : ouverture, et non changement de
     rubrique (le cadre est alors déjà là, seul son contenu change). */
  function entrerFocus(lignes, delai, complet) {
    if (complet) {
      anim(carte, [{ opacity: 0, transform: "translateY(16px)", offset: 0 }], { duration: 850, delay: delai + 40, fill: "backwards" });
      anim(cartel, [{ opacity: 0, offset: 0 }], { duration: 800, delay: delai + 480, fill: "backwards" });
    } else {
      enteteCarte().forEach((n, i) =>
        anim(n, [{ opacity: 0, transform: "translateY(8px)", offset: 0 }], { duration: 650, delay: delai + i * 50, fill: "backwards" }),
      );
    }
    lignes.forEach((l, i) =>
      anim(l, [{ opacity: 0, transform: "translateY(8px)", offset: 0 }], { duration: 650, delay: delai + (complet ? 240 : 120) + i * 45, fill: "backwards" }),
    );
  }

  function sortirFocus() {
    anim(carte, [{ opacity: 0, transform: "translateY(10px)" }], { duration: 380, fill: "forwards" });
    anim(cartel, [{ opacity: 0 }], { duration: 260, fill: "forwards" });
  }

  /* Recopie sur la copie volante l'état affiché d'un élément du panneau,
     survol compris : hors du panneau, la copie ne serait plus survolée. */
  function figer(source, clone, sel, props) {
    const s = getComputedStyle($(sel, source));
    const c = $(sel, clone);
    c.style.transition = "none";
    for (const prop of props) c.style[prop] = s[prop];
  }

  /* Copie volante de la photo d'un panneau. */
  function copieVolante(source, a) {
    const clone = source.cloneNode(true);
    clone.classList.add("volant");
    Object.assign(clone.style, px(a));
    document.body.append(clone);
    return clone;
  }

  function voler(clone, de, vers) {
    Object.assign(clone.style, px(vers));
    return anim(clone, [px(de), px(vers)], { duration: DUREE_VOL, easing: VOL });
  }

  async function ouvrir(r, { historique = true, vol = true, slug = null, clavier = false } = {}) {
    if (!r || etat.ouvert || etat.occupe) return;
    Object.assign(etat, { ouvert: true, occupe: true, aFermer: false, rub: r, choix: null, pousse: historique });
    if (historique) history.pushState(null, "", `#/${r.id}`);

    racine.classList.add("verrou");
    majRetour(r);
    const lignes = remplirFocus(r);
    majCartel(null, true);
    cadre.classList.remove("mode-audio", "charge");
    const prete = montrerIllustration(r, true);
    focus.hidden = false;
    focus.scrollTop = 0;
    majDebord();

    const p = r.panneau;
    const source = $(".visuel", p);
    if (vol && ms(1)) {
      const de = rect(source);
      const vers = rect(cadre);
      const clone = copieVolante(source, de);
      const zoom = getComputedStyle($("img", source)).transform;
      // La copie part de ce qu'on voit sous la souris : titre levé, photo
      // voilée. En vol, le titre s'efface et le voile se lève.
      figer(source, clone, ".voile", ["opacity"]);
      figer(source, clone, ".visuel-titre > span", ["transform"]);
      figer(source, clone, ".visuel-compte", ["opacity", "transform"]);
      source.style.visibility = "hidden";
      cadre.style.opacity = "0";

      anim($("img", clone), [{ transform: zoom === "none" ? "none" : zoom }, { transform: "none" }], { duration: DUREE_VOL, easing: VOL, fill: "forwards" });
      anim($(".visuel-texte", clone), [{ opacity: 0, transform: "translateY(-12px)" }], { duration: 420, fill: "forwards" });
      anim($(".voile", clone), [{ opacity: 0 }], { duration: 650, fill: "forwards" });
      sortirPanneaux(p);
      entrerFocus(lignes, 340, true);

      // La photo du lecteur doit être décodée avant de remplacer la copie.
      await Promise.all([voler(clone, de, vers), prete]);
      cadre.style.opacity = "";
      await image();
      clone.remove();
      source.style.visibility = "";
    } else {
      sortirPanneaux(p);
      anim(focus, [{ opacity: 0, offset: 0 }], { duration: 500 });
      entrerFocus(lignes, 100, true);
      await Promise.all([attendre(ms(500)), prete]);
    }

    accueil.classList.add("cache");
    accueil.inert = true;
    focus.inert = false;
    annuler(...panneaux());
    const cible = slug && r.travaux.find((t) => t.slug === slug);
    if (cible) choisir(cible);
    const premiere = $(".oeuvre", liste);
    if (premiere && (!document.activeElement || document.activeElement === document.body || p.contains(document.activeElement))) {
      premiere.focus({ preventScroll: true, focusVisible: clavier });
    }
    etat.occupe = false;
    if (etat.aFermer) fermer();
  }

  async function changer(r) {
    if (!etat.ouvert || !r || r === etat.rub || etat.occupe) return;
    etat.occupe = true;
    arreter();
    Object.assign(etat, { rub: r, choix: null });
    majRetour(r);
    history.replaceState(null, "", `#/${r.id}`);
    majCartel(null);
    montrerIllustration(r);
    await Promise.all([
      ...enteteCarte().map((n) => anim(n, [{ opacity: 0 }], { duration: 220, fill: "forwards" })),
      ...$$(".oeuvre", liste).map((l, i) => anim(l, [{ opacity: 0 }], { duration: 220, delay: i * 20, fill: "forwards" })),
    ]);
    entrerFocus(remplirFocus(r), 0, false);
    etat.occupe = false;
    if (etat.aFermer) fermer();
  }

  async function fermer() {
    if (!etat.ouvert) return;
    if (etat.occupe) {
      etat.aFermer = true;
      return;
    }
    etat.occupe = true;
    etat.aFermer = false;
    const lecteurVisible = Boolean(etat.lecteur) || cadre.classList.contains("mode-audio");
    arreter();
    etat.choix = null;
    marquer();
    majRetour(null);
    focus.inert = true;
    const r = etat.rub;
    const p = r.panneau;
    const source = $(".visuel", p);

    if (ms(1)) {
      // Le lecteur s'efface d'abord : c'est la photo qu'on voit qui repart.
      if (lecteurVisible) await attendre(320);
      accueil.classList.remove("cache");
      accueil.inert = false;
      let vers = rect(source);
      if (vers.top + vers.height < 0 || vers.top > innerHeight) {
        source.scrollIntoView({ block: "center" });
        vers = rect(source);
      }
      const de = rect(cadre);
      const clone = copieVolante(source, de);
      // La copie part du lecteur, sans titre ni voile, et arrive dans l'état
      // du panneau : titre affiché sur les écrans tactiles, caché sinon.
      const voileCible = getComputedStyle($(".voile", source)).opacity;
      const texte = $(".visuel-texte", clone);
      const voile = $(".voile", clone);
      voile.style.transition = "none";
      voile.style.opacity = "0";
      texte.style.opacity = "0";
      anim(texte, [{ opacity: 1 }], { duration: 450, delay: DUREE_VOL - 380, fill: "forwards" });
      anim(voile, [{ opacity: voileCible }], { duration: 450, delay: DUREE_VOL - 380, fill: "forwards" });
      source.style.visibility = "hidden";
      cadre.style.opacity = "0";
      sortirFocus();
      entrerPanneaux(p, 200);
      await voler(clone, de, vers);
      source.style.visibility = "";
      await image();
      clone.remove();
    } else {
      accueil.classList.remove("cache");
      accueil.inert = false;
      entrerPanneaux(p, 0);
    }

    focus.hidden = true;
    cadre.style.opacity = "";
    annuler(carte, cartel, ...enteteCarte(), ...$$(".oeuvre", liste));
    racine.classList.remove("verrou");
    const clavier = etat.clavier;
    Object.assign(etat, { ouvert: false, occupe: false, aFermer: false, pousse: false, clavier: false, rub: null, choix: null });
    p.focus({ preventScroll: true, focusVisible: clavier });
  }

  /* Fermer revient en arrière dans l'historique quand l'ouverture y avait
     ajouté une entrée : le bouton « retour » du téléphone ferme aussi. */
  function demanderFermeture(clavier = false) {
    if (!etat.ouvert) return;
    etat.clavier = clavier;
    if (etat.pousse && location.hash) history.back();
    else {
      history.replaceState(null, "", location.pathname + location.search);
      fermer();
    }
  }

  function lireHash() {
    const m = /^#\/([^/]+)(?:\/(.+))?$/.exec(location.hash);
    if (!m) return null;
    const rub = rubriques.find((r) => r.id === decodeURIComponent(m[1]));
    return rub ? { rub, slug: m[2] ? decodeURIComponent(m[2]) : null } : null;
  }

  addEventListener("popstate", () => {
    const h = lireHash();
    if (!h) {
      if (etat.ouvert) {
        etat.pousse = false;
        fermer();
      }
    } else if (!etat.ouvert) ouvrir(h.rub, { historique: false, slug: h.slug });
    else if (h.rub !== etat.rub) changer(h.rub);
  });

  retour.addEventListener("click", (e) => demanderFermeture(e.detail === 0));
  for (const lien of [$(".marque"), $(".barre-nom")]) {
    lien.addEventListener("click", (e) => {
      e.preventDefault();
      demanderFermeture(e.detail === 0);
    });
  }
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && etat.ouvert) {
      e.preventDefault();
      demanderFermeture(true);
    }
  });
  addEventListener("resize", () => {
    mesurerBarre();
    majDebord();
  });

  /* ------------------------------------------------------------------------
     Démarrage
     ------------------------------------------------------------------------ */

  async function demarrer() {
    if (!window.PORTFOLIO) console.warn("[portfolio] contenu.js est introuvable ou contient une erreur.");
    rubriques = preparerRubriques(await chargerCatalogue());
    construire();
    mesurerBarre();
    const h = lireHash();
    const polices = document.fonts && document.fonts.ready ? Promise.race([document.fonts.ready, attendre(900)]) : Promise.resolve();
    if (h) {
      polices.then(() => ouvrir(h.rub, { historique: false, vol: false, slug: h.slug }));
      return;
    }
    majRetour(null);
    // Entrée comme sur la référence : les photos glissent de la droite, l'une après l'autre.
    panneaux().forEach((n) => (n.style.opacity = "0"));
    const pretes = panneaux().map((n) => decodee($("img", n)));
    Promise.all([polices, ...pretes].map((x) => Promise.race([x, attendre(1200)]))).then(() =>
      panneaux().forEach((n, i) => {
        n.style.opacity = "";
        anim(n, [{ opacity: 0, transform: "translateX(200px)", offset: 0 }], { duration: 900, delay: 120 + i * 100, fill: "backwards" });
      }),
    );
    anim($(".barre"), [{ opacity: 0, offset: 0 }], { duration: 900 });
  }

  demarrer();
})();
