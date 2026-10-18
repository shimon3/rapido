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
