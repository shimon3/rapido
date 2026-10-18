# Revue des licences bloquantes — bêta privée (2 à 5 testeurs)

Point de départ juridique : remettre l'installateur à des testeurs **externes**
est une distribution, même gratuite et limitée. Les obligations des licences
LGPL, MPL, GPL (exception du bootloader), Apache et BSD/MIT s'appliquent donc
comme pour une version publique. Ce document est un contrôle technique, pas
un avis juridique. Le détail par composant est dans
`docs/license-obligations-report.md`.

## Points qui bloqueraient la distribution, et leur état

| # | Obligation | Contrôle | État |
| --- | --- | --- | --- |
| B1 | Textes de licence et notices de tous les composants livrés avec le programme | `collect_license_evidence.py` : le build échoue si une notice requise manque ou ne correspond pas | Respectée si le run du candidat est vert |
| B2 | pystray (LGPLv3) : notice, textes GPL/LGPL, **source**, moyen de reconstruire avec une version modifiée | Source vérifiée par empreinte et livrée dans `third-party/source/pystray-0.19.5/`, `SOURCE.md`, code de Rapido public (MIT) au commit indiqué | Respectée si le run est vert. La source est livrée depuis le commit `ba5caac` |
| B3 | certifi (MPL-2.0) : indiquer où obtenir la forme source, texte MPL complet | Forme source livrée dans `third-party/source/certifi-2026.7.22/`, plus `MPL-2.0.txt` | Respectée si le run est vert |
| B4 | Bootloader PyInstaller (GPL-2.0+ avec exception) | Le build échoue si le texte de l'exception n'est pas livré | Respectée si le run est vert |
| B5 | Pas de composant non prévu (FFmpeg, Deno, outils de test, clé privée) | `payload.json`, pytest interdit, audit des clés privées | À relire dans `payload.json` du candidat avant envoi |
| B6 | Code source exact disponible pour les testeurs | Dépôt public, commit candidat communiqué dans le message d'envoi | Le propriétaire doit **ne pas supprimer** la branche ni le commit |

## Points non bloquants pour la bêta privée, à régler avant une version publique

| Question | Pourquoi ce n'est pas bloquant ici |
| --- | --- |
| proxy_tools : métadonnées MIT contre texte BSD | Les deux licences sont permissives, et le texte d'origine est livré |
| Crédit FreeType « dans la documentation » | Le crédit figure dans la notice livrée. L'ajouter à l'écran « À propos » serait un plus |
| Conditions Microsoft pour `VCRUNTIME140*.dll` et `ucrtbase.dll` | Elles sont fournies avec la distribution officielle de Python et citées dans `Python-LICENSE.txt`. À confirmer par un juriste avant une version publique |
| WebView2 SDK : périmètre du « Distributable Code » | Ce sont les mêmes fichiers que toute application pywebview, et les textes sont livrés. À confirmer avant une version publique |
| Revue juridique humaine complète | Requise avant une diffusion publique, recommandée mais proportionnée ici |

## Conclusion

**Aucune licence ne bloque une bêta privée**, à deux conditions : le run CI du
candidat est vert (les contrôles B1–B4 en dépendent), et `payload.json` est
relu (B5). Les questions ouvertes ne changent pas cette conclusion pour 2 à 5
testeurs, mais elles doivent avoir une réponse écrite avant une version
publique.
