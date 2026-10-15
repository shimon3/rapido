# Rapido — préparation de la première bêta Windows

État du 15 octobre 2026. **Bêta publique non approuvée.** Pas de fusion, tag,
release ou déploiement autorisé. `main` reste sur `18e0997` et conserve son ancien
mécanisme de publication ; une future intégration autorisée doit préserver les
garde-fous de publication sur tag explicite avant toute exécution sur `main`.

## Dernière validation

CI #196 réussie sur `c68ac60f6c23e783b1c82b5319180d33140b085a` :
[run Windows](https://github.com/shimon3/rapido/actions/runs/38707014474).
221 régressions, 5 fixtures signées ignorées après exécution dédiée, 110 sous-tests,
1 avertissement. Exécution dédiée : 15 tests de signature, dont 5 tests réels de
PE signés, 1 test réel de fichier non signé et 9 tests de politique/unitaires.
Les deux exécutions se recoupent. Sondes WebView2, compilations, installateur/portable,
Firefox 157.0.1, pip check et les 41 réponses PyPI passent ; release ignorée et token build
en lecture seule. Python 3.13.16 / OpenSSL 3.5.9 vérifiés. Les échecs d'installation
pip arrêtent immédiatement la commande. Runner Server 2025, pas certification
Windows 10/11. L'artefact indépendamment inspecté ci-dessous reste #190 ; les ZIP suivants ne sont pas inspectés indépendamment.
Le checkpoint documentaire suivant conserve le code testé et utilise [skip ci] ;
ce HEAD documentaire n'a pas lui-même exécuté la CI. Toute intégration future
exige ses propres contrôles et une autorisation de fusion.

Le lancement natif refuse désormais aussi les liens/jonctions dans les dossiers
parents des exécutables, du navigateur reconnu et du manifeste Firefox. Les tests
couvrent de vraies jonctions et les dossiers Windows des navigateurs. Ce contrôle
reste partiel : aucune attestation ni ancre protégée n'est ajoutée à #26.

Le harnais Firefox utilise une copie de test séparée et un canal local à identifiant
aléatoire ; le background distribué reste intact. Le harnais n'active pas l'accès
système WebDriver et n'affaiblit aucune préférence de sécurité. #195 a validé Firefox 156.0.1 ; #196 valide
séparément 157.0.1, installateur Mozilla contrôlé par SHA-512 et signature, version
installée et version WebDriver vérifiées. [Preuves](native-launcher-validation-20261015.json).

## Dépendances et artefact inspecté — #190

Les 41 versions observées sont figées dans
[les contraintes Windows](../packaging/constraints-windows-build.txt), appliquées
aux installations et aux outils de build connus. Le contrôle exige le même
inventaire, interroge les endpoints PyPI de versions précises et refuse les avis
actifs, retraits de fichiers/version ou réponses non vérifiées. Le
[rapport #190](dependency-advisory-snapshot-20261015.json) contient 41 réponses
vérifiées sans avis actif retourné à cet instant. Les avis retirés sont conservés.
Ce résultat n'est pas une absence démontrée de vulnérabilités ; les dépendances
natives et celles installées plus tard pour Selenium restent à examiner. Les
versions seules ne constituent pas un verrouillage par empreintes des paquets.

Les cinq DLL Microsoft du SDK WebView2 correspondent octet pour octet au paquet
NuGet 1.0.3856.49. Ses deux textes originaux LICENSE/NOTICE sont conservés avec
[provenance et empreintes](../packaging/licenses/Microsoft.Web.WebView2-1.0.3856.49/PROVENANCE.md).
Le collecteur vérifie les cinq DLL installées, la version du porteur pywebview
et les deux textes avant de les copier ; un écart arrête le build. Aucun droit
ou engagement de fourniture de sources n'est inventé. Les autres composants,
la compatibilité d'ensemble et les obligations LGPL/MPL restent ouverts.

Le ZIP #190 a été téléchargé : 154 fichiers de charge utile, 55 entrées binaires
embarquées et 117 textes de licence de packages vérifiés. Les 41 versions et le
rapport PyPI, les cinq DLL SDK et les deux textes d'origine concordent.
[Inspection complète](beta-payload-inspection-20261015.json) et
[ressources natives déclarées](beta-native-version-resources-20261015.json).

| Artefact #190 | SHA-256 vérifiée |
| --- | --- |
| Archive Actions | `46713a203094f27e1b5600358701df2d056c25d9bca75c7092612594bd4929fc` |
| ZIP portable | `177818d1f09748fe5a32f980023115861af81654c2395ed7b5c556185d11b52c` |
| Installateur | `3ee85e1b5906d99fb51a297e557daf5ed179d57bd8ac1ed7fd1aa0616707aa7b` |


## Corrections critiques déjà validées

Les confirmations de suppression, redémarrage, récupération de handoff et
annulation de progression utilisent le dialogue intégré. Annuler reçoit le
focus ; Échap/événement cancel et fermeture externe refusent. Les identités
confirmées sont figées malgré le rafraîchissement, les doubles actions sont
bloquées. Suppr/Ctrl+A dans un champ ne pilotent plus la liste. Une erreur de
pause reste affichée sans fermer la fenêtre.

Deux défauts moteur reproduits puis corrigés : un redémarrage concurrent pouvait
réinitialiser avant la fin de l'ancien écrivain ; annuler son appelant pouvait
interrompre le nettoyage et quand même réinitialiser. Le moteur attend la tâche
partagée, annule une fois, protège le nettoyage et propage l'annulation de
l'appelant. L'état partiel reste en pause ; le fichier terminé est conservé.
Trois tests utilisent de vraies tâches asyncio et des fichiers temporaires.

Les sondes WebView2 utilisent les vrais dialogues/handlers, avec POST destructifs
interceptés. L'événement cancel est synthétique : pas de certification d'une
touche physique ou de tous les parcours UI/API destructifs. Le
[rapport ciblé #189](critical-actions-validation-20261015.json) conserve la preuve
initiale ; #190 réexécute ces contrôles. Les garde-fous de reprise/ETag/If-Range,
Retry-After, plage/taille et écriture disque restent présents. Aucun ancien
workflow des PR séparées n'a été réintroduit.

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

## Licences et provenance — reste une revue à terminer

L'inventaire courant concerne #190 : 41 distributions de compilation et 117
textes de package, dont les notices SDK ajoutées. `pystray 0.19.5` déclare LGPLv3,
`certifi 2026.7.22` MPL-2.0 ; leurs textes sont conservés. Le supplément
[proxy_tools 0.1.0](../packaging/licenses/proxy_tools-0.1.0/PROVENANCE.md) préserve
le texte BSD amont pour un module strictement identifié ; le désaccord avec les
métadonnées MIT reste signalé. Aucune compatibilité globale, obligation de
source/remplacement ou titularité n'est déduite de la simple collecte des textes.
La licence Python 3.13.16 de l'artefact a été vérifiée avec son empreinte.

| Élément | Source vérifiée / point à terminer |
| --- | --- |
| Code Rapido | `LICENSE` contient MIT avec le titulaire **Samuel Tuil** ; l'installateur affiche Samuel Bentouza. Conserver les attributions existantes tant que la titularité n'est pas clarifiée. Le pipeline copie désormais ce LICENSE sans modification dans le dossier distribué. |
| Python et modules Python | `requirements.txt` reste large pour le développement ; les 41 versions du build Windows sont désormais figées et contrôlées. Les fichiers/modules et leurs notices sont inventoriés ; les obligations natives restent à vérifier. La licence propre de Rapido ne remplace pas celles des dépendances. |
| Pillow | Le [texte amont](https://github.com/python-pillow/Pillow/blob/main/LICENSE) identifie MIT-CMU. Vérifier aussi les bibliothèques natives effectivement contenues dans la wheel choisie. |
| FastAPI, HTTPX, pywebview | Sources amont consultées : [FastAPI](https://github.com/fastapi/fastapi/blob/master/LICENSE), [HTTPX](https://github.com/encode/httpx/blob/master/LICENSE.md), [pywebview](https://github.com/r0x0r/pywebview/blob/master/LICENSE). Ce sont des repères de revue, pas la liste complète du bundle ni une validation de chaque version installée. |
| yt-dlp | Installé par pip et importé comme module. La [documentation amont](https://github.com/yt-dlp/yt-dlp#licensing) distingue le dépôt/wheel sous Unlicense et ses exécutables amont qui contiennent d'autres licences. Ne pas conclure que le bundle Rapido est libre de toute autre obligation à partir de la seule licence yt-dlp. |
| PyInstaller | L'[exception de distribution](https://pyinstaller.org/en/stable/license.html) permet de choisir la licence de l'application générée sous réserve des dépendances ; le mot GPL sur l'outil ne suffit pas à imposer cette licence à Rapido. |
| FFmpeg / Deno | Les routes `/api/tools/ffmpeg` et `/api/tools/deno` lancent winget avec `Gyan.FFmpeg` / `DenoLand.Deno`. Le workflow ne les copie pas explicitement dans le bundle ; vérifier les fichiers finaux avant d'attester leur absence. [FFmpeg](https://ffmpeg.org/legal.html) distingue LGPL et options GPL ; [Deno](https://github.com/denoland/deno/blob/main/LICENSE.md) fournit son texte MIT. Vérifier l'artefact effectivement choisi, pas seulement le nom du projet. |
| Interface, images, nom et comparaison IDM | Aucune revue complète de provenance, de marque ou de similarité avec un logiciel tiers n'a été faite ici. L'absence de conflit avec IDM n'est pas établie : je ne peux pas confirmer ça. La présence d'un LICENSE MIT dans le dépôt ne démontre pas l'origine de chaque élément. |


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
