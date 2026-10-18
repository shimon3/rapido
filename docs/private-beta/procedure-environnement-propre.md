# Procédure de test sur un environnement Windows propre

But : prouver, avant d'envoyer la bêta aux testeurs, que **le fichier exact
qui leur sera remis** s'installe, fonctionne et se désinstalle sur un Windows
10 et un Windows 11 sans état antérieur.

Exécutant : Samuel, ou une personne qu'il autorise, sur des machines de test
qu'il désigne. Cette procédure n'a **pas** été exécutée par l'assistant, qui
n'a pas accès aux machines.

Durée : environ 1 h 30 par système (préparation comprise).

## 0. Obtenir le candidat (une seule fois)

1. Ouvrir le run GitHub Actions vert du commit candidat (onglet *Actions*,
   workflow *Windows build*).
2. Copier le bloc **SHA-256** du résumé du job (*Summary*). C'est la
   référence, enregistrée par GitHub indépendamment des fichiers.
3. Télécharger l'artefact `UNPUBLISHED-Rapido-1.3.0-beta.1-windows` (il
   **expire après 14 jours**). Conserver le ZIP dans un dossier d'archive.
4. Vérifier `SHA256SUMS.txt` contre le résumé du job :

   ```powershell
   Get-FileHash .\Rapido-Setup-1.3.0-beta.1.exe, .\Rapido-1.3.0-beta.1-portable.zip -Algorithm SHA256
   ```

5. Noter le commit et le numéro du run dans `checklist-windows.md`.

## 1. Préparer chaque machine

| Point | Windows 10 | Windows 11 |
| --- | --- | --- |
| Édition et build | Pro 22H2, build 19045, à jour | Pro, version actuelle, à jour |
| Compte | Compte **standard** (non administrateur) dédié au test | idem |
| Rapido | Jamais installé, ou instantané pris avant toute installation | idem |
| Navigateurs | Chrome, Edge, Firefox stables, à jour | idem |
| Sécurité | SmartScreen et Microsoft Defender **activés** (ne rien désactiver) | idem |
| Instantané | « propre-avant-rapido » pris maintenant | idem |

Sur une VM : vérifier qu'aucun dossier partagé avec le PC principal n'est monté.

## 2. Déroulé

1. Copier l'installateur et le ZIP sur la machine par le moyen prévu pour les
   testeurs (téléchargement navigateur). Les fichiers reçoivent ainsi la
   marque « provenant d'Internet » et SmartScreen se comporte comme chez un
   testeur.
2. Copier `scripts\collect_candidate_evidence.ps1` du commit candidat sur la
   machine (il n'est pas inclus dans l'installateur), puis relever l'état
   initial (lecture seule) :

   ```powershell
   powershell -NoProfile -ExecutionPolicy Bypass -File .\collect_candidate_evidence.ps1 -Phase before -OutputPath .\avant.json -AuthorizedTestMachine
   ```

3. Vérifier les empreintes (étape 1 du guide du testeur).
4. Dérouler `checklist-windows.md`, sections A à F, en notant chaque résultat.
5. Relever l'état final :

   ```powershell
   powershell -NoProfile -ExecutionPolicy Bypass -File .\collect_candidate_evidence.ps1 -Phase after -OutputPath .\apres.json -AuthorizedTestMachine
   ```

6. Revenir à l'instantané « propre-avant-rapido ».

## 3. Preuves à archiver

Dans `docs/private-beta/validation-<win10|win11>-<date>.md` :

- commit, numéro de run, empreintes ;
- checklist remplie (OK / KO / non testé, avec commentaire) ;
- `avant.json`, `apres.json` ;
- captures : écran SmartScreen, fenêtre principale, extension installée ;
- tout message d'antivirus.

## 4. Règle d'arrêt

Arrêter et ne **pas** envoyer la bêta si l'un de ces cas se produit :
empreinte différente, demande de droits administrateur, alerte antivirus non
expliquée, plantage au premier lancement, désinstallation qui laisse
`Rapido.exe` ou des enregistrements de navigateur.
