# Rapido 1.3.0-beta.1 — limites de sécurité d'une version non signée

À lire **avant** d'installer. Cette version est une bêta privée, remise
personnellement à 2 à 5 testeurs. Ce n'est pas une version publique.

## Ce que « non signée » veut dire

Windows vérifie les programmes avec une signature numérique (Authenticode),
qui indique qui a publié le fichier. Cette bêta **n'a pas de signature**.
Conséquences :

1. **Windows ne peut pas vous dire qui a créé le fichier.** SmartScreen
   affiche « Windows a protégé votre ordinateur » et « Éditeur inconnu ».
   C'est normal pour cette bêta, mais c'est aussi ce que vous verriez avec un
   faux fichier.
2. **Seule l'empreinte SHA-256 prouve que vous avez le bon fichier.**
   Samuel vous envoie les empreintes par un **autre canal** que le fichier
   lui-même. Si une empreinte ne correspond pas, n'ouvrez pas le fichier et
   prévenez-le.
3. **Votre antivirus peut signaler le fichier.** Les programmes Python
   empaquetés et non signés déclenchent parfois des alertes. Ne désactivez pas
   votre antivirus. Signalez l'alerte (nom du produit, nom de la détection).

## Ce que Rapido ne protège pas (même plus tard, signé)

- **Un programme malveillant déjà présent sous votre compte Windows** peut
  remplacer les fichiers de Rapido dans `%LOCALAPPDATA%\Programs\Rapido`,
  modifier ses enregistrements de navigateur (HKCU) ou s'injecter dans ses
  processus. Rapido ne peut pas l'en empêcher dans une installation sans
  droits administrateur (issue #26, toujours ouverte).
- **Une signature, même future, ne change pas ce point.** Elle prouve qui a
  publié le fichier, pas que la copie installée ne peut pas être remplacée.
- La version **portable** (ZIP) a les mêmes limites, et ses fichiers sont
  encore plus faciles à modifier.

## Ce qui est en place

- Les communications entre le navigateur et Rapido sont limitées à votre
  session Windows, vérifiées par identité de processus, et refusent les
  accès non authentifiés.
- Pas de mise à jour automatique : Rapido peut signaler une nouvelle version,
  mais ne télécharge et ne lance jamais rien tout seul.
- L'installateur n'utilise pas de droits administrateur et ne ferme que ses
  propres processus.
- Chaque version testée est construite par GitHub Actions à partir d'un
  commit public identifié. Le dossier `third-party` contient les licences
  des composants.

## Précautions recommandées

1. Si possible, testez sur une **machine virtuelle ou un PC de test**, ou au
   moins sur un compte Windows sans données sensibles.
2. Vérifiez l'empreinte SHA-256 **avant** de lancer l'installateur
   (voir le guide du testeur).
3. Ne téléchargez pas de contenu confidentiel ou privé avec la bêta.
4. Désinstallez la bêta à la fin du test, ou quand Samuel vous le demande.
5. Ne redistribuez pas les fichiers : chaque testeur reçoit sa copie de
   Samuel.

En installant cette bêta, vous confirmez avoir lu ces limites.
