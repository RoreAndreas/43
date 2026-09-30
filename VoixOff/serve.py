"""Aperçu local du portfolio : python serve.py, puis http://localhost:8000.

Le catalogue des réalisations est refait à chaque chargement de la page : un
fichier déposé dans site/cadres/, un lien ajouté à cadres/youtube.txt
apparaissent au simple rechargement.

Le serveur de base de Python ignore les requêtes partielles (Range) : le
navigateur ne pourrait pas avancer dans un extrait audio. Celui-ci les gère.
"""

import os
import re
import sys
import urllib.parse
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

import inventaire

SITE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "site")


class Gestionnaire(SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        self.send_header("Accept-Ranges", "bytes")
        super().end_headers()

    def send_head(self):
        self._reste = None
        if urllib.parse.urlsplit(self.path).path == "/catalogue.json":
            try:
                inventaire.generer(bavard=False)
            except Exception as erreur:  # le catalogue précédent reste servi
                self.log_error("inventaire : %s", erreur)
        plage = re.fullmatch(r"bytes=(\d*)-(\d*)", self.headers.get("Range", ""))
        chemin = self.translate_path(self.path)
        if not plage or not os.path.isfile(chemin):
            return super().send_head()
        taille = os.path.getsize(chemin)
        debut, fin = plage.groups()
        if debut:
            debut, fin = int(debut), min(int(fin or taille - 1), taille - 1)
        else:
            debut, fin = max(0, taille - int(fin)), taille - 1
        f = open(chemin, "rb")
        f.seek(debut)
        self.send_response(206)
        self.send_header("Content-Type", self.guess_type(chemin))
        self.send_header("Content-Range", f"bytes {debut}-{fin}/{taille}")
        self.send_header("Content-Length", str(fin - debut + 1))
        self.end_headers()
        self._reste = fin - debut + 1
        return f

    def copyfile(self, source, sortie):
        if self._reste is None:
            return super().copyfile(source, sortie)
        reste = self._reste
        while reste > 0:
            bloc = source.read(min(65536, reste))
            if not bloc:
                break
            sortie.write(bloc)
            reste -= len(bloc)


if __name__ == "__main__":
    sys.stdout.reconfigure(errors="replace")  # console Windows sans UTF-8
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
    inventaire.generer()
    print(f"Portfolio : http://localhost:{port}")
    ThreadingHTTPServer(("127.0.0.1", port), partial(Gestionnaire, directory=SITE)).serve_forever()
