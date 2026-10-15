# Rapido — préparation de la première bêta Windows

État vérifié le 15 octobre 2026. **Bêta publique non approuvée.** Aucun accord de fusion/publication n'est impliqué par ce document. Pas de nouvelle fonctionnalité prévue.

## Dernière validation fonctionnelle — CI #189

Code `2016be14c8be31f0c45de4b4d175760e8e8b5adc`,
[CI Windows #189](https://github.com/shimon3/rapido/actions/runs/38693975564) réussie :
194 régressions, 5 fixtures signées ignorées dans la suite générale après leur
exécution dédiée, 105 sous-tests, 1 avertissement. L'exécution des signatures
passe ses 15 tests dédiés (dont 5 tests réels de PE signés, avec recoupement des
tests unitaires de la suite générale). Les sondes WebView2 des deux fenêtres,
compilations, installateur/portable et Firefox passent ; release ignorée.

Les confirmations de suppression, redémarrage, récupération de handoff et
annulation de progression utilisent maintenant le dialogue intégré. Annuler est
le choix initial ; Échap/événement cancel et fermeture externe refusent. Les
appels répétés sont bloqués pendant une action et les éléments confirmés sont
figés malgré le rafraîchissement. Suppr/Ctrl+A dans un champ ne pilotent plus la
liste. Une erreur de mise en pause reste visible et ne ferme pas la fenêtre.

Le chemin API simple de redémarrage attendait déjà l'annulation. Deux tests ont
reproduit les défauts réels : appel concurrent qui dépassait l'ancien écrivain
et annulation d'une requête qui interrompait le nettoyage puis réinitialisait.
Le moteur garde désormais la tâche enregistrée jusqu'à sa fin, annule une seule
fois et protège son nettoyage. Une requête interrompue est propagée sans
réinitialisation ; le téléchargement reste en pause avec son état partiel. Les
appels concurrents attendent l'ancien écrivain et le fichier terminé est conservé.

[Preuves et périmètre](critical-actions-validation-20261015.json) : Node exerce
les vrais helpers/handlers avec DOM simulé ; WebView2 exerce les vrais dialogues
et handlers avec POST destructifs interceptés. Les tests backend utilisent de
vraies tâches asyncio et des fichiers temporaires. L'événement cancel est
synthétique : pas de validation d'une touche physique ni certification Windows
10/11. Les anciens artefacts inspectés ci-dessous concernent #187, pas #189.
L'inventaire et les collecteurs sont exécutés dans #189, mais aucune nouvelle
inspection indépendante de son ZIP n'est revendiquée.

## Référence de build inspectée — CI #187

Code testé : `6ba9c229b3cfae3d106b71687553abe18c81a00f`, PR #33 dépendante de #32.
[CI #187](https://github.com/shimon3/rapido/actions/runs/38691471314) réussie :
190 tests dans la suite générale, 5 fixtures signées ignorées après exécution
séparée, 105 sous-tests et 1 avertissement. L'exécution dédiée des signatures
passe ses 15 tests : 9 tests de politique/unitaires, 1 test réel de fichier non
signé et 5 tests réels de PE signés. Les nombres des deux exécutions se recoupent.
Compilation, fenêtre réelle, installateur/désinstallateur, coexistence portable
et Firefox réel passent. OS : Windows Server 2025, pas une validation Windows 10/11.
Token de compilation en lecture seule ; release ignorée. Aucune fusion/publication.

La base de compilation est maintenant **Python 3.13.16 / OpenSSL 3.5.9**, vérifiée
sur le runner et dans les ressources VERSIONINFO des DLL réellement téléchargées.
Auparavant, #184 embarquait Python 3.12.10 / OpenSSL 3.0.16. Les avis
[OpenSSL 3.0](https://openssl-library.org/news/vulnerabilities-3.0/) comprennent
cette ancienne version dans des plages affectées ; l'exploitabilité des chemins
correspondants dans Rapido n'a pas été établie. La
[version Python retenue](https://www.python.org/downloads/release/python-31316/)
fournit les binaires Windows et documente OpenSSL 3.5.9. Un contrôle préalable
refuse une autre version de Python ou un OpenSSL inférieur à la base retenue.
#186 avait échoué uniquement sur une mauvaise interprétation de
`OPENSSL_VERSION_INFO` ; la comparaison explicite des versions et ses tests
corrigent ce contrôle dans #187, sans abaisser le seuil.

L'inventaire lit les archives CArchive/PYZ des deux exécutables sans exécuter
leur code, ainsi que leurs deux ZIP de bibliothèque standard. Il distingue les
candidats de distribution par nom de module RECORD des correspondances natives
par taille et SHA-256. Les inconnus/ambiguïtés restent visibles. Les modules
`pytest`/`_pytest` observés dans #184 sont exclus ; le build refuse leur présence
et le ZIP final confirme leur absence. Aucun statut de conformité ou politique
d'intégrité d'exécution n'est déduit de cet inventaire de compilation.

Inspection finale : **154 fichiers de charge utile** (hors preuves tierces),
**55 entrées binaires de l'hôte natif**, **41 distributions de compilation**,
**115 textes de licence de packages**, licence Python 3.13.16 et licence Rapido.
Empreintes de ces fichiers/textes et concordance du contenu final vérifiées.
Les quatre archives listent 2411 entrées dans Rapido.exe, 131 dans l'hôte et
154 dans chacun des deux ZIP standard ; ces nombres ne désignent pas des
composants tiers distincts. La contradiction MIT/BSD de proxy_tools reste
signalée. Obligations LGPL/MPL, notices natives et provenance restent à examiner.

| Artefact #187 | SHA-256 vérifiée |
| --- | --- |
| Archive GitHub Actions | `d5eb35976f535c69f2c28011048043f44e3402e8d97b0d22c724c8a30fb441f7` |
| Rapido-1.2.2-portable.zip | `22f0d2b282f29012ff592ac8c851ef7d415d0ddfff11078496009c8f4fe38aa1` |
| Rapido-Setup-1.2.2.exe | `a0f9337f21b769ddea2c52cdcacd1b3e589be48d4219f12c0400ff4025f8a182` |

Preuves actuelles : [inspection du contenu](beta-payload-inspection-20261015.json),
[inventaire des distributions](beta-build-inventory-20261015.json),
[ressources de version natives](beta-native-version-resources-20261015.json).
Les chaînes VERSIONINFO sont déclaratives ; aucune validation du signataire ou
certification de sécurité exhaustive n'est impliquée. Le manifeste complet de
charge utile est dans `third-party/payload.json` de l'artefact lié à la CI.
L'ancien `beta-artifact-verification-20261015.json` concerne #183 uniquement.

Ces garde-fous CI sont sur les branches en revue. `main` conserve son ancien
mécanisme de publication automatique : toute future intégration autorisée devra
préserver la publication sur tag explicite avant une exécution sur `main`.
Le nom binaire reste 1.2.2 ; aucune diffusion bêta n'est approuvée.
Le checkpoint documentaire suivant #187 ne modifie aucun code testé et évite
une CI dupliquée avec [skip ci] ; ne pas prétendre que ce HEAD documentaire a
lui-même exécuté les tests. Une future intégration exige sa propre validation.

Les sections suivantes conservent des étapes antérieures ; leurs empreintes et
nombres ne désignent pas #187.

## Ce qui est vérifié

- Moteur consolidé PR #33, code `0dd20fc3d52457b0a33dd2f5bbfe6494f1fc9dee` : [CI Windows #181](https://github.com/shimon3/rapido/actions/runs/38684202772) réussie. 175 régressions réussies, 5 fixtures ignorées après exécution dédiée ; les 15 tests de signature dédiés ont tous réussi (dont 5 tests de PE signés réels). Compilation, fenêtres, installateur/portable et Firefox réel réussis ; release ignorée.
- Inspection effective de l'artefact #181 : 166 entrées dans le ZIP portable, aucun `ffmpeg.exe` ou `deno.exe`, licence Rapido présente et identique au texte source après normalisation LF/CRLF. Empreinte de l'archive Actions : `8114fb77195d97547ee1e4f084f940fbf595ab6e41a0fb7471d0f821b4540b19`. SHA-256 installateur : `053bff5263dca809f328ef1b94f967eb1e3e2ffe67a3d02b0e8ea811812eaed9` ; ZIP portable : `71bea57fb088cb9997948080db0c873f0f842cea3244382418f73b55f3314114`. Ces empreintes concernent #181 uniquement, pas un build ultérieur.
- PR #32, code `a4cae19e43cffa8028814e46f42b125e1971d918` : [CI Windows #179](https://github.com/shimon3/rapido/actions/runs/38682625394) réussie. 15 tests de signature dédiés sans skip (dont 5 tests de PE signés réels) ; 154 régressions réussies, 5 tests de fixtures ignorés dans la suite générale après leur exécution dédiée ; 88 sous-tests, 1 avertissement.
- Les tests réels couvrent signature valide/mauvais signataire/altération, verrouillage écriture/suppression, remplacement par un autre processus, remplacement entre deux vérifications, jonction NTFS et lien symbolique. Le vérificateur reste une brique non connectée à l'autorisation des captures.
- Compilation, fenêtre réelle, installation/désinstallation, coexistence portable, Firefox réel et empaquetage réussis. Token de compilation en lecture seule ; job release ignoré.
- OS du runner : **Windows Server 2025**. Ce résultat ne prouve pas une validation sur Windows 10 ou Windows 11.
- `main` reste sur `18e0997`. Les correctifs sont dans des branches/PR, pas dans la version publiée.

## Revue des PR : ne pas tout fusionner aveuglément

Inventaire de 26 PR ouvertes consulté via l'API GitHub ; vérification locale de l'ascendance de chaque HEAD vers #32. Une ascendance confirme la présence des commits, pas une revue complète ni l'absence de régressions.

| PR | Constat et traitement pour la bêta |
| --- | --- |
| #6 → #7 → #10 → #12 → #13 → #14 → #15 → #16 → #17 → #18 → #19 → #20 → #21 → #22 → #23 → #24 → #25 → #27 → #29 → #32 | HEAD présents dans l'ascendance de #32. Les premières PR ont des bases communes et des diff cumulatifs ; la chaîne décrit la présence des changements, pas un ordre de fusion autorisé. Faire une revue finale de l'ensemble puis préparer l'intégration sans perdre les garde-fous CI. |
| #11 | HEAD **absent** de #32. Les cinq garde-fous moteur n'étaient donc pas attestés présents ; lecture du code a confirmé leur absence. Repris sélectivement sur `work/beta-engine-guards-20261015`, avec tests et adaptation à la persistance privée actuelle. Aucun ancien workflow n'est réintroduit. |
| #5 | HEAD non ancêtre. Le confinement des cookies a été repris dans la branche native (commits `8be504d`, `552d065` et protections ultérieures). Comparer les critères de #5 aux tests actuels avant de décider son sort ; ne pas compter son ancien statut comme preuve d'intégration. |
| #4 | Ancienne conception documentaire, HEAD non ancêtre ; les modèles de menace actuels sont plus récents. Préserver la traçabilité, pas un blocage d'exécution à lui seul. |
| #2 | Confirmations reprises sélectivement et durcies dans #33, validées sur WebView2 par #188/#189. Aucun changement de version ni ancien workflow repris ; PR #2 reste non fusionnée. Acceptation manuelle Windows 10/11 et parcours de saisie/erreur encore à faire. |
| #8, #9 | Langues et notifications de mises à jour : branches séparées non intégrées. Différer les ajouts non indispensables ; ne pas présenter les traductions comme terminées. Aucun téléchargement/exécution d'updater à ajouter. |

### Moteur : correction sélectionnée après la revue

La branche bêta reprend les validateurs ETag/Last-Modified, `If-Range`, le refus d'une ressource modifiée, les écritures courtes/disque plein et les attentes bornées HTTP 429/503. Adaptations supplémentaires :

- Une date `If-Range` n'est utilisée qu'en l'absence d'ETag et avec un `Date` de réponse au moins 60 secondes après `Last-Modified`. Un ETag faible ne devient pas artificiellement un validateur fort.
- Rafraîchir un lien d'un fichier déjà partiellement écrit exige le même validateur utilisable et la reprise disponible ; la taille seule ne suffit plus. En cas de refus, URL/validateurs d'origine sont conservés et un téléchargement actif reste en pause.
- Le téléchargement est retiré temporairement de la file pendant la sonde du nouveau lien. Les écritures du fichier `.part` sont non tamponnées pour ne pas avancer la progression sur une simple acceptation en tampon Python.
- Si un segment est raccourci pendant l'arrivée d'une réponse, sa plage est comparée à la requête réellement envoyée ; seule la partie encore attribuée au worker est écrite. Un test reproduit le refus erroné antérieur puis vérifie ce comportement.
- Les validateurs sont conservés dans l'enveloppe DPAPI existante sur Windows. Une ancienne fiche sans validateur reste lisible ; le rafraîchissement d'un fichier partiel non identifiable exige de recommencer depuis zéro.

Référence technique : [RFC 9110, If-Range et validateurs](https://www.rfc-editor.org/rfc/rfc9110.html#section-13.1.5). Ces garde-fous ne sont pas une preuve cryptographique d'authenticité du fichier fourni par un serveur.

## Licences et provenance : revue initiale, pas conformité attestée

L'inspection du ZIP #181 n'a trouvé que la licence Rapido et trois textes de
licence de distributions Python. Le nouveau collecteur
`scripts/collect_license_evidence.py` rassemble donc les textes de licence
enregistrés par les distributions installées et le LICENSE de l'interpréteur,
avec noms/versions/empreintes et problèmes explicites. Ils sont destinés à
`Rapido/third-party/` dans le portable et l'installateur. Les chemins de métadonnées
qui sortent du répertoire de packages ne sont pas copiés. Le collecteur ne charge
pas le code des packages et n'exporte pas les variables d'environnement ou les
chemins absolus du runner.

Le rapport indique `scope=installed-build-environment` et
`compliance_verified=false` : outils de compilation/tests compris, sans prétendre
identifier exactement les modules distribués ou résoudre les obligations des
DLL natives. Le build refuse l'absence du LICENSE Python ; les autres textes
manquants sont signalés pour revue. Le collecteur a passé trois tests ciblés et
un essai réel sur 25 distributions Linux (36 textes collectés). Validation Windows et inspection effective sont désormais établies par #183 ci-dessus ; la conformité juridique complète reste non attestée.

### Inspection Windows #182

[CI #182](https://github.com/shimon3/rapido/actions/runs/38684939137), code
`e7483de52c2056ce4f502bb665ae22dd39823922` : réussite complète, 178 régressions
réussies, 5 fixtures ignorées après exécution dédiée ; 15 tests Authenticode
dédiés réussis. L'archive réelle a été téléchargée et vérifiée : 393 entrées,
46 distributions inventoriées, 120 textes de licence de packages et le LICENSE
Python 3.12.10 présents. Toutes les empreintes des textes copiés correspondent à
l'inventaire. Digest de l'archive Actions :
`bd28f0aa9dd99cd4fd4f56ed27e60ed46f0e1f50e1d9fcf5288f3519e47e5538`.

Le seul texte de package manquant dans ce build est `proxy_tools 0.1.0`. Sa
source publiée PyPI (SHA-256 vérifié) n'inclut pas de LICENSE ; ses métadonnées
annoncent MIT, mais l'en-tête du module annonce BSD. Le module publié correspond
exactement au module d'un commit amont dont le fichier BSD est accessible.
Le texte authentique et sa [provenance](../packaging/licenses/proxy_tools-0.1.0/PROVENANCE.md)
sont désormais conservés dans le dépôt. Le collecteur ne les applique qu'à la
version et à l'empreinte exacte de ce module et garde le conflit MIT/BSD signalé
pour revue. Cette modification supplémentaire est désormais validée et inspectée dans #183 ci-dessus.

L'inventaire réel confirme également `pystray 0.19.5` avec métadonnées LGPLv3 et
textes COPYING/COPYING.LGPL collectés, ainsi que `certifi 2026.7.22` avec
métadonnées MPL-2.0. Ne pas présenter toutes les dépendances comme permissives
ou sous MIT. Les obligations de distribution correspondantes et celles des
bibliothèques natives restent à examiner ; aucun verdict général de conformité
n'est produit par ces tests.

| Élément | Source vérifiée / point à terminer |
| --- | --- |
| Code Rapido | `LICENSE` contient MIT avec le titulaire **Samuel Tuil** ; l'installateur affiche Samuel Bentouza. Conserver les attributions existantes tant que la titularité n'est pas clarifiée. Le pipeline copie désormais ce LICENSE sans modification dans le dossier distribué. |
| Python et modules Python | `requirements.txt` énumère les dépendances directes, mais la plupart des versions et dépendances transitives ne sont pas figées. Inventorier les versions réellement embarquées et leurs notices avant distribution. La licence propre de Rapido ne remplace pas celles des dépendances. |
| Pillow | Le [texte amont](https://github.com/python-pillow/Pillow/blob/main/LICENSE) identifie MIT-CMU. Vérifier aussi les bibliothèques natives effectivement contenues dans la wheel choisie. |
| FastAPI, HTTPX, pywebview | Sources amont consultées : [FastAPI](https://github.com/fastapi/fastapi/blob/master/LICENSE), [HTTPX](https://github.com/encode/httpx/blob/master/LICENSE.md), [pywebview](https://github.com/r0x0r/pywebview/blob/master/LICENSE). Ce sont des repères de revue, pas la liste complète du bundle ni une validation de chaque version installée. |
| yt-dlp | Installé par pip et importé comme module. La [documentation amont](https://github.com/yt-dlp/yt-dlp#licensing) distingue le dépôt/wheel sous Unlicense et ses exécutables amont qui contiennent d'autres licences. Ne pas conclure que le bundle Rapido est libre de toute autre obligation à partir de la seule licence yt-dlp. |
| PyInstaller | L'[exception de distribution](https://pyinstaller.org/en/stable/license.html) permet de choisir la licence de l'application générée sous réserve des dépendances ; le mot GPL sur l'outil ne suffit pas à imposer cette licence à Rapido. |
| FFmpeg / Deno | Les routes `/api/tools/ffmpeg` et `/api/tools/deno` lancent winget avec `Gyan.FFmpeg` / `DenoLand.Deno`. Le workflow ne les copie pas explicitement dans le bundle ; vérifier les fichiers finaux avant d'attester leur absence. [FFmpeg](https://ffmpeg.org/legal.html) distingue LGPL et options GPL ; [Deno](https://github.com/denoland/deno/blob/main/LICENSE.md) fournit son texte MIT. Vérifier l'artefact effectivement choisi, pas seulement le nom du projet. |
| Interface, images, nom et comparaison IDM | Aucune revue complète de provenance, de marque ou de similarité avec un logiciel tiers n'a été faite ici. L'absence de conflit avec IDM n'est pas établie : je ne peux pas confirmer ça. La présence d'un LICENSE MIT dans le dépôt ne démontre pas l'origine de chaque élément. |

Référence Python : [licence de Python 3.12 et composants incorporés](https://docs.python.org/3.12/license.html). L'inventaire des fichiers/modules est maintenant collecté ; les attributions natives et obligations de redistribution restent à vérifier ; ne pas remplacer ces preuves par une déclaration générale « toutes les dépendances sont MIT ».

## Travail restant, difficulté et effort

**Estimations d'ingénierie**, pas résultats mesurés ni date promise. Une journée représente environ 6 à 8 heures de travail effectif. Les délais de certificat, d'infrastructure ou de réponse externe sont exclus.

| Priorité | Tâche restante | Difficulté | Effort estimé | Condition de fin |
| --- | --- | --- | --- | --- |
| Terminé | Valider la branche moteur consolidée sur Windows | Moyenne | 0 h restantes pour ce correctif | CI #181 réussie sur `0dd20fc` ; les changements d'empaquetage suivants ont leur propre validation |
| P0 | Revue finale sécurité/intégration des PR indispensables | Élevée | 1–2 j | Routes/IPC/persistance/handoff relus, conflits traités sur branche, critères #3/#28 couverts ; aucune fusion avant accord |
| P0 | Définir la garantie réelle de la bêta pour #26 | Élevée | 0,5–1 j de revue | Distinguer bêta par utilisateur et installation administrée ; limites explicites, aucune prétention de protection contre le compte compromis |
| P0 | Inventaire du bundle, versions, notices et provenance | Moyenne à élevée | 0,5–1,5 j | Composants/versions/hashes/licences exacts, notices présentes, attributions clarifiées |
| P0 | Tests propres Windows 10/11, Chrome/Edge/Firefox, comptes/installations isolés | Élevée | 1,5–3 j | Captures normales/privées/cookies, host absent, pause/reprise/redémarrage, mise à niveau et désinstallation ; sur VM dédiée, jamais le PC utilisateur |
| P1 | Acceptation manuelle des dialogues, erreurs, clavier et parcours sans extension | Moyenne | 0,5–1 j | Automatisation WebView2 et redémarrage concurrent validés #189 ; reste la matrice de bureau et les parcours non couverts |
| P0 avant diffusion | Revue des artefacts, Defender, hashes, version bêta distincte et retour arrière | Moyenne | 0,5–1 j | Artefacts identifiés par commit, aucun secret/test-key, procédure de réparation/retrait documentée |
| Décision externe | Identité/certificat de signature de production | Dépend du fournisseur | Non estimable ici ; intégration technique 0,5–1 j une fois les prérequis disponibles | Identité et renouvellement approuvés ; aucune clé de test utilisée en production |
| Hors garantie bêta actuelle | Résoudre complètement #26 contre le remplacement par le même compte | Très élevée | Prototype/revue/matrice : au moins 5–10 j supplémentaires ; estimation à revoir après choix d'architecture | Ancre système indépendante, exécution/dépendances protégées et sélection navigateur imposée ; la signature seule ne suffit pas |

Pour une bêta au périmètre explicite, prévoir environ **5–10 journées effectives restantes**, selon les défauts trouvés en revue et sur les VM. Ce n'est pas une promesse de calendrier. Si la résistance complète au compte compromis est exigée avant la bêta, ne pas utiliser cette fourchette : le dernier chantier s'ajoute et les prérequis de déploiement restent à établir.

## Prochain ordre de travail

1. Revoir les vulnérabilités, notices natives et obligations de licence à partir des inventaires collectés ; conserver les droits existants.
2. Compléter les parcours de saisie/erreur et la matrice de VM Windows 10/11 ; l'automatisation critique #189 est déjà validée.
3. Définir les prérequis concrets de signature/ancre protégée pour #26, puis préparer la revue d'intégration.
4. Soumettre les éléments concrets nécessitant une décision ; aucune fusion, tag, release ou publication automatique.
