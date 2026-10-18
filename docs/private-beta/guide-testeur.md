# Guide du testeur — Rapido 1.3.0-beta.1 (bêta privée)

Durée : environ 30 minutes pour l'installation et les tests de base.
Configuration : Windows 10 (22H2) ou Windows 11, avec Chrome, Edge ou Firefox.

Lisez d'abord la notice de sécurité :
`notice-securite-version-non-signee.md`.

## 1. Vérifier le fichier (2 minutes, obligatoire)

Samuel vous envoie :

- le fichier `Rapido-Setup-1.3.0-beta.1.exe` ;
- **par un autre moyen** (SMS, appel, autre messagerie), son empreinte SHA-256.

Dans le menu Démarrer, ouvrez **PowerShell**, puis tapez (adaptez le chemin) :

```powershell
Get-FileHash "$env:USERPROFILE\Downloads\Rapido-Setup-1.3.0-beta.1.exe" -Algorithm SHA256
```

Comparez la ligne `Hash` avec l'empreinte reçue, caractère par caractère, ou
au moins les 8 premiers et les 8 derniers.

- **Identique** : passez à l'étape 2.
- **Différente** : n'ouvrez pas le fichier, supprimez-le et prévenez Samuel.

## 2. Installer

1. Double-cliquez sur l'installateur.
2. Windows affiche « Windows a protégé votre ordinateur — Éditeur inconnu ».
   C'est attendu pour cette bêta non signée. **Seulement si l'empreinte de
   l'étape 1 correspond**, cliquez sur « Informations complémentaires », puis
   sur le bouton qui lance l'application.
3. Suivez l'installateur. Aucun mot de passe administrateur n'est demandé.
   Si Windows en demande un, arrêtez et prévenez Samuel.
4. Rapido s'installe dans `%LOCALAPPDATA%\Programs\Rapido`.

## 3. Tester (cochez ce qui marche)

- [ ] Rapido s'ouvre et l'icône apparaît près de l'horloge.
- [ ] Téléchargement simple : collez un lien de fichier public (par exemple
      une image ou un PDF public) et téléchargez-le.
- [ ] Trois téléchargements en même temps.
- [ ] Coupez le Wi-Fi pendant un téléchargement, puis rallumez-le et reprenez.
- [ ] Extension de navigateur : Rapido > Options > Outils, installez
      l'extension pour votre navigateur, puis lancez un téléchargement depuis
      le navigateur.
- [ ] Fermez Rapido depuis l'icône près de l'horloge, puis relancez-le.
- [ ] Langue : changez entre français, anglais et hébreu (si l'option existe).

Notez tout ce qui vous surprend, même un détail.

## 4. Envoyer vos retours

Voir `retours-et-bugs.md`. En résumé :

- **Bug ou avis** : formulaire « Bêta privée — bug » sur GitHub, ou message
  à Samuel si vous n'avez pas de compte GitHub.
- **Problème de sécurité** : jamais en public, uniquement en message privé
  à Samuel.
- Les issues GitHub de Rapido sont **publiques** : n'y mettez ni vos liens de
  téléchargement privés, ni vos noms de fichiers personnels, ni de captures
  qui montrent des données personnelles.

## 5. Désinstaller à la fin du test

1. Paramètres Windows > Applications > Rapido > Désinstaller.
2. Vos fichiers téléchargés restent dans leur dossier.
3. Pour tout effacer, supprimez aussi le dossier `%USERPROFILE%\.rapido`
   (réglages, historique et journal de Rapido).
