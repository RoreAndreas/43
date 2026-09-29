/* ==========================================================================
   RÉGLAGES DU PORTFOLIO

   Les réalisations ne se déclarent pas ici : le site les trouve seul, dans
   le dossier realisations/ (à côté de ce fichier), et en deux sources :

     - les fichiers déposés dans le dossier de chaque rubrique
       (realisations/Corporate/, realisations/Documentaire/…) : vidéos .mp4,
       .webm, .mov ; audios .mp3, .wav, .m4a. Le titre affiché est le nom du
       fichier. Un numéro en tête (« 01 - Mon film.mp4 ») fixe l'ordre et
       ne s'affiche pas ;
     - les liens de realisations/youtube.txt, rangés sous le nom de leur
       rubrique : [Corporate], [Documentaire]… Le titre est celui de la
       vidéo sur YouTube.

   Ici, chaque rubrique :
     titre     le nom affiché
     dossier   son dossier dans realisations/ (par défaut, le titre) ; c'est
               aussi le nom à écrire entre crochets dans youtube.txt
     intro     une phrase sous le titre (facultatif)
     image     la photo de la rubrique, déposée dans medias/
     cadrage   le point de la photo à garder visible quand elle est recadrée :
               position horizontale puis verticale, de "0%" (bord gauche /
               haut) à "100%" (bord droit / bas). Par défaut "50% 50%".
   ========================================================================== */

window.PORTFOLIO = {
  nom: "Anne-Katy MILIDJI",
  metier: "Voix off professionnel",
  email: "contact@exemple.fr",
  liens: [
    { libelle: "LinkedIn", url: "https://www.linkedin.com/" },
    { libelle: "TikTok", url: "https://www.tiktok.com/" },
  ],

  rubriques: [
    {
      titre: "Corporate",
      dossier: "Corporate",
      intro: "Films institutionnels, motion design, présentations produit.",
      image: "medias/corporate.jpg",
      cadrage: "50% 43%",
    },
    {
      titre: "Documentaire",
      dossier: "Documentaire",
      intro: "Narration pour la télévision et les plateformes.",
      image: "medias/documentaire.jpg",
      cadrage: "38% 30%",
    },
    {
      titre: "Piste audio",
      dossier: "Piste audio",
      intro: "Livres audio, spots radio, messages d'attente.",
      image: "medias/piste-audio.jpg",
      cadrage: "38% 50%",
    },
  ],
};
