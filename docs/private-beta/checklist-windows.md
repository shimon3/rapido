# Checklist de validation Windows 10 / 11 — bêta privée non signée

Candidat : commit `__________` · run Actions `__________` ·
SHA-256 installateur `__________`

Remplir une colonne par système. « CI » = déjà couvert automatiquement sur
Windows Server 2025 (utile, mais ne remplace pas Windows 10/11).

| # | Contrôle | CI | Win 10 | Win 11 |
| --- | --- | --- | --- | --- |
| **A** | **Fichier** | | | |
| A1 | Empreintes du fichier reçu = résumé du job GitHub | — | ☐ | ☐ |
| A2 | `Get-AuthenticodeSignature` → `NotSigned` (attendu, aucune autre signature) | — | ☐ | ☐ |
| A3 | SmartScreen : écran « Éditeur inconnu » relevé (capture) | — | ☐ | ☐ |
| A4 | Defender : aucune alerte (sinon, noter le nom de la détection) | — | ☐ | ☐ |
| **B** | **Installation** | | | |
| B1 | Installation sans demande de droits administrateur | ✔ | ☐ | ☐ |
| B2 | Installé dans `%LOCALAPPDATA%\Programs\Rapido` | ✔ | ☐ | ☐ |
| B3 | Premier lancement : fenêtre principale (WebView2) affichée | ✔ | ☐ | ☐ |
| B4 | Icône de zone de notification : Afficher, Masquer, Quitter | — | ☐ | ☐ |
| B5 | `rapido.log` sans « Traceback » après le premier lancement | — | ☐ | ☐ |
| **C** | **Téléchargements** | | | |
| C1 | Téléchargement simple, fichier complet et lisible | ✔ (self-test) | ☐ | ☐ |
| C2 | 3 téléchargements simultanés | — | ☐ | ☐ |
| C3 | Coupure réseau puis reprise, fichier correct | — | ☐ | ☐ |
| C4 | Pause et reprise manuelles | — | ☐ | ☐ |
| **D** | **Navigateurs** | | | |
| D1 | Chrome : extension installée par le chemin normal, téléchargement repris par Rapido | — | ☐ | ☐ |
| D2 | Edge : idem | — | ☐ | ☐ |
| D3 | Firefox : idem | ✔ (vrai Firefox) | ☐ | ☐ |
| D4 | Rapido fermé : le navigateur télécharge lui-même (pas de perte) | ✔ (Firefox) | ☐ | ☐ |
| **E** | **Cycle de vie** | | | |
| E1 | Mise à niveau depuis la version précédente (si un testeur l'a) : réglages conservés | — | ☐ | ☐ |
| E2 | Réinstallation par-dessus la même version | — | ☐ | ☐ |
| E3 | Réparation : supprimer `RapidoNativeHost.exe` puis relancer l'installateur, fichier restauré | — | ☐ | ☐ |
| E4 | Désinstallation : dossier programme vidé, autres processus intacts | ✔ | ☐ | ☐ |
| E5 | Clés HKCU `NativeMessagingHosts` de Rapido supprimées | ✔ | ☐ | ☐ |
| E6 | `%USERPROFILE%\.rapido` et fichiers téléchargés conservés | — | ☐ | ☐ |
| E7 | Version portable : fonctionne seule, et après désinstallation de la version installée | ✔ | ☐ | ☐ |
| **F** | **Sécurité visible** | | | |
| F1 | `http://127.0.0.1:<port>/api/state` sans authentification → 403 | ✔ | ☐ | ☐ |
| F2 | Aucune mise à jour automatique téléchargée ou lancée | ✔ (test) | ☐ | ☐ |
| F3 | Notice de sécurité remise et comprise (lien dans le message d'envoi) | — | ☐ | ☐ |

**Validé pour envoi** si A1, A2, B1–B5, C1–C3, au moins un navigateur de D,
E4–E6 et F1–F2 sont OK sur **les deux** systèmes. Toute case KO doit avoir
une issue et une décision écrite.
