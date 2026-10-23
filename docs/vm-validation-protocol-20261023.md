# Protocole de validation VM — correctifs du 2026-10-23

Ce protocole complète `private-beta/checklist-windows.md` et
`private-beta/procedure-environnement-propre.md`. Il vise les correctifs de la
branche `dev/autonomous-rapido-20261023` et les anomalies encore ouvertes.

**À exécuter uniquement sur des VM de test autorisées (Windows 10 22H2 et
Windows 11 23H2 ou plus récent). Jamais sur le PC principal.**

## 0. Pré-requis

| # | Élément | Détail |
| --- | --- | --- |
| P1 | Candidat | Build CI non publiée de la branche, après push autorisé par le propriétaire. Noter commit, run, SHA-256 de l'installateur, du ZIP portable, de `Rapido.exe` et `RapidoNativeHost.exe` |
| P2 | VM | Windows 10 22H2 **et** Windows 11. UAC actif (`EnableLUA=1`), Defender et SmartScreen par défaut |
| P3 | Comptes | `rtest-std` (standard, **sans** droits administrateur) et `rtest-adm` (administrateur, UAC actif). Profils neufs |
| P4 | Instantané | « propre-avant-rapido » pris **après** mise à jour de Chrome, Edge, Firefox et WebView2 |
| P5 | Outils | Sysinternals Process Explorer, Process Monitor, ProcDump (copiés dans `C:\Tools`, pas installés) |
| P6 | Réseau | Coupure par la carte virtuelle de l'hyperviseur (pas par le pare-feu Windows) |
| P7 | Preuves | Dossier `C:\Evidence\<date>-<win10|win11>-<compte>` ; une capture par écran demandé |

Règle d'arrêt : un écran SmartScreen, Defender ou UAC inattendu est **capturé,
puis on s'arrête**. Rien n'est contourné sans décision écrite du propriétaire.

## 1. Relevé initial (lecture seule)

```powershell
.\scripts\collect_candidate_evidence.ps1 -Phase before -OutputPath C:\Evidence\avant.json -AuthorizedTestMachine
reg query "HKCU\Software\Google\Chrome\NativeMessagingHosts" /s   > C:\Evidence\nmh-avant.txt
reg query "HKCU\Software\Microsoft\Edge\NativeMessagingHosts" /s >> C:\Evidence\nmh-avant.txt
reg query "HKCU\Software\Mozilla\NativeMessagingHosts" /s        >> C:\Evidence\nmh-avant.txt
reg query "HKCU\Software\Microsoft\Windows NT\CurrentVersion\AppCompatFlags\Layers" > C:\Evidence\compat-avant.txt
reg query "HKCU\Software\Microsoft\Windows NT\CurrentVersion\AppCompatFlags\Compatibility Assistant\Store" >> C:\Evidence\compat-avant.txt
Get-ChildItem $env:TEMP -Directory | Where-Object { Test-Path (Join-Path $_.FullName 'EBWebView') } | Measure-Object | Select-Object Count > C:\Evidence\ebwebview-avant.txt
```

Vérifier aussi `Get-ItemProperty HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\System`
→ `EnableLUA`, `ConsentPromptBehaviorAdmin`, `EnableInstallerDetection` (à noter, pas à changer).

## 2. Installation — demande UAC (anomalie 1, cause non établie)

Faire chaque cas sur l'instantané propre, **dans cet ordre**. Le journal Inno
Setup (`/LOG`) dit si l'installateur a tourné élevé : chercher dans le journal les
lignes `Administrative install mode`, `Running as administrator` (ou
`Non administrative install mode`, `User privileges: None`).

| # | Compte | Fichier | Lancement | Relever |
| --- | --- | --- | --- | --- |
| U1 | `rtest-std` | Marqué Internet (`Zone.Identifier` ZoneId=3) | Double-clic dans l'Explorateur | SmartScreen ? UAC ? (un compte standard verrait une demande d'identifiants administrateur) |
| U2 | `rtest-adm` | Marqué Internet | Double-clic ; SmartScreen « Exécuter quand même » si le propriétaire l'a autorisé | UAC ? Capture |
| U3 | `rtest-adm` | Copie débloquée (`Unblock-File`) | Double-clic | UAC ? Si U2 = UAC et U3 = pas d'UAC, la cause est le chemin SmartScreen |
| U4 | `rtest-adm` | Débloquée | `Rapido-Setup-….exe /LOG="C:\Evidence\setup-u4.log"` depuis une console **non** élevée | Journal : mode d'installation |
| U5 | `rtest-adm` | Marqué Internet | Le double-clic ne passe pas `/LOG` : `Start-Process .\Rapido-Setup-….exe -ArgumentList '/LOG=C:\Evidence\setup-u5.log'` depuis une console non élevée | Journal + UAC ; comparer à U2 |

Pour chaque cas :

1. Process Explorer ouvert, colonne « Integrity » affichée : relever le niveau
   (`Medium` attendu, `High` = élevé) de `Rapido-Setup-….exe`, de
   `Rapido-Setup-….tmp` et de `Rapido.exe` lancé en fin d'installation.
2. Propriétaire du dossier : `(Get-Acl "$env:LOCALAPPDATA\Programs\Rapido").Owner`
   (`BUILTIN\Administrators` = installation élevée).
3. Relire `AppCompatFlags\Layers` et `Compatibility Assistant\Store` après
   l'installation : une entrée `RUNASADMIN` ou une nouvelle entrée pour l'installateur
   indique un marquage de compatibilité.
4. Désinstaller (section 3) et restaurer l'instantané avant le cas suivant.

Critère : **aucune élévation dans U1, U3 et U4.** Si seule U2/U5 élève, documenter
« élévation déclenchée par le parcours SmartScreen », sans changer le produit.

## 3. Désinstallation et registre (anomalie 2, corrigée dans le code)

1. Fermer Rapido par l'icône (Quitter), vérifier qu'aucun `Rapido.exe` ni
   `RapidoNativeHost.exe` ne tourne.
2. Process Monitor : filtre `Path contains Rapido` et `Path contains com.rapido.bridge`,
   capture active.
3. Paramètres > Applications > Rapido > Désinstaller (et une fois en silencieux :
   `unins000.exe /VERYSILENT /LOG="C:\Evidence\uninstall.log"`).
4. Contrôles :

| # | Contrôle | Attendu |
| --- | --- | --- |
| R1 | `reg query "HKCU\Software\Google\Chrome\NativeMessagingHosts\com.rapido.bridge"` (idem Edge, Mozilla), vues 32 et 64 bits (`/reg:32`, `/reg:64`) | « Le système n'a pas trouvé la clé » pour les 3 navigateurs : **aucune clé vide** |
| R2 | Clé parente `…\NativeMessagingHosts` | Présente si elle existait avant (comparer à `nmh-avant.txt`). Si Rapido l'a créée (navigateur absent), elle peut rester : noter, non bloquant |
| R3 | `HKCU\…\Run` valeur `Rapido` | Absente |
| R4 | `%LOCALAPPDATA%\Programs\Rapido` | Absent. S'il reste un dossier vide, Process Monitor dit quel processus le tenait (`CreateFile`/`SetDispositionInformationFile` en échec) |
| R5 | `%USERPROFILE%\.rapido`, fichiers téléchargés | **Conservés** (E6) |
| R6 | Autre installation (portable) enregistrée avant la désinstallation | Son enregistrement est conservé |
| R7 | Extensions Chrome/Edge/Firefox | Toujours présentes (attendu) : les retirer à la main, puis vérifier qu'aucun fichier de profil ne mentionne Rapido |

5. Tests de catégorie 2 sur la VM (un venv de test, compte `rtest-adm`) :

```powershell
python -m pytest -q tests/test_native_registration.py::RealRegistrationTests
python -m pytest -q tests/test_release_signing_scripts.py::test_candidate_verification_runs_and_rejects_a_mismatch
```

## 4. Navigateurs réels (Chrome, Edge, Firefox)

Profils neufs, extension chargée par le chemin normal (Chrome/Edge : Mode
développeur > Charger l'extension non empaquetée, dossier
`%LOCALAPPDATA%\Programs\Rapido\extension` / `extension-edge` ; Firefox : module
temporaire `about:debugging` ou XPI de test).

| # | Navigateur | Scénario | Attendu |
| --- | --- | --- | --- |
| N1 | Chrome, Edge, Firefox | Popup de l'extension | « Connecté à Rapido » |
| N2 | Tous | Lien direct `.zip` ≥ 1 Mo sur un site public sans connexion | Le navigateur annule, Rapido reprend, une seule entrée, fichier correct |
| N3 | Tous | Clic droit « Télécharger avec Rapido » | Fenêtre de capture Rapido |
| N4 | Tous | Rapido quitté, même lien | Le navigateur télécharge lui-même, aucune perte |
| N5 | Tous | Page nécessitant une connexion (cookie) | Laissé au navigateur (S3) |
| N6 | Firefox | Fenêtre privée | Laissé au navigateur |
| N7 | Tous | 5 liens en rafale | 5 fenêtres de capture, Rapido reste réactif |

Pour chaque cas : capture, puis `rapido.log` sans `Traceback`.

## 5. Téléchargements et reprise après coupure

Fichiers **signés** pour que toute corruption soit détectée : installateur
Firefox (≈ 95 Mo) et installateur Python 3.13 (≈ 28 Mo), depuis leurs sites
officiels. Noter les SHA-256 publiés quand ils existent.

| # | Scénario | Attendu |
| --- | --- | --- |
| T1 | Téléchargement simple | `Get-AuthenticodeSignature` = `Valid`, SHA-256 = référence |
| T2 | Pause à ~30 %, attendre 1 min, reprise ; refaire 3 fois | Valid + SHA identique ; jamais de retour à 0 % |
| T3 | Coupure de la carte réseau à ~50 % pendant 30 s puis rétablissement | Reprise automatique ou « Reprendre » manuel ; Valid + SHA identique |
| T4 | Coupure de 3 min (au-delà des essais) | Erreur affichée, « Reprendre » termine le fichier, Valid + SHA identique |
| T5 | Quitter Rapido pendant un téléchargement, relancer, reprendre | Progression conservée, Valid + SHA identique |
| T6 | Ouvrir un `.exe` terminé depuis Rapido, **laisser la fenêtre UAC ouverte 30 s** et, pendant ce temps, mettre un autre téléchargement en pause | L'interface reste réactive (correctif `a088036`) ; annuler l'UAC n'affiche pas d'erreur |

## 6. Blocages (« Application Hang ») et journaux Windows

1. Avant le test : `Get-WinEvent -FilterHashtable @{LogName='Application'; ProviderName='Application Hang','Application Error'} -MaxEvents 50`
   → `C:\Evidence\events-avant.txt`.
2. ProcDump prêt à capturer un blocage :
   `C:\Tools\procdump.exe -accepteula -h -ma -w Rapido.exe C:\Evidence\dumps`
   (`-h` : vidage quand la fenêtre ne répond plus).
3. Scénarios, chacun 10 min : N7 (rafale), 2e lancement de `Rapido.exe` pendant
   une capture, ouverture/fermeture répétée de la fenêtre principale depuis
   l'icône, T6.
4. Après : relire les journaux Windows (même commande) et `rapido.log` ; chercher
   `fil graphique bloque` (vidage des piles écrit par `UiWatchdog`).
5. Joindre au rapport : événements, vidage ProcDump, extrait du journal autour du
   blocage. Ne pas déclarer le problème résolu sans ce type de preuve.

## 7. Stabilité avec RAM limitée

1. VM réglée à **2 Go** de RAM (comme la VM du 16/10), puis à 4 Go pour comparer.
2. Ouvrir Chrome avec 10 onglets, Edge avec 5, puis Rapido.
3. Pendant 30 min : 3 téléchargements simultanés, captures N7 toutes les 5 min,
   T2 sur un des fichiers.
4. Relever toutes les 5 min (Process Explorer ou `Get-Process`) : mémoire de
   `Rapido.exe` et des `msedgewebview2.exe`, nombre de handles. Une croissance
   continue = fuite à analyser.
5. Critères : aucun « Application Hang », aucun `Traceback`, tous les fichiers
   Valid + SHA correct, mémoire stabilisée.

## 8. Dossiers temporaires EBWebView (anomalie ouverte)

1. Compter les dossiers `%TEMP%\tmp*\EBWebView` avant et après chaque scénario
   (commande de la section 1).
2. Cas à distinguer : Quitter par l'icône ; fermeture de session Windows avec
   Rapido ouvert ; mise à niveau par l'installateur avec Rapido ouvert ; arrêt
   forcé (Gestionnaire des tâches).
3. Relever la ligne `[pywebview] Failed to delete user data folder` de `rapido.log`
   et la relier au cas. **Ne rien supprimer** dans `%TEMP%` pendant le test.

## 9. Fin de test

1. `collect_candidate_evidence.ps1 -Phase after` et différence avec `avant.json`.
2. Archiver `C:\Evidence` (hors VM), remplir `checklist-windows.md` (une colonne
   par système), restaurer l'instantané propre.

## 10. Correctifs de la nuit du 2026-10-23 à confirmer sur la build

| # | Vérification | Attendu |
| --- | --- | --- |
| V1 | Démarrer et quitter Rapido 3 fois (icône > Quitter) | Aucun nouveau `%TEMP%\tmp*\EBWebView` ; dossier `%USERPROFILE%\.rapido\WebView2` présent pendant l'exécution, absent (ou réutilisé) ensuite |
| V2 | Pendant un téléchargement vidéo, « Fin de tâche » sur `Rapido.exe` dans le Gestionnaire des tâches | Aucun processus `Rapido.exe` enfant (yt-dlp) ne reste ; au redémarrage, la vidéo reprend sans doublon |
| V3 | Deux captures du même fichier (même nom) coup sur coup | Deux fichiers distincts (`nom.ext`, `nom (1).ext`), contenus corrects |
| V4 | Copier un fichier du même nom dans le dossier de destination pendant un téléchargement | Le fichier copié est intact ; le téléchargement se termine sous `nom (1).ext` |
| V5 | Sélectionner 200 éléments puis « Suspendre » / « Reprendre » | Interface réactive ; un seul enregistrement de l'historique par action |
| V6 | Ouvrir un `.exe` téléchargé et laisser la fenêtre UAC ouverte 30 s | L'interface et les autres téléchargements continuent (correctif de la phase 1) |
| V7 | Lancer `Rapido.exe` une 2e fois pendant une activité intense | Fenêtre existante ramenée au premier plan ; jamais « port utilisé par un autre programme » |
| V8 | Vérifier `%USERPROFILE%\.rapido` après ces essais | Aucun fichier `ck-*.txt` ; pas de `*.unreadable-*` sauf fichier réellement abîmé |
