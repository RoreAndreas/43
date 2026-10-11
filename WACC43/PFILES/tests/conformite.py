"""Une requête obtenue est-elle celle qu'on attendait ?

Partagé par les tests des gabarits (`test_agent.py`) et par la mesure du
traducteur en ligne (`mesurer_agent.py`). On compare les requêtes *résolues*
par la page — noms ramenés aux libellés de la base, « Maroc » devenu
« Morocco » — parce que c'est la requête exécutée qui compte, pas son
orthographe. Seuls les champs qui décident de la réponse sont comparés :
source, filtres, tri, limite, agrégat, paramètres.
"""

import unicodedata


def _texte(v):
    s = unicodedata.normalize("NFD", str(v)).encode("ascii", "ignore").decode().lower()
    return " ".join("".join(c if c.isalnum() else " " for c in s).split())


def _valeur(v):
    if isinstance(v, bool):
        return v
    if isinstance(v, (int, float)):
        return round(float(v), 6)
    if isinstance(v, list):
        return tuple(sorted(_valeur(x) for x in v))
    return _texte(v)


def _filtres(liste):
    return sorted((f["champ"], f["op"], _valeur(f["valeur"])) for f in (liste or []))


def conforme(obtenu, attendu, champs_inclus=None):
    """(vrai ou faux, raison). `obtenu` et `attendu` sont des requêtes résolues."""
    if not obtenu:
        return False, "aucune requête"
    if obtenu.get("source") != attendu.get("source"):
        return False, f"source {obtenu.get('source')} au lieu de {attendu.get('source')}"
    if "requetes" in attendu:
        a, o = attendu["requetes"], obtenu.get("requetes") or []
        if len(a) != len(o):
            return False, f"{len(o)} requêtes comparées au lieu de {len(a)}"
        for i, (x, y) in enumerate(zip(o, a)):
            ok, raison = conforme(x, y)
            if not ok:
                return False, f"requête {i + 1} : {raison}"
        return True, ""
    if "filtres" in attendu and _filtres(obtenu.get("filtres")) != _filtres(attendu["filtres"]):
        return False, f"filtres {_filtres(obtenu.get('filtres'))} au lieu de {_filtres(attendu['filtres'])}"
    for cle in ("tri", "limite"):
        if cle in attendu and attendu[cle] is not None and obtenu.get(cle) != attendu[cle]:
            return False, f"{cle} {obtenu.get(cle)} au lieu de {attendu[cle]}"
    if attendu.get("agregat"):
        a, o = attendu["agregat"], obtenu.get("agregat") or {}
        if o.get("fonction") != a.get("fonction"):
            return False, f"agrégat {o.get('fonction')} au lieu de {a.get('fonction')}"
        if a.get("champ") and a["fonction"] != "compte" and o.get("champ") != a["champ"]:
            return False, f"agrégat sur {o.get('champ')} au lieu de {a['champ']}"
    for cle, v in (attendu.get("parametres") or {}).items():
        if _valeur((obtenu.get("parametres") or {}).get(cle)) != _valeur(v):
            return False, f"paramètre {cle} : {(obtenu.get('parametres') or {}).get(cle)} au lieu de {v}"
    champs = obtenu.get("champs")
    for c in champs_inclus or []:
        if champs and c not in champs:
            return False, f"champ {c} absent de l'affichage"
    return True, ""
