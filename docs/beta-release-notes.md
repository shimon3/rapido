# Rapido 1.3.0-beta.1 — notes de bêta (brouillon)

Brouillon préparé le 15 octobre 2026. Cette bêta n'est **pas publiée** : la
publication exige une identité Authenticode approuvée, la signature et la
vérification des exécutables et de l'installateur, la revue des licences, les
essais du candidat exact sur Windows 10/11 et l'autorisation explicite du
propriétaire. Un tag seul ne peut plus publier : le workflow conserve le garde
`publishable=false` jusqu'à une modification de signature relue.

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
- **Candidat actuellement non signé.** Il ne doit pas être distribué comme
  bêta publique et aucune consigne de contournement de SmartScreen ne doit être
  donnée. Les artefacts CI `UNPUBLISHED-*` servent uniquement de preuves de test.
- **Historique chiffré.** L'historique des téléchargements est chiffré avec
  DPAPI (lié au compte Windows). Les versions antérieures de Rapido ne savent
  pas le relire : revenir à une ancienne version repart d'un historique vide.
- **Capture vidéo : fichiers directs seulement.** Le bouton « Télécharger cette
  vidéo » et le clic droit « Télécharger la vidéo avec Rapido » envoient à
  Rapido les vidéos qui sont de simples fichiers (`.mp4`, `.webm`, `.mkv`,
  `.mov`…). Les flux (YouTube, m3u8/DASH), les sources `blob:` et les lecteurs
  intégrés affichent « Capture vidéo désactivée (bêta) » : ce chemin attend un
  canal sécurisé.
- **Firefox : « Enregistrer sous » non capturé.** Firefox télécharge le fichier
  pendant que sa boîte « Enregistrer sous » est ouverte et ne prévient
  l'extension qu'après validation : le fichier est déjà complet et reste dans
  Firefox, avec un message qui l'explique. Dans Firefox, utilisez le clic droit
  « Télécharger … avec Rapido » ou un clic direct sur le lien du fichier.
- **Boîte d'enregistrement du navigateur.** Dans Chrome et Edge, quand Rapido
  prend un « Enregistrer sous », la boîte du navigateur reste ouverte : il faut
  l'annuler.
- **Extension Firefox temporaire.** Non signée, elle se charge depuis
  `about:debugging` et disparaît à la fermeture de Firefox.
- **Essais réalisés.** Tests automatisés sur Windows Server 2025 (GitHub
  Actions), y compris installation, désinstallation, coexistence avec la
  version portable et Firefox réel. Essais manuels sur une VM Windows 10 22H2
  (le 15 octobre 2026) avec Edge 155, Chrome 155 et Firefox 158. Windows 11,
  la navigation privée, le redémarrage et la mise à jour restent à tester avant
  publication.
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
