# Recueillir les retours et les signalements de bugs (bêta privée)

Le dépôt `shimon3/rapido` est **public** : tout ce qui est écrit dans une
issue est visible par tous et indexé. La méthode sépare donc trois flux.

| Flux | Canal | Visibilité |
| --- | --- | --- |
| Bug fonctionnel, avis, suggestion | GitHub, formulaire **« Bêta privée — bug »** ou **« Bêta privée — avis »** (`.github/ISSUE_TEMPLATE/`), étiquettes `beta-privee` + `bug`/`feedback` | Public |
| Testeur sans compte GitHub, ou retour contenant des données personnelles | Message privé à Samuel. Samuel recopie dans une issue une version **sans données personnelles** | Privé, puis public anonymisé |
| Vulnérabilité de sécurité | Signalement privé GitHub (« Report a vulnerability », voir `SECURITY.md`) ou message privé à Samuel | Privé |

## Ce que les formulaires demandent

- Version de Windows (`winver`), navigateur et version.
- Version de Rapido et **8 premiers caractères de l'empreinte** de
  l'installateur testé, pour savoir exactement quel fichier a été testé.
- Étapes pour reproduire, résultat attendu, résultat obtenu.
- Gravité : bloquant / gênant / mineur.
- Une case obligatoire qui confirme l'absence de liens privés, cookies,
  noms de fichiers personnels et données personnelles.

## Journaux : ce qu'on peut partager

- `%USERPROFILE%\.rapido\rapido.log` : à **relire avant envoi**. Il peut
  contenir des chemins de fichiers. En cas de doute, envoyez-le en privé.
- **Ne jamais joindre** `%USERPROFILE%\.rapido\downloads.json` : il contient
  les adresses des téléchargements.

## Suivi par Samuel (15 minutes, 2 fois par semaine)

1. Filtrer les issues `label:beta-privee is:open`.
2. Pour chaque issue : reproduire, ajouter `confirme` ou `besoin-info`, puis
   relier le commit correctif.
3. Retirer immédiatement d'une issue publique toute donnée personnelle
   publiée par erreur, avec « Edit » ou en masquant le commentaire.
4. À la fin de la bêta : faire un tableau récapitulatif dans
   `docs/private-beta/bilan-<date>.md` (bugs bloquants corrigés, ouverts,
   décisions).

## Critère de fin de bêta privée

- Au moins 2 testeurs ont terminé le guide sur Windows 10 **et** Windows 11
  (les deux au total).
- Aucun bug « bloquant » ouvert.
- Toutes les alertes antivirus signalées ont été analysées : faux positif
  confirmé ou corrigé.
