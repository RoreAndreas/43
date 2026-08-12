"""xlaudit - aide a l'audit de modeles financiers Excel.

L'outil produit des **signaux** : des faits verifiables, chiffres et traces. Il ne
produit jamais de constats d'audit. Le tri des faux positifs, la qualification
erreur/convention, l'attribution de criticite et la redaction restent a
l'auditeur ou a un modele de langage travaillant sur la sortie JSON.
"""

from .models import SCHEMA_VERSION, AuditContext, Finding, Reserve, RunLog, Signal

__version__ = "0.6.0"

__all__ = [
    "AuditContext",
    "Finding",
    "Reserve",
    "RunLog",
    "SCHEMA_VERSION",
    "Signal",
    "__version__",
]
