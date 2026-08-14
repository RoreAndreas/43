"""
Serveur local de développement.

    python serve.py            # http://localhost:8000

La page distribuée est celle produite par `build_static.py` : elle calcule tout
dans le navigateur et n'a besoin d'aucun serveur. `serve.py` sert à deux choses
en local :

  * prévisualiser la page sans reconstruire le fichier `dist/index.html` ;
  * produire le classeur Excel, qui lui réclame Python (openpyxl).

Routes :
    GET /              la page, avec le jeu de données du jour
    GET /export.xlsx   classeur Excel pour les paramètres passés en requête
"""

import argparse
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

import wacc_core
from wacc_html import render_page

DEFAULT_PORT = 8000

TEXT_KEYS = ("maturity", "country", "industry")
FLOAT_KEYS = ("d", "e", "inflation_ref", "inflation_local")

DATASET = None  # rempli au démarrage


def _slug(params: dict) -> str:
    return f"WACC_{params['industry']}_{params['country']}_{params['year']}".replace(" ", "_")


def _params_from_query(query: str) -> dict:
    """Paramètres portés par l'URL, complétés par les valeurs par défaut."""
    params = dict(DATASET["defaults"])
    fields = parse_qs(query)
    for key in TEXT_KEYS:
        if fields.get(key):
            params[key] = fields[key][0]
    if fields.get("year"):
        try:
            params["year"] = int(fields["year"][0])
        except ValueError:
            pass
    for key in FLOAT_KEYS:
        if fields.get(key):
            try:
                params[key] = float(fields[key][0])
            except ValueError:
                pass
    return params


def _excel(params: dict):
    """Classeur Excel du calcul, via le module d'export existant."""
    from export_wacc import generate_wacc_workbook

    values = wacc_core.compute(params)
    return generate_wacc_workbook(
        values,
        wacc_core.load_betas_data(),
        wacc_core.load_erps_data()[0],
        wacc_core.load_tax_rates_data(),
        wacc_core.load_financing_spread_data(),
    )


class Handler(BaseHTTPRequestHandler):
    server_version = "wacc43"

    def log_message(self, fmt, *args):
        print(f"  {self.command} {self.path}")

    def _send(self, status, body, content_type, filename=None):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        if filename:
            self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        route = urlparse(self.path)
        try:
            if route.path in ("/", "/index.html"):
                self._send(200, render_page(DATASET).encode("utf-8"), "text/html; charset=utf-8")
            elif route.path == "/export.xlsx":
                params = _params_from_query(route.query)
                self._send(
                    200,
                    _excel(params).getvalue(),
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    filename=f"{_slug(params)}.xlsx",
                )
            else:
                self._send(404, b"Route inconnue", "text/plain; charset=utf-8")
        except Exception as exc:
            message = f"{type(exc).__name__}: {exc}"
            self._send(500, message.encode("utf-8"), "text/plain; charset=utf-8")


def main():
    global DATASET

    parser = argparse.ArgumentParser(description="Prévisualisation locale du calcul de CMPC")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()

    print("Chargement des données Damodaran...")
    DATASET = wacc_core.build_dataset(progress=lambda m: print(f"  {m}"))

    server = ThreadingHTTPServer((args.host, args.port), Handler)
    url = f"http://127.0.0.1:{args.port}"
    print(f"\nwacc43 — {url}   (Ctrl+C pour arrêter)")
    if not args.no_browser:
        threading.Timer(0.5, lambda: webbrowser.open(url)).start()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nArrêt.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
