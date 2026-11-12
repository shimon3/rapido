# Bêta privée non signée — conditions de distribution

Périmètre : Rapido 1.3.0-beta.2, installateur et ZIP **non signés**, remis
personnellement à **2 à 5 testeurs externes nommés**. Ce n'est ni une release
GitHub, ni un lien public.

## Documents

| Besoin | Document |
| --- | --- |
| Checklist de validation Windows 10/11 | `checklist-windows.md` |
| Procédure de test sur Windows propre | `procedure-environnement-propre.md` |
| Revue des licences bloquantes | `revue-licences-bloquantes.md` |
| Notice des limites de sécurité (pour les testeurs) | `notice-securite-version-non-signee.md` |
| Guide du testeur | `guide-testeur.md` |
| Retours et bugs | `retours-et-bugs.md` + `.github/ISSUE_TEMPLATE/` + `SECURITY.md` |

## Conditions nécessaires (toutes obligatoires)

1. **Candidat figé** : un commit, un run CI vert (tests, licences,
   installation et désinstallation, Firefox réel, répétition de signature),
   artefact `UNPUBLISHED-*` téléchargé et archivé avant son expiration à
   14 jours.
2. **Identité du fichier** : empreintes SHA-256 issues du résumé du job
   GitHub, envoyées aux testeurs par un **second canal**. Chaque testeur
   vérifie avant d'exécuter.
3. **Validation propre** : `checklist-windows.md` réussie sur Windows 10 **et**
   Windows 11 avec **ce** fichier exact, sans désactiver SmartScreen ni Defender.
4. **Consentement éclairé** : chaque testeur a reçu et accepté la notice de
   sécurité. Il sait que la version n'est pas signée et qu'elle ne protège pas
   contre un programme déjà présent sur son compte (issue #26).
5. **Diffusion limitée** : envoi individuel, pas de redistribution, liste des
   testeurs tenue par Samuel, désinstallation demandée en fin de bêta.
6. **Licences** : notices, textes et sources LGPL/MPL livrés dans
   `third-party/` (contrôlé par la CI), `payload.json` relu, commit source
   communiqué.
7. **Canal de retours** : un moyen privé (message, signalement de vulnérabilité
   GitHub) existe pour les données personnelles et la sécurité.
8. **Pas d'automatisme** : pas de mise à jour automatique. Toute nouvelle
   version suit à nouveau les étapes 1 à 3.

## Vérifier hors ligne l'artefact CI non publié

Après avoir téléchargé et extrait l'artefact GitHub depuis un **run réussi**,
relever sur GitHub le **run ID** et le commit réellement contrôlé par l'étape
`Record tested source commit`. Attention : sur une pull request, il peut
s'agir d'un commit de fusion de test GitHub, et non du SHA de tête de la PR.
Comparer ces identifiants à une source GitHub indépendante, pas seulement au
fichier `ci-artifact-provenance.json` contenu dans l'archive.

Dans un terminal à la racine du dépôt Rapido, lancer :

```powershell
python -m scripts.verify_unpublished_ci_artifact "C:\\chemin\\vers\\artefact-extrait" --run-id 123456789 --tested-source-commit <SHA-GITHUB-40-CARACTERES>
```

Remplacer les valeurs d'exemple par celles du run réellement téléchargé.
Le script lit uniquement les fichiers, vérifie les SHA-256 de l'installeur et
du ZIP, puis ceux des deux exécutables **à l'intérieur du ZIP**, sans les
exécuter. Il refuse les fichiers manquants, les fichiers supplémentaires,
les entrées ZIP dangereuses et les identifiants de run incompatibles.

**Important :** ce contrôle de cohérence utilise le `SHA256SUMS.txt` et le
JSON fournis avec l'artefact. Un attaquant pouvant remplacer **l'ensemble**
des fichiers peut aussi réécrire ces deux preuves. Le propriétaire doit donc
vérifier les empreintes indépendantes affichées dans le résumé GitHub Actions
du run original. Ce script ne vérifie pas Authenticode et ne rend pas le
candidat apte à une publication publique.

## Ce qu'il ne faut pas faire

- Ne pas créer de release GitHub ni de tag `v*`, ne pas publier de lien
  public, et ne pas déposer le fichier sur un site de partage ouvert.
- Ne pas demander aux testeurs de désactiver leur antivirus ou SmartScreen.
- Ne pas présenter la bêta comme sûre face à un logiciel malveillant local.

## Règle GO / NO-GO

**GO** quand les conditions 1 à 8 sont toutes cochées, avec leurs preuves
archivées. **NO-GO** tant qu'une seule manque. Le verdict à jour et ses
preuves figurent dans `docs/beta-publication-checklist.md`, partie Track P.
