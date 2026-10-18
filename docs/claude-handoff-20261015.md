# Rapido — reprise pour Claude ou Codex

> **Checkpoint historique.** Les branches, PR, CI et règles de publication
> ci-dessous décrivent l'état du 15 octobre. Pour l'état courant, commencer par
> `docs/work-state.md`, puis les PR #34 et #35. Depuis le commit
> `de1a7b083d036b8bb1d15a6e138c558fae58b0db`, un tag seul ne peut plus publier :
> le workflow exige aussi le garde volontairement désactivé
> `publishable=false`.


Point de pause du 15 octobre 2026, après validation de la correction des enregistrements natifs. Aucun travail de licences supplémentaire n'a été commencé dans cette dernière étape. Aucun processus de développement ni tâche automatique n'est lancé pour la reprise de 14 h 13.

## Instruction de reprise

Poursuis le développement de `shimon3/rapido` pour une première bêta Windows stable et sécurisée. Lis d'abord ce fichier, `docs/work-state.md`, puis seulement les fichiers pertinents de la prochaine tâche. Vérifie les éventuels AGENTS.md du checkout et les changements concurrents. Ne recommence pas une analyse complète du dépôt. Travaille sur une tâche ciblée, tests ciblés avant suite complète, résumés courts, sécurité inchangée. Ne présente pas la bêta ou #26 comme terminées.

## Branche, PR et autorisations conservées

- Dépôt : https://github.com/shimon3/rapido
- Branche de travail : `work/beta-engine-guards-20261015`.
- PR #33 en brouillon : https://github.com/shimon3/rapido/pull/33 ; base `work/security-26-followup-20261015` de la PR #32, dépendante de #29. Ne pas changer cette base ni fusionner les piles sans revue.
- Dernier code validé : `d882f644ef195a8ad2f2a42da0a53946b5e86c43`. Un checkpoint documentaire ultérieur conserve exactement ce code et utilise `[skip ci]` ; son HEAD n'a pas lui-même exécuté la CI.
- `main` dernière valeur vérifiée : `18e0997ed0e09ed73d3723faef0904f2c5964af0`. La revérifier avant toute mutation distante.
- Autorisés par l'utilisateur : push ordinaire de commits sur branche dédiée, création/mise à jour de PR **en brouillon**, Actions **non publiantes** après inspection des workflows. Pas besoin de redemander ces autorisations.
- Interdits : modification directe de `main`, fusion, force-push, release, tag de publication, publication ou déploiement. Aucun test ni installation sur le PC de l'utilisateur, même si Claude y tourne. Les tests Windows doivent rester sur l'infrastructure isolée autorisée.
- Un seul workflow : `.github/workflows/windows.yml`. Build/PR Contents:read, publication uniquement sur push de tag `v*` et succès du build ; aucun déploiement. La branche de travail ne déclenche pas de push build, la PR déclenche la validation. **Ces protections ne sont pas encore sur main**, qui conserve son ancien mécanisme de publication ; ne pas le lancer/modifier.

## Dernière validation vérifiée

[CI Windows #197](https://github.com/shimon3/rapido/actions/runs/38715835112) SUCCESS sur `d882f64` ; build job `116358174709`, release job `116359977859` ignoré.

- 225 régressions passées, 5 fixtures signées ignorées dans la suite générale après exécution dédiée, 120 sous-tests et 1 avertissement existant.
- Signatures : 15 tests passés sans skip, 39 sous-tests : 9 tests unitaires/politique, 1 fichier réellement non signé et 5 tests de PE réellement signés. Ces comptes recoupent la suite générale : ne pas les additionner ni appeler les 15 des fixtures signées réelles.
- pip check et 41 réponses PyPI de versions précises vérifiés. Une liste d'avis vide n'établit pas l'absence de toutes vulnérabilités.
- Compilations, fenêtres WebView2/engine, protocole natif, installation/désinstallation/coexistence portable et Firefox **157.0.1** réels réussis, dont transfert automatique et téléchargement dans Firefox sans hôte natif.
- Firefox de CI épinglé à l'installateur Mozilla officiel : SHA-512, signature Mozilla valide, versions installée et WebDriver contrôlées. Fixture CI non distribuée ; ne pas modifier les règles d'admission pour accepter un navigateur dans un cache utilisateur.
- Runner **Windows Server 2025**, pas certification Windows 10/11.
- Dernière suite Linux : 194 passed /36 skips de plateforme-fixture /116 subtests /1 warning. Ciblés registre/lancement/hôte/publication : 28 passed /7 skips /18 subtests.

## Ce qui vient d'être corrigé

`native_registration.py` : un JSON non objet pouvait interrompre le nettoyage ; des doublons/non-finis pouvaient être acceptés ; une propriété de registre ou un manifeste étranger introduit après le premier contrôle pouvait être adopté/écrasé.

Lecture désormais limitée à 16 KiB de fichier régulier, JSON UTF-8 strict et sans doublons/non-finis, refus des objets invalides ou trop imbriqués. Les fichiers corrompus sont conservés et les autres navigateurs nettoyés. Tous les fichiers sont préparés puis les manifestes et propriétaires du registre revérifiés avant la première écriture. Tests d'injection après précontrôle et test réel sous une clé Windows unique, avec manifeste Chrome `null`, nettoyage Firefox et propriétaire Edge étranger conservé.

Limites : les changements après le dernier contrôle et les écritures registre partiellement échouées ne sont pas une transaction atomique. Des fichiers légitimes nouvellement préparés peuvent rester pour réparation/désinstallation. Aucun rollback risqué supprimant un fichier remplacé n'a été ajouté. **Cette correction ne ferme pas #26.**

Les étapes précédentes (déjà validées, ne pas réappliquer) sont résumées dans `docs/work-state.md` : IPC privé, garde-fous moteur, confirmations UI, concurrence des redémarrages, contrôles des liens/jonctions, primitive Authenticode et preuves de licences/charge utile.

## #26 : séparation exacte du travail restant

- Déjà réalisé : identité noyau SID/processus/parent/pipe, origines exactes, garde-fous de liens et de propriété, primitive Authenticode à fichier tenu ouvert avec pin SHA-256 explicite, tests Windows. La primitive reste **hors admission de production**.
- Il manque pour défendre contre le remplacement par un programme du même utilisateur : installation/ancêtres/politique indépendamment protégés, signataire et cycle versions/révocation/renouvellement, protection complète des DLL/Python/PyInstaller/extraction, sélection de l'hôte imposée au navigateur avant transfert. Aucun signataire de production ni ancre gérée n'est fourni.
- Une signature seule, un hash adjacent, DPAPI, HKCU ou une variable d'environnement ne remplacent pas cette ancre. Ne pas brancher le vérificateur seul et déclarer #26 résolu.
- Lire `docs/windows-executable-integrity-threat-model.md` et `docs/windows-managed-integrity-contract.md` pour les prérequis/matrice ; le profil géré est une proposition, pas une implémentation. Injection, écrivains mappés et toutes les courses des ancêtres ne sont pas couverts.

## Prochaine tâche autonome utile

Passer au dossier de redistribution **licences et sources** déjà identifié : LGPL de pystray, MPL de certifi, conflit MIT/BSD de proxy_tools, attribution/provenance des composants natifs et obligations de sources/remplacement. Lire les versions exactes dans `packaging/constraints-windows-build.txt` et l'inventaire, puis `scripts/collect_license_evidence.py` et ses tests. Utiliser les textes et sources primaires exacts ; préparer ce qui manque sans inventer d'autorisation ou déclarer une conformité complète à partir des seules notices.

Preuves actuelles : artefact **#190**, pas les ZIP #195–197. Archive #190 `11954004962`, SHA-256 `46713a203094f27e1b5600358701df2d056c25d9bca75c7092612594bd4929fc` : 154 fichiers payload, 55 binaires natifs embarqués, 117 textes de licence, Python et LICENSE projet, 5 DLL SDK WebView2 +2 textes originaux et 41 versions/réponses PyPI vérifiés indépendamment. Les ZIP suivants n'ont pas été retéléchargés/inspectés indépendamment ; ne pas leur attribuer les hashes #190.

Fichiers de référence : `docs/beta-readiness-20261015.md`, `docs/beta-build-inventory-20261015.json`, `docs/beta-payload-inspection-20261015.json`, `docs/dependency-advisory-snapshot-20261015.json` et `packaging/licenses/`. Les noms de modules candidats par RECORD ne prouvent pas l'identité du bytecode ; VERSIONINFO ne prouve pas le signataire.

Titulaire confirmé par le propriétaire le 15 octobre 2026 : Samuel Bentouza (LICENSE, installateur, ressources de version alignés). Ne pas inventer une validation de similarité avec IDM.

Ensuite : vraies VM Windows 10/11 propres, Chrome/Edge/Firefox et chemins privés/cookies/absence d'hôte/redémarrage/mise à jour/erreurs/clavier, Defender, version bêta distincte et réparation/rollback. Ces étapes restent ouvertes. Pas de nouvelle fonctionnalité non essentielle ; #8/#9 différées. Préparer les PR pour revue, attendre l'accord avant fusion.

## Reprise technique sans gaspillage

Dans l'environnement Codex actuel seulement : checkout `/workspace/scratch/a15d48cb1e30/rapido`, Python Linux `/workspace/scratch/a15d48cb1e30/rapido-test-venv/bin/python`. Ne pas supposer ces chemins présents chez Claude. Vérifier branche/HEAD/status et préserver tout travail concurrent avant de récupérer le dépôt. Ne pas exécuter les tests sur le PC utilisateur.

Git CLI local sait lire/fetch, mais n'a pas de credentials de push. Le connecteur GitHub a servi à créer arbre/commit puis avancer la référence avec parent et SHA attendus, `force=false`. Vérification distante après push. Pour resynchroniser ce checkout : fetch, comparer l'index à FETCH_HEAD, puis soft reset **uniquement si identiques**. Pas de reset destructif.

Arguments du connecteur si disponible : create_tree(repository_full_name, base_tree_sha, tree_elements), create_commit(repository_full_name, tree_sha, parent_sha, message), update_ref(repository_full_name, branch_name, sha, expected_sha, force=false). fetch_pr(repo_full_name, pr_number) renvoie structuredContent.pull_request ; logs dans structuredContent.content. Ne pas imprimer les diffs complets de PR ou journaux entiers.

À la fin de chaque tâche : tests ciblés, CI adaptée, contrôle des workflows avant push, mise à jour du suivi sur cette branche. Bilan court : tâche, résultat, tests, commit, blocage. Aucun travail ne continue automatiquement après la fin de la session.
