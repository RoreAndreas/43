/* ==========================================================================
   Portfolio — rendu et interactions.

   Les réglages viennent de contenu.js (window.PORTFOLIO), le contenu de
   catalogue.json, qu'écrit inventaire.py à partir du dossier cadres/ (les
   fichiers déposés) et de cadres/youtube.txt (les liens YouTube) : rien à
   modifier ici.

   Accueil : trois cadres, chacun sa photo. Au clic, la photo s'envole et
   devient le lecteur, à droite, pendant que les autres se fondent dans le
   noir et que la liste apparaît à gauche, sur la même ligne. Deux sortes de
   cadres :
     - diaporama : le lecteur prend le format des pages, aussi grand que
       l'écran le permet, les miniatures dessous ; une fois le cadre ouvert,
       les pages se posent sur la photo et se font défiler avec les flèches,
       le clavier, le doigt ou les miniatures ;
     - liste : choisir une réalisation la lit dans le lecteur, à la place de
       la photo. Un seul média joue à la fois.
   « Retour », Échap ou le retour du navigateur ramènent la photo à sa place.
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
     Le contenu : catalogue.json
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

  /* Illustration de repli, pour un cadre sans photo : dégradé bleu et barres
     d'onde, toujours les mêmes pour un même cadre. */
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

  /* Mêmes règles que inventaire.py : comparaison sans accents, casse ni
     espaces en trop, et numéro de rang en tête ignoré (« 1 - À propos de moi »). */
  const cle = (t) =>
    String(t || "")
      .normalize("NFD")
      .replace(/\p{Diacritic}/gu, "")
      .toLowerCase()
      .split(/\s+/)
      .filter(Boolean)
      .join(" ");
  const sansRang = (t) => String(t || "").replace(/^\s*\d{1,3}(?:\s*[-–—_.)]\s*|\s+)(?=\S)/, "");

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
    if (["image", "video", "audio"].includes(brut.type) && brut.fichier) {
      // Les dimensions d'une image, lues par inventaire.py dans son en-tête.
      const format = brut.largeur > 0 && brut.hauteur > 0 ? { l: brut.largeur, h: brut.hauteur } : null;
      return { ...commun, type: brut.type, lien: brut.fichier, format };
    }
    return null;
  }

  const estDiaporama = (r) => Boolean(r) && r.mode === "diaporama" && r.travaux.length > 0;

  /* Les cadres de contenu.js, garnis du contenu de leur dossier. */
  function preparerCadres(catalogue) {
    const source = (catalogue && (catalogue.cadres || catalogue.rubriques)) || {};
    const parDossier = new Map(Object.entries(source).map(([nom, liste]) => [cle(sansRang(nom)), liste]));
    const idsPris = new Set();
    const reglages = Array.isArray(P.cadres) ? P.cadres : Array.isArray(P.rubriques) ? P.rubriques : [];
    return reglages.map((r, index) => {
      const rub = {
        titre: String(r.titre || "Cadre"),
        intro: r.intro || "",
        index,
        cadrage: r.cadrage || "50% 50%",
        // « carrousel » : l'ancien nom de l'affichage en diaporama.
        mode: r.affichage === "diaporama" || r.affichage === "carrousel" ? "diaporama" : "liste",
      };
      rub.id = slugifier(r.id || r.titre, idsPris);
      const pris = new Set();
      const liste = parDossier.get(cle(sansRang(r.dossier || r.titre))) || [];
      rub.travaux = liste.map((t) => realisation(t, rub, pris)).filter(Boolean);
      if (rub.mode === "diaporama") {
        const autres = rub.travaux.filter((t) => t.type !== "image");
        if (autres.length) console.info(`[portfolio] « ${rub.titre} » est un diaporama : ${pluriel(autres.length, "fichier")} autre(s) qu'une image ignoré(s).`);
        rub.travaux = rub.travaux.filter((t) => t.type === "image");
        // Le lecteur prendra le format de la première page.
        rub.format = (rub.travaux.find((t) => t.format) || {}).format || null;
      }
      const yt = rub.travaux.find((t) => t.yt);
      rub.image = r.image
        ? { src: r.image }
        : rub.mode === "diaporama" && rub.travaux[0]
          ? { src: rub.travaux[0].lien }
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
     Pages : des images qui se remplacent en fondu enchaîné
     ------------------------------------------------------------------------ */

  /* Une image entière. Dans une liste, elle est posée sur un fond flou tiré
     d'elle-même quand elle n'a pas le format du lecteur (`flou`) ; dans un
     diaporama, le lecteur a déjà le format des pages : elle le remplit
     (`remplir`), sans bandes ni flou. */
  function diapo(item, { alt = item.titre, flou = true, remplir = false } = {}) {
    return el(
      "span",
      { class: "diapo" },
      flou && el("img", { class: "diapo-fond", src: item.lien, alt: "", "aria-hidden": "true", decoding: "async", draggable: "false" }),
      el("img", { class: remplir ? "diapo-image remplie" : "diapo-image", src: item.lien, alt, decoding: "async", draggable: "false" }),
    );
  }

  /* Deux formats à 2 % près : la page remplit le lecteur sans rien perdre de visible. */
  const proche = (a, b) => Boolean(a && b) && Math.abs((a.l / a.h) / (b.l / b.h) - 1) < 0.02;

  function creerPages(rub) {
    const d = {
      index: -1,
      jeton: 0,
      noeud: el("span", { class: "diapos" }),
      /* Montre la page i ; la promesse est tenue quand elle est prête. */
      async montrer(i, { instant = false } = {}) {
        const n = rub.travaux.length;
        if (!n || i < 0 || i >= n || i === d.index) return;
        d.index = i;
        const jeton = ++d.jeton;
        const item = rub.travaux[i];
        const s = diapo(item, { alt: `Page ${i + 1} sur ${n}`, flou: false, remplir: proche(item.format, rub.format) });
        s.style.opacity = "0";
        d.noeud.append(s);
        const img = $(".diapo-image", s);
        await decodee(img);
        if (jeton !== d.jeton) {
          s.remove(); // une autre page a été demandée entre-temps
          return;
        }
        // Sans dimensions au catalogue, la première page donne son format au lecteur.
        if (!rub.format && img.naturalWidth) {
          rub.format = { l: img.naturalWidth, h: img.naturalHeight };
          if (etat.rub === rub) poserFormat(rub);
        }
        const anciennes = [...d.noeud.children].filter((x) => x !== s);
        s.style.opacity = "";
        if (instant || !ms(1)) anciennes.forEach((x) => x.remove());
        else {
          // Fondu enchaîné : la nouvelle page se pose sur l'ancienne, qui reste
          // en place jusqu'au bout. Le lecteur n'est jamais vide, et rien ne
          // dépasse de son cadre.
          anim(s, [{ opacity: 0, transform: "scale(1.012)", offset: 0 }], { duration: 650 }).then(() => anciennes.forEach((x) => x.remove()));
        }
        // Les voisines se chargent pendant qu'on regarde celle-ci.
        for (const j of [i + 1, i - 1]) if (j >= 0 && j < n) new Image().src = rub.travaux[j].lien;
      },
    };
    return d;
  }

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
  const miniatures = $(".miniatures");
  const enteteCarte = () => [$(".carte-tete"), $(".carte-titre"), $(".carte-intro")];

  const etat = {
    ouvert: false, // un cadre est ouvert (ou s'ouvre, ou se ferme)
    occupe: false, // une transition est en cours
    aFermer: false, // fermeture demandée pendant une transition
    pousse: false, // l'ouverture a ajouté une entrée à l'historique
    clavier: false, // la dernière commande venait du clavier
    rub: null,
    choix: null, // la réalisation (ou la page) choisie
    lecteur: null, // ce qui est monté dans le lecteur : vidéo, image, diaporama
  };

  function construire() {
    const nom = String(P.nom || "").trim();
    // « Responsable marketing & communication / Voix off professionnel » :
    // chaque métier sur sa ligne, sous le nom.
    const metiers = String(P.metier || "")
      .split("/")
      .map((m) => m.trim())
      .filter(Boolean);
    document.title = [nom, metiers.join(" / ")].filter(Boolean).join(" — ") || document.title;
    $(".barre-nom-texte").textContent = nom;
    $(".barre-metier").replaceChildren(...metiers.map((m) => el("span", { class: "barre-metier-ligne", text: m })));

    const droite = [];
    for (const l of Array.isArray(P.liens) ? P.liens : []) {
      if (l && l.url) droite.push(el("a", { href: l.url, target: "_blank", rel: "noopener", text: l.libelle || l.url }));
    }
    if (P.email) {
      // Sur les écrans étroits, le mot « Contact » laisse place à une enveloppe.
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
        const n = pluriel(r.travaux.length, r.mode === "diaporama" ? "page" : "réalisation");
        const visuel = el(
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
        );
        const b = el("button", { type: "button", class: "panneau", "data-id": r.id, "aria-label": `${r.titre} — ${n}` }, visuel);
        b.addEventListener("click", (e) => ouvrir(r, { clavier: e.detail === 0 }));
        // Un diaporama charge sa première page dès le survol : elle est prête
        // quand la photo se pose dans le lecteur.
        if (estDiaporama(r)) b.addEventListener("pointerenter", () => (new Image().src = r.travaux[0].lien), { once: true });
        r.panneau = b;
        return b;
      }),
    );
  }

  /* Le bouton retour s'affiche dans un cadre ouvert, et seulement là. */
  function majRetour(r) {
    retour.classList.toggle("visible", Boolean(r));
    barre.classList.toggle("en-rubrique", Boolean(r));
  }

  /* L'en-tête fixe : sa hauteur réelle règle l'espace qui lui est laissé au
     haut de la page, et la position du lecteur collant sur mobile. */
  function mesurerBarre() {
    const h = barre.offsetHeight;
    racine.style.setProperty("--barre", `${h}px`);
    racine.style.setProperty("--haut", `${h + (innerWidth < 900 ? 14 : 20)}px`);
  }

  /* ------------------------------------------------------------------------
     La liste
     ------------------------------------------------------------------------ */

  function remplirFocus(r) {
    annuler(...enteteCarte(), ...$$(".oeuvre", liste));
    const diaporama = r.mode === "diaporama";
    $(".carte-etiquette").textContent = diaporama ? "Sommaire" : "Réalisations";
    $(".carte-titre").textContent = r.titre;
    $(".carte-compte").textContent = deux(r.travaux.length);
    const intro = $(".carte-intro");
    intro.textContent = r.intro;
    intro.hidden = !r.intro;
    liste.replaceChildren(...(diaporama ? [] : r.travaux.map((item, i) => el("li", {}, ligne(item, i)))));
    liste.hidden = diaporama || !r.travaux.length;
    miniatures.replaceChildren(...(diaporama ? r.travaux.map((item, i) => miniature(item, i, r.travaux.length)) : []));
    const vide = $(".carte-vide");
    vide.textContent = diaporama ? "Aucune page pour l'instant" : "Aucune réalisation pour l'instant";
    vide.hidden = r.travaux.length > 0;
    $(".cartel-invite").hidden = !r.travaux.length; // rien à sélectionner
    liste.scrollTop = 0;
    miniatures.scrollLeft = 0;
    requestAnimationFrame(majDebord);
    return diaporama ? $$(".miniature", miniatures) : $$(".oeuvre", liste);
  }

  /* Une miniature de page, sous le lecteur du diaporama. */
  function miniature(item, i, n) {
    const b = el(
      "button",
      { type: "button", class: "miniature", "data-slug": item.slug, "aria-current": "false", "aria-label": `Page ${i + 1} sur ${n}` },
      el("img", { src: item.lien, alt: "", decoding: "async", fetchpriority: "low", draggable: "false" }),
    );
    b.addEventListener("click", () => allerPage(i, { manuel: true }));
    return b;
  }

  function ligne(item, i) {
    const diaporama = item.rub.mode === "diaporama";
    const texteInfo = diaporama ? "" : item.type === "youtube" ? "YouTube" : item.type === "image" ? "Image" : item.dureeTexte || "";
    const info = el("span", { class: "oeuvre-info", text: texteInfo });
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
    b.addEventListener("click", () => (diaporama ? allerPage(i, { manuel: true }) : choisir(item, { auto: true })));
    if (item.yt) b.addEventListener("pointerenter", prechauffer, { once: true });
    else if (!diaporama && (item.type === "audio" || item.type === "video") && !item.dureeTexte) mesurerDuree(item, info);
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
     Le lecteur : la photo du cadre, puis la réalisation choisie
     ------------------------------------------------------------------------ */

  /* Pose la photo d'un cadre dans le lecteur, en fondu enchaîné. La promesse
     est tenue quand elle est prête à s'afficher. */
  function montrerIllustration(r, instant = false) {
    if (illustration.dataset.cle === r.image.src) return Promise.resolve();
    illustration.dataset.cle = r.image.src;
    const img = creerImg(r.image, r.cadrage);
    const prete = decodee(img);
    const anciens = [...illustration.children];
    if (instant || !ms(1)) {
      illustration.replaceChildren(img);
      return prete;
    }
    img.style.opacity = "0";
    illustration.append(img);
    prete.then(() => {
      if (!img.isConnected) return;
      img.style.opacity = "";
      img
        .animate([{ opacity: 0, transform: "scale(1.02)" }, { opacity: 1, transform: "none" }], { duration: 800, easing: EASE })
        .finished.then(() => anciens.forEach((n) => n.remove()))
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
    const actif = (b) => Boolean(etat.choix) && b.dataset.slug === etat.choix.slug;
    for (const b of $$(".oeuvre", liste)) {
      b.setAttribute("aria-current", String(actif(b)));
      b.classList.toggle("joue", actif(b) && joue);
    }
    for (const b of $$(".miniature", miniatures)) {
      b.setAttribute("aria-current", String(actif(b)));
      // La miniature en cours reste visible quand la bande déborde : la bande
      // défile seule, jamais la page.
      if (actif(b) && miniatures.scrollWidth > miniatures.clientWidth) {
        miniatures.scrollTo({ left: b.offsetLeft - (miniatures.clientWidth - b.offsetWidth) / 2, behavior: Diapo.pages && ms(1) ? "smooth" : "auto" });
      }
    }
  }

  function majCartel(item, instant = false) {
    const remplir = () => {
      cartel.classList.toggle("vide", !item);
      if (!item) return;
      const r = item.rub;
      const diaporama = estDiaporama(r);
      $(".cartel-titre").textContent = diaporama ? `Page ${r.travaux.indexOf(item) + 1} sur ${r.travaux.length}` : item.titre;
      const meta = diaporama
        ? []
        : item.type === "youtube"
          ? [item.auteur, "YouTube"]
          : [{ audio: "Audio", video: "Vidéo", image: "Image" }[item.type], item.dureeTexte];
      const texte = meta.filter(Boolean).join(" · ");
      $(".cartel-meta").textContent = texte;
      $(".cartel-meta").hidden = !texte;
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

  /* Coupe ce qui joue, en fondu ; la photo du cadre réapparaît. */
  function arreter() {
    if (etat.lecteur) demonterLecteur();
    const it = Audio_.item;
    Audio_.item = null;
    if (it && it.audio && !it.audio.paused) fondreAudio(it.audio);
    Diapo.rub = null;
    Diapo.pages = null;
    cadre.classList.remove("mode-audio", "mode-diaporama", "charge");
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
    } else if (item.type === "image") {
      // Une image entière, sur son propre fond flou, comme une page.
      l = diapo(item);
      l.classList.add("lecteur");
      decodee($(".diapo-image", l)).then(() => pret(l));
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
     Le diaporama du cadre ouvert : flèches, clavier, glissé du doigt
     ------------------------------------------------------------------------ */

  const Diapo = {
    rub: null,
    pages: null,
    index: 0,
    precedente: $(".diaporama-precedente"),
    suivante: $(".diaporama-suivante"),
  };

  /* Le lecteur d'un diaporama prend le format de ses pages, qui le
     remplissent exactement : ni bandes, ni flou, ni recadrage. Il occupe
     toute la place sous l'en-tête, ses miniatures dessous, jamais plus
     larges que lui (style.css). En attendant la première page, 16/9. */
  function poserFormat(r) {
    const diaporama = estDiaporama(r);
    const f = (diaporama && r.format) || { l: 16, h: 9 };
    focus.classList.toggle("mode-diaporama", diaporama);
    focus.style.setProperty("--rw", String(f.l));
    focus.style.setProperty("--rh", String(f.h));
    focus.style.setProperty("--n", String(diaporama ? r.travaux.length : 1));
  }

  /* Prépare le diaporama d'un cadre, à la page `index` : sommaire et
     légende d'abord, pendant que la photo s'envole ; les pages se posent
     sur elle quand elle est arrivée (monterDiaporama). */
  function preparerDiaporama(r, index) {
    Object.assign(Diapo, { rub: r, pages: null, index: borner(index, 0, r.travaux.length - 1) });
    etat.choix = r.travaux[Diapo.index];
    marquer();
    majCartel(etat.choix, true);
  }

  function monterDiaporama() {
    const r = Diapo.rub;
    if (!r || !etat.ouvert) return;
    const pages = creerPages(r);
    const l = el("div", { class: "lecteur diaporama" }, pages.noeud);
    l._joue = false;
    Diapo.pages = pages;
    etat.lecteur = l;
    cadre.classList.add("charge", "mode-diaporama");
    scene.append(l);
    pages.montrer(Diapo.index, { instant: true }).then(() => pret(l));
    majFleches();
  }

  /* `manuel` : le visiteur a choisi la page ; elle s'inscrit dans l'adresse. */
  function allerPage(i, { manuel = false } = {}) {
    const r = Diapo.rub;
    if (!r || !Diapo.pages || !etat.ouvert || i < 0 || i >= r.travaux.length || i === Diapo.index) return;
    Diapo.index = i;
    Diapo.pages.montrer(i);
    etat.choix = r.travaux[i];
    marquer();
    majCartel(etat.choix);
    if (manuel) majHash();
    majFleches();
    if (miniatures.contains(document.activeElement)) {
      const b = $('.miniature[aria-current="true"]', miniatures);
      if (b && b !== document.activeElement) b.focus({ preventScroll: true });
    }
  }

  /* Pas de boucle : la première page n'a pas de précédente, la dernière pas
     de suivante. */
  function majFleches() {
    const n = Diapo.rub ? Diapo.rub.travaux.length : 0;
    Diapo.precedente.disabled = Diapo.index <= 0;
    Diapo.suivante.disabled = Diapo.index >= n - 1;
  }

  Diapo.precedente.addEventListener("click", () => allerPage(Diapo.index - 1, { manuel: true }));
  Diapo.suivante.addEventListener("click", () => allerPage(Diapo.index + 1, { manuel: true }));

  // Sur écran tactile : glisser vers la gauche ou la droite.
  let glisse = null;
  cadre.addEventListener("pointerdown", (e) => {
    glisse = Diapo.pages && e.pointerType !== "mouse" && !e.target.closest("button") ? { x: e.clientX, y: e.clientY } : null;
  });
  cadre.addEventListener("pointerup", (e) => {
    if (!glisse) return;
    const dx = e.clientX - glisse.x;
    const dy = e.clientY - glisse.y;
    glisse = null;
    if (Math.abs(dx) > 40 && Math.abs(dx) > 1.5 * Math.abs(dy)) allerPage(Diapo.index + (dx < 0 ? 1 : -1), { manuel: true });
  });
  cadre.addEventListener("pointercancel", () => (glisse = null));

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
     Transitions entre l'accueil et un cadre
     ------------------------------------------------------------------------ */

  const panneaux = () => rubriques.map((r) => r.panneau);

  /* Les autres cadres se fondent dans le noir, sur place. */
  function sortirPanneaux(p) {
    panneaux().forEach((n) => {
      if (n !== p) anim(n, [{ opacity: 0, transform: "scale(.96)" }], { duration: 650, fill: "forwards" });
    });
  }

  /* Au retour, ils en ressortent, du plus proche au plus lointain. */
  function entrerPanneaux(p, delai) {
    const k = panneaux().indexOf(p);
    panneaux().forEach((n, i) => {
      annuler(n);
      if (n !== p) anim(n, [{ opacity: 0, transform: "scale(.96)", offset: 0 }], { duration: 900, delay: delai + Math.abs(i - k) * 90, fill: "backwards" });
    });
  }

  /* La liste apparaît pendant que la photo s'installe, puis ses lignes se
     déroulent. `complet` : ouverture, et non changement de cadre (la liste
     est alors déjà là, seul son contenu change). */
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
    anim(miniatures, [{ opacity: 0, transform: "translateY(10px)" }], { duration: 320, fill: "forwards" });
  }

  /* Recopie sur la copie volante l'état affiché d'un élément du cadre,
     survol compris : hors de l'accueil, la copie ne serait plus survolée. */
  function figer(source, clone, sel, props) {
    const s = getComputedStyle($(sel, source));
    const c = $(sel, clone);
    c.style.transition = "none";
    for (const prop of props) c.style[prop] = s[prop];
  }

  /* Copie volante de la photo d'un cadre. */
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

  /* La page de l'adresse (« …/a-propos-de-moi/mon-parcours »), sinon la première. */
  const pageDepart = (r, slug) => Math.max(0, slug ? r.travaux.findIndex((t) => t.slug === slug) : 0);

  async function ouvrir(r, { historique = true, vol = true, slug = null, clavier = false } = {}) {
    if (!r || etat.ouvert || etat.occupe) return;
    Object.assign(etat, { ouvert: true, occupe: true, aFermer: false, rub: r, choix: null, pousse: historique });
    if (historique) history.pushState(null, "", `#/${r.id}`);

    racine.classList.add("verrou");
    majRetour(r);
    const lignes = remplirFocus(r);
    cadre.classList.remove("mode-audio", "mode-diaporama", "charge");
    const prete = montrerIllustration(r, true);
    // La place du lecteur (celle d'un diaporama n'est pas celle d'une
    // liste) : c'est là que la photo doit se poser en vol.
    poserFormat(r);
    focus.hidden = false;
    focus.scrollTop = 0;
    if (estDiaporama(r)) preparerDiaporama(r, pageDepart(r, slug));
    else majCartel(null, true);
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
    if (estDiaporama(r)) {
      // La photo est posée : les pages viennent la recouvrir.
      monterDiaporama();
      if (slug && r.travaux.some((t) => t.slug === slug)) majHash();
    } else {
      const cible = slug && r.travaux.find((t) => t.slug === slug);
      if (cible) choisir(cible);
    }
    const premiere = $('.miniature[aria-current="true"]', miniatures) || $('.oeuvre[aria-current="true"]', liste) || $(".oeuvre", liste);
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
    montrerIllustration(r);
    if (!estDiaporama(r)) majCartel(null);
    await Promise.all([
      ...enteteCarte().map((n) => anim(n, [{ opacity: 0 }], { duration: 220, fill: "forwards" })),
      ...[...$$(".oeuvre", liste), ...$$(".miniature", miniatures)].map((l, i) => anim(l, [{ opacity: 0 }], { duration: 220, delay: i * 20, fill: "forwards" })),
    ]);
    const lignes = remplirFocus(r);
    poserFormat(r);
    if (estDiaporama(r)) {
      preparerDiaporama(r, 0);
      monterDiaporama();
    }
    entrerFocus(lignes, 0, false);
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
      // du cadre d'accueil : titre affiché sur les écrans tactiles, caché sinon.
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
    focus.classList.remove("mode-diaporama");
    cadre.style.opacity = "";
    annuler(carte, cartel, miniatures, ...enteteCarte(), ...$$(".oeuvre", liste), ...$$(".miniature", miniatures));
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
    if (!etat.ouvert) return;
    if (e.key === "Escape") {
      e.preventDefault();
      demanderFermeture(true);
      return;
    }
    // Dans un diaporama, les flèches gauche et droite tournent les pages.
    if ((e.key === "ArrowLeft" || e.key === "ArrowRight") && Diapo.pages && !e.altKey && !e.ctrlKey && !e.metaKey && !e.target.closest(".onde, input, textarea")) {
      e.preventDefault();
      allerPage(Diapo.index + (e.key === "ArrowRight" ? 1 : -1), { manuel: true });
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
    rubriques = preparerCadres(await chargerCatalogue());
    construire();
    mesurerBarre();
    const h = lireHash();
    const polices = document.fonts && document.fonts.ready ? Promise.race([document.fonts.ready, attendre(900)]) : Promise.resolve();
    polices.then(mesurerBarre); // le nom, dans sa police, peut changer la hauteur de l'en-tête
    if (h) {
      polices.then(() => ouvrir(h.rub, { historique: false, vol: false, slug: h.slug }));
      return;
    }
    majRetour(null);
    // Entrée comme sur la référence : les cadres glissent de la droite, l'un après l'autre.
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
