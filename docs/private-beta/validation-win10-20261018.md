# Validation Windows 10 — bêta privée 1.3.0-beta.1 — 2026-10-18

Statut : **préparation et contrôles en lecture seule uniquement.** Aucune
installation, aucun transfert de fichier vers la VM, aucune modification.
L'installation n'est pas encore autorisée.

## Candidat

| Élément | Valeur | Contrôle |
| --- | --- | --- |
| Run CI | https://github.com/shimon3/rapido/actions/runs/39125658661 (succès, `pull_request`) | — |
| Commit de tête | `4a4a03ba8fbe9985e161a4207ad6c23241da048c` (= tête actuelle de la branche) | `ci-artifact-provenance.json` → `head_commit` |
| Artefact | `UNPUBLISHED-Rapido-1.3.0-beta.1-windows`, id 12136003020, 80 773 512 octets, expire le 2026-11-01 | API GitHub |
| Condensat de l'archive | `sha256:da2813b6c2ee89fb629e50420341fda530b52aaa7cfb4574684d94cfd6b9c4ef` | Calculé sur l'original téléchargé = condensat GitHub ✔ |
| `Rapido-Setup-1.3.0-beta.1.exe` | `a679165b7fa04bad733a1907bf46abd7f4c82ed2f07873238091a90e2a551d01` | = `SHA256SUMS.txt` ✔, = journal CI ✔ |
| `Rapido-1.3.0-beta.1-portable.zip` | `8c5c5dd1b38d7ecd1fa97510760b69adaeb6d3ffc37252cbbb73897955c9c4d3` | = `SHA256SUMS.txt` ✔, = journal CI ✔ |
| `Rapido.exe` (dans le ZIP portable) | `05274ae93be2e711568542e3c2dcb902e834434a2b4a30a7a05846044fa3c84e` | = `SHA256SUMS.txt` ✔, = journal CI ✔ |
| `RapidoNativeHost.exe` (dans le ZIP portable) | `85be1ae12b37e2824aa7c5c5cb77b12b3e34d6430ca65fd24f6a4d885ed7cadf` | = `SHA256SUMS.txt` ✔, = journal CI ✔ |
| Provenance | `official_release=false`, `production_signed=false` | ✔ |

L'archive originale est conservée en lecture seule dans l'espace de test de la
session Claude. Seule une copie extraite a servi aux comparaisons. Rien n'a été
exécuté.

## Identité de la VM

| Contrôle | Résultat |
| --- | --- |
| Clé d'hôte SSH présentée | ED25519 `SHA256:uPKOuDRiQdBQo7FOTvrJrSFVfbjHFIgQtmd42UYaxXQ` = clé déjà connue (aucune nouvelle clé acceptée) ✔ |
| Nom de machine | `DESKTOP-F2ALUG9`, différent du PC principal `DESKTOP-O535E49` ✔ |
| Compte | `desktop-f2alug9\samue` |
| Système | Windows 10 Pro 22H2, build 19045.6466 ✔ (cible de la checklist) |
| Matériel | VMware20,1, 2 Go de RAM, 12,7 Go libres sur C: |

## État relevé (lecture seule)

| Point | Constat | Conforme à la procédure ? |
| --- | --- | --- |
| Rapido déjà installé | Oui : 1.3.0-beta.1 **ancienne build** (`Rapido.exe` `ce6a7c5c…01f5` = CI #218), processus lancé, démarrage automatique actif, entrée de désinstallation présente | **Non** : la machine n'est pas propre |
| Enregistrements navigateur | `com.rapido.bridge` présent pour Chrome, Edge et Firefox (HKCU) | **Non** : reste de l'ancienne build |
| Données utilisateur | `%USERPROFILE%\.rapido` présent. Dossiers de test dans Téléchargements : `Rapido`, `Rapido-1.3.0-beta.1-windows (3)`, `testrapido-store-20261018` | **Non** |
| Compte de test | `samue` est membre des **Administrateurs** locaux | **Non** : la procédure demande un compte standard |
| UAC | Activé (`EnableLUA=1`) | ✔ |
| Microsoft Defender | Service, antivirus et protection en temps réel activés. Signatures du 2026-10-18 | ✔ |
| SmartScreen | Aucun réglage explicite (registre et stratégie vides), donc valeur par défaut de Windows | À confirmer visuellement dans Sécurité Windows |
| Navigateurs | Chrome 155.0.8059.80, Edge 155.0.4283.45, Firefox 158.0 | À mettre à jour avant le test |
| WebView2 Runtime | 155.0.4283.60 | ✔ |

## Limite technique pour SmartScreen et l'installation

SmartScreen n'agit que sur un fichier marqué « provenant d'Internet » et
**lancé depuis le bureau** (Explorateur). Une session SSH n'a pas de bureau
interactif : elle ne peut ni afficher ni relever l'écran SmartScreen, ni
tester l'icône de notification ou l'interface. Les sections A3, B1, B3, B4,
C et D de la checklist demandent donc une session graphique sur la VM
(console VMware ou Bureau à distance), conduite par Samuel ou explicitement
autorisée.

Si SmartScreen bloque l'installateur, la consigne est : relever l'écran
(capture), **arrêter**, ne rien contourner.

## Ce qui reste avant l'exécution Windows 10

1. **Restaurer un instantané propre** de la VM (sans Rapido), ou désinstaller
   l'ancienne build puis supprimer `.rapido` et les dossiers de test. Ce sont
   des écritures, donc une autorisation est nécessaire.
2. Créer ou utiliser un **compte standard** pour le test (B1 : aucune demande
   de droits administrateur).
3. Mettre à jour Chrome, Edge et Firefox.
4. Prendre l'instantané « propre-avant-rapido ».
5. Autoriser le transfert du candidat sur la VM **par téléchargement
   navigateur**, pour que la marque « Internet » soit présente.
6. Autoriser l'installation, puis dérouler `checklist-windows.md` en session
   graphique.

## Windows 11

Aucune machine Windows 11 n'est identifiée ni autorisée pour cette
validation. Le PC principal est exclu.

## Second relevé après désinstallation (compte `samue`, 12:23 UTC)

Identité reconfirmée : même clé ED25519 et `DESKTOP-F2ALUG9`. Lecture seule.

| Point | Constat | Statut |
| --- | --- | --- |
| Programme, processus, démarrage automatique, entrée de désinstallation | Absents | ✔ |
| `%USERPROFILE%\.rapido`, dossiers de test dans Téléchargements, menu Démarrer | Absents | ✔ |
| Clés HKCU `NativeMessagingHosts\com.rapido.bridge` (Chrome, Edge, Firefox) | **Présentes mais vides** (aucune valeur) | À supprimer. À surveiller au contrôle E5 du candidat |
| Extension Chrome | Toujours enregistrée dans `Secure Preferences`, chemin `...\Programs\Rapido\extension` (dossier supprimé) | À retirer dans `chrome://extensions` |
| Extension Edge « Rapido - Capture » 1.3.0.1 | Toujours enregistrée dans `Preferences` | À retirer dans `edge://extensions` |
| Firefox | Aucune mention dans `extensions.json` | ✔ |
| Bureau | `Rapido-1.3.0-beta.1-windows.zip` (ancien artefact) et `rapido_vm.pub` | Supprimer l'ancien ZIP |
| `%TEMP%` | 9 dossiers contenant `EBWebView` (anciennes sessions WebView2) | À supprimer (non bloquant) |
| Compte de test standard | Aucun : seul `samue` (administrateur) est actif | Non bloquant, voir le relevé suivant |
| Navigateurs | Inchangés : Chrome 155.0.8059.80, Edge 155.0.4283.45, Firefox 158.0 | À mettre à jour |

Constat utile pour le produit : la désinstallation de l'ancienne build (CI #218)
a laissé des clés de registre vides et les extensions de navigateur. Le
contrôle E5 sur le candidat dira si le problème existe toujours.

## Troisième relevé après nettoyage manuel (lecture seule)

Identité reconfirmée (même clé ED25519, `DESKTOP-F2ALUG9`).

| Point | Constat | Statut |
| --- | --- | --- |
| Clés HKCU `com.rapido.bridge` (Chrome, Edge, Firefox) | Absentes | ✔ |
| Extensions Chrome et Edge (fichiers de réglages) | Aucune mention de Rapido | ✔ |
| Ancien ZIP sur le Bureau | Absent | ✔ |
| Dossiers `EBWebView` dans `%TEMP%` | 0 | ✔ |
| Navigateurs | Chrome 155.0.8059.80, Edge 155.0.4283.45, Firefox 158.0 : **inchangés**. Chrome et Edge sont ouverts (une mise à jour peut attendre leur redémarrage) | **À faire** |
| Compte standard de test | Aucun. Seuls `samue` (administrateur) et `sshd` sont actifs | Non bloquant : UAC actif, le contrôle B1 se fait sur `samue` en lançant l'installateur depuis l'Explorateur (pas depuis une console administrateur). Un compte standard reste un test complémentaire |

Rapido ne laisse plus aucune trace sur le compte `samue`.

## État de départ retenu pour le test (lecture seule)

Identité reconfirmée (même clé ED25519, `DESKTOP-F2ALUG9`).

| Point | Valeur |
| --- | --- |
| Système | Windows 10 Pro 22H2, build 19045.6466 |
| Chrome | 155.0.8059.85 (mis à jour depuis .80) |
| Edge | 155.0.4283.62 (mis à jour depuis .45) |
| Firefox | 158.0 (« à jour » à confirmer dans sa page À propos) |
| WebView2 Runtime | 155.0.4283.60 |
| Rapido | Absent : aucun programme, clé HKCU, extension ni donnée |
| Compte de test | `samue` (administrateur, UAC actif). Installation à lancer depuis l'Explorateur |
| Defender | Antivirus et temps réel actifs |

## Transfert du candidat (option A : téléchargement navigateur par Samuel)

Samuel a téléchargé l'artefact sur la VM avec le navigateur, puis l'a
extrait avec l'Explorateur. Contrôle par SSH en lecture seule, identité
reconfirmée.

| Fichier sur la VM (`Téléchargements`) | SHA-256 | = référence | Marque « Internet » |
| --- | --- | --- | --- |
| `UNPUBLISHED-Rapido-1.3.0-beta.1-windows.zip` | `da2813b6…c4ef` | ✔ (= condensat GitHub) | ZoneId=3, HostUrl = stockage GitHub Actions |
| `Rapido-Setup-1.3.0-beta.1.exe` | `a679165b…1d01` | ✔ | ZoneId=3 (héritée de l'extraction) |
| `Rapido-1.3.0-beta.1-portable.zip` | `8c5c5dd1…c4d3` | ✔ | ZoneId=3 |
| `SHA256SUMS.txt` | `1656dd77…a1f7` | ✔ | ZoneId=3 |
| `ci-artifact-provenance.json` | `a6325711…5816` | ✔ | ZoneId=3 |
| `signing-plan.json` | `760665ff…7173` | ✔ | ZoneId=3 |
| `signing-rehearsal.json` | `5bdcee65…275d` | ✔ | ZoneId=3 |

Checklist A1 (empreintes) : **OK**. Rapido n'est pas encore installé.

## Résultat A3 — SmartScreen (session graphique, Samuel)

Action : double-clic sur `Rapido-Setup-1.3.0-beta.1.exe` depuis l'Explorateur
(fichier ZoneId=3, empreinte `a679165b…1d01`).

Résultat : **bloqué par Microsoft Defender SmartScreen.** L'écran « Windows a
protégé votre ordinateur » (interface en hébreu) indique que SmartScreen a
empêché le démarrage d'une application non reconnue. Seul le bouton « Ne pas
exécuter » est proposé, plus le lien « Informations complémentaires ».
Capture : `evidence/smartscreen-win10-20261018.png`.

Conformément à la consigne, **l'installation est arrêtée** et rien n'est
contourné. Les contrôles B à F ne sont pas exécutés.

| Contrôle | Statut |
| --- | --- |
| A1 empreintes | OK |
| A3 SmartScreen | Relevé : blocage « application non reconnue » |
| A2, A4, B à F | Non exécutés (installation arrêtée) |

Conséquence : sur un Windows 10 standard, un testeur ne peut installer cette
bêta non signée qu'en cliquant « Informations complémentaires » puis
« Exécuter quand même ». Décision du propriétaire requise.

## Décision du propriétaire sur le blocage SmartScreen (2026-10-18)

Samuel Bentouza accepte, **pour la bêta privée uniquement**, une exception
encadrée : après vérification de l'empreinte SHA-256, cliquer « Informations
complémentaires » puis « Exécuter quand même » **pour ce fichier précis**.
SmartScreen et Defender restent activés. Aucun réglage n'est modifié.
L'exception ne s'applique pas à une version publique, qui devra être signée.
Samuel réalise lui-même cette action sur la VM.

## Installation (Samuel, session graphique) et contrôle SSH en lecture seule

Parcours : SmartScreen « Informations complémentaires » puis « Exécuter
quand même » (exception autorisée). Ensuite, **une fenêtre UAC** est apparue
(« application d'un éditeur inconnu », origine : disque dur local) et Samuel a
répondu Oui. Enfin, la langue de l'installateur a été choisie (hébreu) et
l'installation est allée jusqu'au bout. Capture UAC : `evidence/uac-win10-20261018.png`.

| Contrôle | Résultat | Statut |
| --- | --- | --- |
| B1 aucune demande de droits | **Fenêtre UAC affichée.** Le manifeste de l'installateur est pourtant `asInvoker` et le script dit `PrivilegesRequired=lowest`. Les fichiers installés appartiennent à `BUILTIN\Administrators`, preuve que l'installateur a tourné élevé | **KO, cause à établir** (hypothèse : élévation déclenchée par le chemin SmartScreen « Exécuter quand même ») |
| B2 emplacement | `%LOCALAPPDATA%\Programs\Rapido`, 366 fichiers. Aucune entrée HKLM, désinstallation enregistrée dans HKCU (`Rapido 1.3.0-beta.1`, langue `he`) | OK |
| Identité des fichiers installés | `Rapido.exe` `05274ae9…c84e`, `RapidoNativeHost.exe` `85be1ae1…7cadf` = candidat ✔. Non signés (attendu) | OK |
| Droits | `samue` a FullControl sur le dossier, malgré le propriétaire Administrators | OK pour `samue`. À revoir pour une mise à jour lancée sans élévation |
| A4 Defender | 0 détection aujourd'hui | OK |
| B3 premier lancement | Processus `Rapido.exe` lancé par l'installateur (session 1, utilisateur `samue`) | En attente de confirmation visuelle par Samuel |
| B5 journal | `rapido.log` : un démarrage, 0 « Traceback » | OK |
| Enregistrements navigateurs | Chrome, Edge et Firefox (HKCU) pointent vers les manifestes installés, qui existent | OK |
| Démarrage automatique | `Rapido.exe --tray` dans HKCU\Run (option par défaut) | Noté |
| Menu Démarrer | Raccourcis Rapido, désinstallation et extension Chrome | OK |
| F1 API locale | `127.0.0.1:9614` : `/api/ping` 200, `/api/state` **403** sans authentification | OK |

Point ouvert : Rapido a été lancé par un installateur élevé. Une entrée
`postinstall` d'Inno Setup s'exécute normalement en tant qu'utilisateur
d'origine (non élevé), mais ce n'est pas prouvé ici. Pour la suite des tests,
Rapido est quitté puis relancé depuis le menu Démarrer.

## B3 / B4 — lancement et zone de notification (Samuel, session graphique)

| Contrôle | Résultat | Statut |
| --- | --- | --- |
| B3 fenêtre principale ouverte et lisible | Oui | OK |
| B4 icône : Masquer, Afficher, Quitter | Oui, l'icône disparaît après Quitter | OK |
| Relance depuis le menu Démarrer | Nouveau processus `Rapido.exe` (pid 8848, parent `explorer.exe`, donc non élevé). Journal : 2 démarrages, 0 « Traceback » | OK |

## C — premier essai de téléchargement : échec dû au serveur de test

Samuel a ajouté 4 téléchargements `proof.ovh.net` vers 15:59. Rapido affiche
`ConnectError: All connection attempts failed` pour l'un, et 0 o/s pour les 3 autres.

Diagnostic par SSH, en lecture seule :

- Internet fonctionne depuis la VM : TCP 443 vers 1.1.1.1 et GitHub OK, aucun
  proxy (WinHTTP, IE, variables d'environnement), pare-feu sans règle Rapido.
- `proof.ovh.net` (141.95.207.211) **ne répond plus en TCP 443** depuis la VM,
  alors qu'une requête HEAD avait réussi quelques minutes plus tôt. La VM n'a
  pas de route IPv6, et l'AAAA échoue aussi.
- Le `100Mb.dat` complet (104 857 600 octets) trouvé dans Téléchargements a été
  écrit à 15:58:18 par le **navigateur** (marque HostUrl), pas par Rapido.

Conclusion : le serveur de test bloque l'adresse de la VM après plusieurs
connexions. C'est extérieur à Rapido, et ce n'est pas un résultat valable
pour C1–C4. Les tests repartent avec `speedtest.tele2.net`, `python.org` et
le CDN Mozilla, tous vérifiés joignables avec `Accept-Ranges: bytes`.

Remarque produit : le message d'erreur et « Reprise possible : Non » sont
corrects tant qu'aucune connexion n'aboutit.

## C — téléchargements (Samuel dans l'interface, vérification par SSH en lecture seule)

Rapido range les fichiers par catégorie dans `~\Downloads\Rapido\`.

| # | Fichier | Taille obtenue = attendue | Preuve de contenu | Statut |
| --- | --- | --- | --- | --- |
| C1 | `Programmes\python-3.13.0-amd64.exe` (HTTPS) | 28 160 096 ✔ | Authenticode **Valid**, Python Software Foundation | OK |
| C2 | `Archives\100MB.zip` (HTTP) | 104 857 600 ✔ | SHA-256 = fichier de zéros de même taille (contenu servi par tele2) | OK |
| C2 | `Archives\10MB.zip` (HTTP) | 10 485 760 ✔ | idem | OK |
| C2 | `Programmes\Firefox Setup 158.0.exe` (HTTPS, après redirection) | 95 250 208 ✔ | Authenticode **Valid**, Mozilla Corporation | OK |
| C3/C4 | `Archives\1GB.zip` : pause puis reprise, et coupure réseau VMware puis reconnexion | 1 073 741 824 ✔, terminé à 16:09:15 | SHA-256 = 1 Gio de zéros | OK, avec réserve |

Réserve C3/C4 : le fichier de test ne contient que des zéros. Une reprise qui
laisserait un trou rempli de zéros ne serait donc pas détectée. Pour une
preuve forte, il faudrait refaire pause et coupure sur un fichier signé
(par exemple l'installateur Firefox, 95 Mo). Samuel n'a signalé aucun retour
à 0 % ni plantage.

Autres constats : journal sans « Traceback » (2 démarrages), Rapido toujours
lancé. `downloads.json` est chiffré (`private_state_enc`) : les adresses ne
sont pas lisibles en clair.
