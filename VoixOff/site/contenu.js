/* ==========================================================================
   RÉGLAGES DU PORTFOLIO

   L'accueil montre trois cadres. Leur contenu ne se déclare pas ici : le site
   le trouve seul dans le dossier cadres/ (à côté de ce fichier), un dossier
   par cadre, et dans cadres/youtube.txt pour les vidéos YouTube.

     cadres/1 - À propos de moi/              les pages de la présentation,
                                              une image par page
     cadres/2 - Expériences et réalisations/  vidéos, audios, images
     cadres/3 - Voix off/                     audios, vidéos
     cadres/youtube.txt                       liens YouTube, rangés sous
                                              [Expériences et réalisations]
                                              ou [Voix off]

   Le nom d'un fichier devient son titre ; un numéro en tête (« 01 - … »)
   fixe l'ordre et ne s'affiche pas.

   Ici, chaque cadre :
     titre      le nom affiché
     dossier    son dossier dans cadres/, sans le numéro (par défaut, le
                titre) ; c'est aussi le nom à écrire entre crochets dans
                youtube.txt
     affichage  "diaporama" : les images du dossier se font défiler dans le
                lecteur, avec des flèches ; "liste" (par défaut) : une liste
                de réalisations à côté d'un lecteur
     intro      une phrase sous le titre (facultatif)
     image      la photo du cadre, déposée dans medias/
     cadrage    le point de la photo à garder visible quand elle est recadrée :
                position horizontale puis verticale, de "0%" (bord gauche /
                haut) à "100%" (bord droit / bas). Par défaut "50% 50%".
   ========================================================================== */

window.PORTFOLIO = {
  nom: "Anne-Katy MILIDJI",
  // Sous le nom. Une barre « / » sépare les deux métiers : chacun a sa ligne.
  metier: "Responsable marketing & communication / Voix off professionnel",
  email: "contact@exemple.fr",
  liens: [
    { libelle: "LinkedIn", url: "https://www.linkedin.com/" },
    { libelle: "TikTok", url: "https://www.tiktok.com/" },
  ],

  cadres: [
    {
      titre: "À propos de moi",
      dossier: "À propos de moi",
      affichage: "diaporama",
      intro: "Ma présentation, page par page.",
      image: "medias/a-propos-de-moi.jpg",
      cadrage: "50% 43%",
    },
    {
      titre: "Expériences et réalisations",
      dossier: "Expériences et réalisations",
      intro: "Marketing et communication : campagnes, contenus, projets.",
      image: "medias/experiences.jpg",
      cadrage: "50% 72%",
    },
    {
      titre: "Voix off",
      dossier: "Voix off",
      intro: "Publicité, corporate, documentaire, livres audio.",
      image: "medias/voix-off.jpg",
      cadrage: "38% 50%",
    },
  ],
};
