# Résultats de l'agent

Mesures du traducteur (niveau 1) et de l'analyste (niveau 2) sur le site
déployé, ajoutées par `python tests/mesurer_agent.py`. Le niveau 0 — les trente
questions reconnues sans serveur — est vérifié à chaque passage de la suite par
`tests/test_agent.py`.

## Ce qui reste à mesurer

Aucune mesure en ligne n'a encore été faite : les fonctions serveur n'étaient
pas déployées quand l'agent a été construit (octobre 2026). Le cerveau doit
rester gratuit, donc les candidats sont tous des modèles Workers AI, dans
l'enveloppe offerte de 10 000 neurones par jour :

| Rôle | Candidat | Neurones par appel (estimation) | Remarque |
|---|---|---|---|
| Traducteur | `@cf/qwen/qwen3-30b-a3b-fp8` (défaut) | ≈ 12 | raisonnement coupé par `/no_think` |
| Traducteur | `@cf/google/gemma-4-26b-a4b-it` | ≈ 18 | JSON extrait du texte |
| Traducteur | `@cf/meta/llama-3.3-70b-instruct-fp8-fast` | ≈ 71 | mode JSON garanti, six fois plus cher |
| Analyste | `@cf/meta/llama-3.3-70b-instruct-fp8-fast` (défaut) | ≈ 400 | mode JSON garanti |
| Analyste | `@cf/openai/gpt-oss-120b` | ≈ 280 + raisonnement | meilleur indice de raisonnement, JSON non garanti |
| Analyste | `@cf/qwen/qwen3-30b-a3b-fp8` | ≈ 65 | le moins cher, à juger sur la rédaction |

Seuil de bascule proposé par la note du 5 octobre : sous 90 % de requêtes
identiques à l'attendu, changer de traducteur. Pour l'analyste, la grille de
lecture à l'aveugle (`--aveugle`) départage les candidats à JSON valide égal.
