/* ==========================================================================
   RÉGLAGES DU PORTFOLIO

   L'accueil montre trois cadres. Leur contenu ne se déclare pas ici : le site
   le trouve seul dans le dossier cadres/ (à côté de ce fichier), un dossier
   par cadre, et dans cadres/youtube.txt pour les vidéos YouTube.

     cadres/1 - Présentation/                 les images du carrousel
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
     affichage  "carrousel" : les images défilent, sur l'accueil comme dans
                le cadre ouvert ; "liste" (par défaut) : une liste de
                réalisations à côté d'un lecteur
     ajustement pour un carrousel : "entier" (par défaut) montre chaque image
                en entier, sur un fond flou ; "couvrir" la recadre pour
                remplir le cadre, mieux pour des photos que des diapositives
     intro      une phrase sous le titre (facultatif)
     image      la photo du cadre, déposée dans medias/ (un carrousel montre
                ses propres images)
     cadrage    le point de la photo à garder visible quand elle est recadrée :
                position horizontale puis verticale, de "0%" (bord gauche /
                haut) à "100%" (bord droit / bas). Par défaut "50% 50%".
   ========================================================================== */

window.PORTFOLIO = {
  nom: "Anne-Katy MILIDJI",
  // Sous le nom. Une barre « / » sépare les deux métiers : sur les écrans
  // étroits, chacun passe sur sa ligne.
  metier: "Responsable marketing & communication / Voix off professionnel",
  email: "contact@exemple.fr",
  liens: [
    { libelle: "LinkedIn", url: "https://www.linkedin.com/" },
    { libelle: "TikTok", url: "https://www.tiktok.com/" },
  ],

  cadres: [
    {
      titre: "Présentation",
      dossier: "Présentation",
      affichage: "carrousel",
      intro: "Parcours et savoir-faire, en quelques images.",
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
