# Bêta privée non signée — conditions de distribution

Périmètre : Rapido 1.3.0-beta.1, installateur et ZIP **non signés**, remis
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

## Ce qu'il ne faut pas faire

- Ne pas créer de release GitHub ni de tag `v*`, ne pas publier de lien
  public, et ne pas déposer le fichier sur un site de partage ouvert.
- Ne pas demander aux testeurs de désactiver leur antivirus ou SmartScreen.
- Ne pas présenter la bêta comme sûre face à un logiciel malveillant local.

## Règle GO / NO-GO

**GO** quand les conditions 1 à 8 sont toutes cochées, avec leurs preuves
archivées. **NO-GO** tant qu'une seule manque. Le verdict à jour et ses
preuves figurent dans `docs/beta-publication-checklist.md`, partie Track P.
