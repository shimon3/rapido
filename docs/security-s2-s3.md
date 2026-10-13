# Rapido — sécurité API locale et extension Chrome (S2/S3)

Statut : conception avant implémentation. **Les failles ne sont pas corrigées par ce document.**

## État vérifié
- Le serveur FastAPI accepte des requêtes sur `127.0.0.1:9614`.
- `Host`, `Origin`, `Sec-Fetch-Site` et le type JSON sont contrôlés, mais ces en-têtes ne sont pas une authentification de processus local.
- L'extension Chrome collecte des cookies et les envoie via HTTP au port local ; le contrôle du propriétaire de l'instance n'est pas établi.
- Le système de fenêtres Rapido utilise son propre jeton de fenêtre ; ce jeton ne protège pas les autres endpoints.

## Contraintes de sécurité
1. **Pas de secret codé en dur dans l'extension**, ni de secret lisible via un GET HTTP sans authentification.
2. La vérification doit authentifier l'instance de Rapido **avant** toute transmission de cookies.
3. Un autre programme local ou une autre session Windows ne doit pas pouvoir déclencher une écriture privilégiée.
4. Conserver les contrôles web existants en défense en profondeur.
5. Ne pas casser le téléchargement Chrome normal si Rapido est absent, non appairé ou ne répond pas.
6. Ne pas enregistrer dans les logs les cookies, tokens ou en-têtes d'authentification.
7. Protéger les données téléchargées, l'historique et les téléchargements actifs.

## Proposition de conception
- **Canal privilégié** : étudier et prototyper Chrome Native Messaging pour l'extension, avec hôte natif enregistré uniquement pour l'identifiant fixe de l'extension.
- Faire établir par l'hôte natif un canal authentifié vers l'instance Rapido appartenant au même utilisateur ; préférer un IPC local protégé par ACL du compte Windows.
- Pour les pages WebView intégrées : distinguer l'identité WebView de la page de navigateur ; ne pas faire reposer la confiance sur `Origin` seul. Étudier un canal JS natif contrôlé ou un jeton de session intransmissible aux sites étrangers, sans endpoint public servant le jeton.
- Limiter les capacités des canaux : les informations de cookies ne transitent que lors d'une capture explicite depuis l'extension ; les opérations mutantes ordinaires requièrent une autorisation.
- Garder la possibilité d'une installation portable et d'un arrêt/reprise sans perte d'historique.

## Vérifications nécessaires avant codage
- Inspecter précisément le démarrage serveur/WebView, l'installation de l'extension et les droits du programme Inno Setup.
- Définir la procédure d'appairage et de révocation, et les ACL Windows des IPC ou fichiers éventuels.
- Évaluer le comportement lorsque le port 9614 est déjà occupé par un processus tiers.
- Définir la migration de l'extension installée actuellement (sans échec silencieux ni envoi de cookies au mauvais destinataire).

## Tests d'acceptation bloquants
- [ ] Client HTTP local sans authentification : POST/PUT/DELETE refusés, pas seulement CORS.
- [ ] Appel depuis autre compte Windows : rejeté, même sur loopback.
- [ ] Processus imposteur écoutant sur 9614 : aucun cookie n'est envoyé.
- [ ] Extension appairée : capture fichier et vidéo fonctionnelle.
- [ ] Rapido fermé / non appairé : Chrome conserve ou reprend le téléchargement.
- [ ] Fenêtres de capture/progression et menu Aide fonctionnent.
- [ ] Pause, reprise, arrêt brutal, installer et portable fonctionnent.
- [ ] Aucune donnée sensible dans les logs, erreurs et fichiers non protégés.
- [ ] Tests Windows + Chrome réels et suite GitHub Actions verts.

Ne pas fusionner en promettant « S2/S3 corrigés » avant d'avoir implémenté et validé ces points.
