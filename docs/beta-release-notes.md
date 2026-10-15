# Rapido 1.3.0-beta.1 — notes de bêta (brouillon)

Brouillon préparé le 15 octobre 2026. Cette bêta n'est **pas publiée** : la
publication demande un tag `v1.3.0-beta.1` poussé explicitement par le
propriétaire, après relecture des PR et essais sur Windows 10/11.

## Ce qu'est cette bêta

- Version de test destinée à trouver les problèmes d'installation, de capture
  dans les navigateurs, de reprise et de mise à jour avant une version finale.
- Elle sera publiée comme **préversion** GitHub : les installations de versions
  finales ne se la verront pas proposer automatiquement. Les utilisateurs de la
  bêta se verront proposer la 1.3.0 finale quand elle sortira.
- Installation pour l'utilisateur courant, sans droits administrateur, ou
  version portable.

## Limites connues, à lire avant d'installer

- **Pas de protection contre un compte Windows déjà compromis (#26).** Un
  programme malveillant qui tourne déjà sous ton compte peut remplacer les
  fichiers de Rapido ou son enregistrement dans le navigateur. Rapido vérifie
  l'identité des processus, l'origine exacte de l'extension et refuse les
  liens symboliques, mais ces contrôles ne remplacent pas une signature de
  code imposée par le système. Décision du propriétaire du 15 octobre 2026 :
  la bêta part sans cette protection ; #26 reste ouvert.
- **Programme non signé.** Windows SmartScreen peut afficher « Windows a
  protégé votre ordinateur ». Cliquer sur « Informations complémentaires »
  puis « Exécuter quand même », uniquement pour un fichier téléchargé depuis
  la page officielle des releases du projet.
- **Historique chiffré.** L'historique des téléchargements est chiffré avec
  DPAPI (lié au compte Windows). Les versions antérieures de Rapido ne savent
  pas le relire : revenir à une ancienne version repart d'un historique vide.
- **Essais réalisés.** Tests automatisés sur Windows Server 2025 (GitHub
  Actions), y compris installation, désinstallation, coexistence avec la
  version portable et Firefox réel. Les essais sur Windows 10/11 réels et avec
  Chrome/Edge installés par l'utilisateur restent à faire avant publication.
- **Extensions de développement.** Les extensions Chrome, Edge et Firefox
  fournies sont des versions de développement à charger manuellement ; elles
  ne viennent pas des boutiques officielles.

## Licences

Le dossier `third-party` à côté de `Rapido.exe` contient les licences, notices
et emplacements des sources des composants tiers (Python, bibliothèques
Python, bibliothèques natives, crates Rust de pydantic_core, SDK WebView2).
Rapido est publié sous licence MIT, © 2026 Samuel Bentouza.

## Signaler un problème

https://github.com/shimon3/rapido/issues — indiquer la version de Windows, le
navigateur, la version de Rapido (1.3.0-beta.1) et les étapes pour reproduire.
Ne jamais joindre de cookies, d'URL signées ni de fichier `downloads.json`.
