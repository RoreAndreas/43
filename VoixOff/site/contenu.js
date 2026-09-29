/* ==========================================================================
   CONTENU DU PORTFOLIO — le seul fichier à modifier.

   Chaque travail est un bloc { ... } dans la liste « travaux ». Le type de
   média se déduit du lien :

     - un lien YouTube (youtube.com/watch?v=…, youtu.be/…, youtube.com/shorts/…)
       → la vidéo se regarde directement sur le site ;
     - un fichier vidéo (.mp4, .webm, .mov) déposé dans le dossier medias/
       → lien: "medias/mon-film.mp4" ;
     - un fichier audio (.mp3, .wav, .m4a, .ogg) déposé dans medias/
       → lien: "medias/ma-demo.mp3" : il se lit sur place, avec sa forme d'onde.

   Champs d'un travail (seuls « titre » et « lien » sont obligatoires) :
     titre        le nom affiché
     lien         YouTube ou chemin du fichier
     client       la marque, la chaîne, l'éditeur…
     categorie    sert aux filtres (Publicité, Documentaire, Livre audio…)
     annee        2026
     description  une ou deux phrases, affichées pendant la lecture
     image        vignette personnalisée (conseillée pour les fichiers vidéo)
     duree        "0:30" — affichée sur la vignette (les audios la calculent seuls)
     vedette      true pour mettre ce travail en grand, en tête de page
                  (une bande démo, par exemple). Un seul à la fois.

   L'ordre de la liste est l'ordre d'affichage.
   ========================================================================== */

window.PORTFOLIO = {
  nom: "Prénom Nom",
  metier: "Voix off",
  accroche:
    "Une voix posée et chaleureuse pour la publicité, le documentaire et la narration.",

  // Un paragraphe par chaîne de caractères. Laissez [] pour masquer la section.
  apropos: [
    "Quelques lignes sur vous : votre timbre, vos langues, votre home studio, les marques qui vous ont fait confiance.",
  ],

  email: "contact@exemple.fr",
  telephone: "", // facultatif, par exemple "+33 6 00 00 00 00"
  invitation: "Un texte à faire vivre ?",
  liens: [
    { libelle: "LinkedIn", url: "https://www.linkedin.com/" },
    { libelle: "Instagram", url: "https://www.instagram.com/" },
  ],

  // "auto" suit le réglage clair / sombre de l'appareil du visiteur.
  theme: "auto", // "auto", "clair" ou "sombre"

  // ------------------------------------------------------------------------
  // Travaux. Les liens ci-dessous sont des exemples (courts métrages libres de
  // la Blender Foundation) : remplacez-les par les vôtres.
  // ------------------------------------------------------------------------
  travaux: [
    {
      titre: "Bande démo 2026",
      categorie: "Démo",
      annee: 2026,
      lien: "https://www.youtube.com/watch?v=aqz-KE-bpKQ",
      description:
        "Une minute pour entendre la palette : publicité, documentaire, narration, personnage.",
      vedette: true,
    },
    {
      titre: "Spot TV — lancement produit",
      client: "Marque (exemple)",
      categorie: "Publicité",
      annee: 2026,
      lien: "https://youtu.be/eRsGyueVLvQ",
    },
    {
      titre: "Les gardiens de la mangrove",
      client: "Chaîne (exemple)",
      categorie: "Documentaire",
      annee: 2025,
      lien: "https://www.youtube.com/watch?v=R6MlUcmOul8",
      description: "Narration d'un documentaire animalier de 52 minutes.",
    },
    {
      titre: "Extrait de livre audio",
      client: "Éditeur (exemple)",
      categorie: "Livre audio",
      annee: 2025,
      lien: "medias/exemple-audio.mp3",
    },
    {
      titre: "Film institutionnel",
      client: "Entreprise (exemple)",
      categorie: "Corporate",
      annee: 2025,
      lien: "https://www.youtube.com/watch?v=WhZLL-lHwaU",
    },
    {
      titre: "Bande-annonce",
      client: "Studio (exemple)",
      categorie: "Publicité",
      annee: 2024,
      lien: "https://www.youtube.com/watch?v=Y-rmzh0PI3c",
    },
    {
      titre: "Voix de personnage",
      client: "Studio (exemple)",
      categorie: "Animation",
      annee: 2024,
      lien: "https://www.youtube.com/watch?v=mN0zPOpADL4",
    },
  ],
};
