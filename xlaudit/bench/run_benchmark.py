"""Banc d'essai des moteurs d'evaluation de formules.

Le critere central n'est pas la couverture, c'est **l'honnetete** : que fait le
moteur quand il rencontre une fonction qu'il ne sait pas evaluer ?

Trois issues possibles pour chaque cellule testee :

- `OK`        : la valeur rendue egale la valeur attendue ;
- `ECHEC`     : le moteur leve une exception ou rend un marqueur d'erreur — il
                dit qu'il ne sait pas, ce qui est un comportement acceptable ;
- `FAUX`      : le moteur rend une valeur numerique differente de la valeur
                attendue, sans rien signaler.

`FAUX` est eliminatoire. Un moteur d'audit qui produit un chiffre faux en
silence est pire qu'un moteur absent : il transforme un trou de couverture en
constat errone.
"""

from __future__ import annotations

import resource
import sys
import time
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from bench.build_bench_workbooks import CASES, CIRCULAR, SHEET

TOL = 1e-6
ERROR_MARKERS = ("#VALUE!", "#NAME?", "#N/A", "#REF!", "#DIV/0!", "#NUM!", "#NULL!",
                 "#CALC!", "#SPILL!")


def classify(got, expected) -> tuple[str, str]:
    """Compare une valeur rendue a la verite. Rend (verdict, detail)."""
    if isinstance(got, Exception):
        return "ECHEC", f"{type(got).__name__}: {str(got)[:70]}"
    # Les moteurs enveloppent parfois le resultat dans un tableau numpy.
    raw = got
    for attr in ("value", "values"):
        if hasattr(raw, attr):
            raw = getattr(raw, attr)
    try:
        import numpy as np

        if isinstance(raw, np.ndarray):
            raw = raw.flatten()[0] if raw.size else None
    except ImportError:
        pass
    if raw is None:
        return "ECHEC", "None"
    text = str(raw)
    if any(m in text for m in ERROR_MARKERS):
        return "ECHEC", text[:70]
    if isinstance(expected, str):
        return ("OK", text[:40]) if text.strip() == expected else ("FAUX", f"{text[:40]!r}")
    try:
        num = float(raw)
    except (TypeError, ValueError):
        return "ECHEC", f"non numerique: {text[:60]}"
    if abs(num - float(expected)) <= TOL:
        return "OK", f"{num:g}"
    return "FAUX", f"{num:g} au lieu de {expected:g}"


def peak_memory_mb() -> float:
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024.0


# ---------------------------------------------------------------------------
# Adaptateurs : une fonction par moteur, qui rend un dict {ref: valeur|Exception}
# ---------------------------------------------------------------------------

def probe_pycel(path: Path, refs: list[str]) -> tuple[dict, float, str]:
    from pycel import ExcelCompiler

    t0 = time.perf_counter()
    compiler = ExcelCompiler(filename=str(path))
    out = {}
    for ref in refs:
        try:
            out[ref] = compiler.evaluate(f"{SHEET}!{ref}")
        except Exception as exc:  # noqa: BLE001 - on veut classer l'echec, pas le propager
            out[ref] = exc
    return out, time.perf_counter() - t0, ""


def probe_formulas(path: Path, refs: list[str]) -> tuple[dict, float, str]:
    import formulas

    t0 = time.perf_counter()
    model = formulas.ExcelModel().loads(str(path)).finish(circular=True)
    solution = model.calculate()
    elapsed = time.perf_counter() - t0

    # formulas indexe par "'[FICHIER]FEUILLE'!REF" en majuscules.
    index: dict[str, object] = {}
    for key, value in solution.items():
        index[str(key).upper()] = value
    out = {}
    for ref in refs:
        hit = None
        for key, value in index.items():
            if key.endswith(f"!{ref.upper()}") and SHEET.upper() in key:
                hit = value
                break
        out[ref] = hit if hit is not None else KeyError(f"{ref} absent de la solution")
    return out, elapsed, ""


def probe_xlcalculator(path: Path, refs: list[str]) -> tuple[dict, float, str]:
    from xlcalculator import ModelCompiler, Evaluator

    t0 = time.perf_counter()
    model = ModelCompiler().read_and_parse_archive(str(path))
    evaluator = Evaluator(model)
    out = {}
    for ref in refs:
        try:
            out[ref] = evaluator.evaluate(f"{SHEET}!{ref}")
        except Exception as exc:  # noqa: BLE001
            out[ref] = exc
    return out, time.perf_counter() - t0, ""


ENGINES = {
    "pycel": probe_pycel,
    "formulas": probe_formulas,
    "xlcalculator": probe_xlcalculator,
}


def run_coverage(path: Path, engine: str) -> dict:
    refs = [c[0] for c in CASES] + [c[0] for c in CIRCULAR] + ["G2"]
    expected = {c[0]: c[2] for c in CASES}
    expected.update({c[0]: c[2] for c in CIRCULAR})
    expected["G2"] = 55000.0
    names = {c[0]: c[3] for c in CASES}
    names.update({c[0]: "circularite" for c in CIRCULAR})
    names["G2"] = "matricielle"

    try:
        values, elapsed, _ = ENGINES[engine](path, refs)
    except Exception as exc:  # noqa: BLE001
        return {"engine": engine, "fatal": f"{type(exc).__name__}: {exc}",
                "trace": traceback.format_exc()[-600:]}

    rows = []
    for ref in refs:
        verdict, detail = classify(values.get(ref), expected[ref])
        rows.append({"ref": ref, "fonction": names[ref], "verdict": verdict,
                     "detail": detail})
    return {"engine": engine, "elapsed": elapsed, "rows": rows}


def run_load(path: Path, engine: str) -> dict:
    """Charge le gros classeur et evalue une seule cellule."""
    before = peak_memory_mb()
    try:
        t0 = time.perf_counter()
        values, _e, _ = ENGINES[engine](path, [])
        elapsed = time.perf_counter() - t0
    except Exception as exc:  # noqa: BLE001
        return {"engine": engine, "fatal": f"{type(exc).__name__}: {str(exc)[:200]}"}
    return {"engine": engine, "elapsed": elapsed,
            "memoire_mb": peak_memory_mb() - before,
            "memoire_totale_mb": peak_memory_mb()}


def main() -> None:
    bench_dir = Path(sys.argv[1])
    engine = sys.argv[2]
    mode = sys.argv[3] if len(sys.argv) > 3 else "couverture"

    if mode == "couverture":
        result = run_coverage(bench_dir / "couverture.xlsx", engine)
        if "fatal" in result:
            print(f"[{engine}] FATAL {result['fatal']}")
            print(result.get("trace", ""))
            return
        print(f"[{engine}] chargement + evaluation : {result['elapsed']:.2f}s")
        counts = {"OK": 0, "ECHEC": 0, "FAUX": 0}
        for row in result["rows"]:
            counts[row["verdict"]] += 1
            flag = {"OK": "  ", "ECHEC": "??", "FAUX": "!!"}[row["verdict"]]
            print(f" {flag} {row['ref']:>4} {row['fonction']:<14} "
                  f"{row['verdict']:<6} {row['detail']}")
        print(f"[{engine}] OK={counts['OK']} ECHEC={counts['ECHEC']} "
              f"FAUX={counts['FAUX']}")
        if counts["FAUX"]:
            print(f"[{engine}] DISQUALIFIE : {counts['FAUX']} valeur(s) fausse(s) "
                  f"rendue(s) sans signalement")
    else:
        result = run_load(bench_dir / "charge.xlsx", engine)
        if "fatal" in result:
            print(f"[{engine}] FATAL {result['fatal']}")
            return
        print(f"[{engine}] charge : {result['elapsed']:.1f}s, "
              f"memoire +{result['memoire_mb']:.0f} Mo "
              f"(pic {result['memoire_totale_mb']:.0f} Mo)")


if __name__ == "__main__":
    main()
