"""Validation pydantic du mapping YAML.

Le mapping dit ou se trouvent, dans *ce* modele, les grandeurs sur lesquelles
portent les bouclages : total actif, total passif, solde de cloture, CRD des
dettes. Rien de tout cela n'est devinable de facon fiable, d'ou le fichier.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from ..core import refs as R


class Located(BaseModel):
    """Une grandeur reperee par son onglet et sa ligne."""

    model_config = ConfigDict(extra="forbid")

    sheet: str
    row: int = Field(ge=1, le=R.MAX_ROW)
    #: Renseigne par `validate-mapping`. Un controle ne s'execute jamais sur une
    #: localisation dont la validation numerique a echoue.
    validated: bool | None = None
    validation_note: str = ""

    def __str__(self) -> str:  # pragma: no cover - confort d'affichage
        return f"{self.sheet}!{self.row}"


class Periodes(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sheet: str
    ligne_index: int = Field(ge=1)
    ligne_date: int | None = Field(default=None, ge=1)
    colonnes: str = Field(description="plage de colonnes, p.ex. 'O:HU'")

    @field_validator("colonnes")
    @classmethod
    def _check_columns(cls, value: str) -> str:
        if ":" not in value:
            raise ValueError("les colonnes doivent s'ecrire 'O:HU'")
        left, right = value.split(":", 1)
        R.col_to_index(left.strip().lstrip("$"))
        R.col_to_index(right.strip().lstrip("$"))
        return value

    @property
    def col_range(self) -> tuple[int, int]:
        left, right = self.colonnes.split(":", 1)
        lo = R.col_to_index(left.strip().lstrip("$"))
        hi = R.col_to_index(right.strip().lstrip("$"))
        return (lo, hi) if lo <= hi else (hi, lo)

    def columns(self) -> list[int]:
        lo, hi = self.col_range
        return list(range(lo, hi + 1))


class Bilan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    actif_total: Located | None = None
    passif_total: Located | None = None
    tresorerie: Located | None = None


class Cascade(BaseModel):
    model_config = ConfigDict(extra="forbid")

    solde_cloture: Located | None = None
    solde_ouverture: Located | None = None
    encaissements: Located | None = None
    decaissements: Located | None = None
    facilite_court_terme: Located | None = None
    reserves: Located | None = None


class Dette(BaseModel):
    model_config = ConfigDict(extra="forbid")

    nom: str
    sheet: str
    crd_debut: int | None = Field(default=None, ge=1)
    tirage: int | None = Field(default=None, ge=1)
    remb: int | None = Field(default=None, ge=1)
    interets: int | None = Field(default=None, ge=1)
    crd_fin: int | None = Field(default=None, ge=1)
    taux_periode: float | None = None
    validated: bool | None = None
    validation_note: str = ""


class Immobilisations(BaseModel):
    model_config = ConfigDict(extra="forbid")

    brut: Located | None = None
    amortissements: Located | None = None
    net: Located | None = None


class AnnualSeries(BaseModel):
    """Une grandeur presente des deux cotes : par periode, et par annee.

    Les deux lignes doivent etre nommees. Une seule ne suffirait pas : rien ne
    garantit qu'une grandeur occupe le meme numero de ligne sur l'onglet
    periodique et sur l'onglet annuel.
    """

    model_config = ConfigDict(extra="forbid")

    periode_row: int = Field(ge=1, le=R.MAX_ROW)
    annuel_row: int = Field(ge=1, le=R.MAX_ROW)


class Annuel(BaseModel):
    """Correspondance entre la vue par periode et la vue annuelle.

    `flux` et `stocks` ne se controlent pas de la meme facon : un flux annuel
    doit egaler la **somme** des periodes de l'annee, un stock annuel doit egaler
    le stock de la **derniere** periode de l'annee. Les confondre est une source
    classique d'erreur, d'ou deux rubriques distinctes.
    """

    model_config = ConfigDict(extra="forbid")

    sheet: str
    ligne_index: int | None = Field(default=None, ge=1)
    colonnes: str | None = None
    flux: dict[str, AnnualSeries] = Field(default_factory=dict)
    stocks: dict[str, AnnualSeries] = Field(default_factory=dict)


class Tolerances(BaseModel):
    model_config = ConfigDict(extra="forbid")

    bilan: float = 1e-6
    cascade: float = 1e-6
    continuite: float = 1e-6
    amortissement: float = 1e-6
    interets_relatif: float = 0.005
    emplois_ressources: float = 1e-6
    periode_annuel: float = 1e-6
    immobilisations: float = 1e-6
    non_negativite: float = 0.0


class MappingModel(BaseModel):
    """Mapping complet d'un modele."""

    model_config = ConfigDict(extra="forbid")

    periodes: Periodes
    bilan: Bilan = Field(default_factory=Bilan)
    cascade: Cascade = Field(default_factory=Cascade)
    dettes: list[Dette] = Field(default_factory=list)
    immobilisations: Immobilisations = Field(default_factory=Immobilisations)
    annuel: Annuel | None = None
    flags: dict[str, Located] = Field(default_factory=dict)
    emplois: list[Located] = Field(default_factory=list)
    ressources: list[Located] = Field(default_factory=list)
    non_negatif: list[Located] = Field(default_factory=list)
    tolerances: Tolerances = Field(default_factory=Tolerances)

    @model_validator(mode="after")
    def _at_least_one_check(self) -> "MappingModel":
        if not any(
            [
                self.bilan.actif_total,
                self.cascade.solde_cloture,
                self.dettes,
                self.emplois,
                self.non_negatif,
                self.flags,
                self.immobilisations.net,
            ]
        ):
            raise ValueError(
                "le mapping ne permet aucun controle : renseigner au moins le bilan, "
                "la cascade, une dette ou une ligne a controler"
            )
        return self

    def located_items(self) -> list[tuple[str, Located]]:
        """Toutes les localisations simples, avec leur chemin dans le mapping."""
        out: list[tuple[str, Located]] = []
        for group_name, group in (("bilan", self.bilan), ("cascade", self.cascade)):
            for field_name in type(group).model_fields:
                value = getattr(group, field_name)
                if isinstance(value, Located):
                    out.append((f"{group_name}.{field_name}", value))
        for field_name in type(self.immobilisations).model_fields:
            value = getattr(self.immobilisations, field_name)
            if isinstance(value, Located):
                out.append((f"immobilisations.{field_name}", value))
        for name, loc in self.flags.items():
            out.append((f"flags.{name}", loc))
        for i, loc in enumerate(self.emplois):
            out.append((f"emplois[{i}]", loc))
        for i, loc in enumerate(self.ressources):
            out.append((f"ressources[{i}]", loc))
        for i, loc in enumerate(self.non_negatif):
            out.append((f"non_negatif[{i}]", loc))
        return out


def load_mapping(path: str | Path) -> MappingModel:
    """Charge et valide un mapping YAML."""
    with open(path, "r", encoding="utf-8") as fh:
        raw = yaml.safe_load(fh) or {}
    return MappingModel.model_validate(raw)


def _strip_empty_validation(data: Any) -> Any:
    """Retire les champs de validation vides du YAML ecrit.

    Un `validation_note: ''` sur chaque localisation rend le fichier illisible
    sans rien apprendre ; seules les notes reellement renseignees sont utiles.
    """
    if isinstance(data, dict):
        return {
            k: _strip_empty_validation(v)
            for k, v in data.items()
            if not (k == "validation_note" and v == "")
        }
    if isinstance(data, list):
        return [_strip_empty_validation(v) for v in data]
    return data


def dump_mapping(mapping: MappingModel, path: str | Path) -> None:
    """Ecrit un mapping en YAML lisible."""
    data = _strip_empty_validation(mapping.model_dump(exclude_none=True, mode="json"))
    with open(path, "w", encoding="utf-8") as fh:
        yaml.safe_dump(data, fh, allow_unicode=True, sort_keys=False, default_flow_style=False)


def mapping_to_dict(mapping: MappingModel) -> dict[str, Any]:
    return mapping.model_dump(exclude_none=True, mode="json")
