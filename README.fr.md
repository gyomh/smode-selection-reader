# Lire l'élément sélectionné dans Smode Compose (depuis un Script)

*[English version](README.md)*

Un petit outil qui permet à un **Script Smode Compose** de savoir quel élément est actuellement sélectionné dans
l'interface, pour que votre script agisse sur « ce qui est sélectionné » au lieu de demander à l'utilisateur de le
glisser-déposer dans un paramètre.

**Important : Smode Tech n'a pas publié de documentation officielle de l'API, et ceci n'est pas un outil
officiellement supporté.** L'API Oil n'expose pas la sélection de l'interface aux scripts (rien n'apparaît en
parcourant `engine`, `project` et `script`). Cet outil contourne le problème en lisant le nom affiché dans le
panneau Paramètres via Windows UI Automation. Il est expérimental et construit par essais et erreurs.

## Fonctionnement

Deux éléments :

1. **`read_selection.ps1`** — un petit script PowerShell (lecture seule, il ne clique ni ne saisit jamais rien).
   Smode est une application JUCE et expose une partie de son interface à Windows UI Automation. Le script
   retrouve le titre du panneau Paramètres (le nom de l'élément affiché) et l'écrit sur une ligne de JSON.

2. **`smode_read_selection.py`** — deux fonctions Python à coller dans votre propre script Smode :
   - `readSelection()` lance le script PowerShell dans un fil séparé (avec un délai maximum) et renvoie le résultat ;
   - `findLayersByName(root, name)` retrouve le ou les layers portant ce nom dans l'arbre du projet.

```
votre script Smode --readSelection()--> powershell read_selection.ps1 --UI Automation--> titre du panneau Paramètres
        |
        +--findLayersByName(script.rootElement, nom)--> l'objet layer, prêt à l'emploi
```

## Installation

1. Copiez `read_selection.ps1` dans `<votre dossier Documents>\Smode Files\Tools\read_selection.ps1`
   (créez le dossier `Tools` si nécessaire). Chaque utilisateur de votre script doit faire de même.
2. Collez le contenu de `smode_read_selection.py` en haut de votre script Smode (après vos déclarations de
   paramètres Oil et avant d'utiliser la sélection).

Le chemin est calculé à partir du vrai dossier Documents indiqué par Windows : un dossier Documents redirigé
(OneDrive, par exemple) ne pose donc pas de problème.

## Utilisation dans un script

```python
selection = readSelection()
if not selection["ok"]:
    print(selection["error"], selection["message"])     # dites à l'utilisateur quoi corriger
else:
    matches = findLayersByName(script.rootElement, selection["name"])
    if len(matches) == 1:
        layer = matches[0]
        # vérifiez son type vous-même, p. ex. layer.generator.getOilClassName() == 'VideoFileTextureGenerator'
```

La plupart des utilisateurs n'ont pas de console visible pour les Scripts Smode : écrire le message dans un
paramètre texte (`Status: Oil.String("")` puis `script.Status = message`) est un moyen pratique de l'afficher.

## Ce que vous obtenez

Succès : `{"ok": True, "name": "<nom de l'élément>"}`. L'outil renvoie **uniquement le nom** : il ne filtre pas par
type, c'est à votre script de le faire (le type affiché dans le panneau dépend de la sous-page affichée, il n'est
donc pas fiable de le lire dans l'interface ; retrouvez le layer par son nom et lisez son type côté Oil).

Échec : `{"ok": False, "error": <code>, "message": <texte>}` avec l'un de ces codes :

| Code | Signification |
|---|---|
| `reader_missing` | `read_selection.ps1` introuvable au chemin attendu |
| `timeout` | la lecture a dépassé le délai (25 s par défaut) |
| `read_failed` | erreur inattendue ou réponse illisible |
| `smode_not_found` | Smode n'est pas ouvert |
| `ui_not_readable` | moins de 100 éléments d'interface visibles (fenêtre réduite ou masquée) |
| `no_panel` | aucun panneau Paramètres visible |
| `multiple_panels` | plusieurs panneaux affichent des éléments différents (les noms sont listés dans le message) |

## Règles et limites

- **Gardez un seul panneau Paramètres visible et non verrouillé.** Un panneau verrouillé continue d'afficher un
  élément qui n'est pas la sélection, et l'état du verrou n'est pas lisible de façon fiable. Si plusieurs panneaux
  sont ouverts, l'outil ne les accepte que s'ils affichent tous le même nom.
- **Lancement de votre script :** le bouton Execute de la ligne du script dans l'arbre *Elements* ne change pas la
  sélection. Le bouton Execute du panneau Paramètres du script, lui, la change (il faut sélectionner le script
  pour l'afficher), et vous liriez alors le nom du script lui-même.
- **Nom, pas chemin.** Deux layers de même nom ne peuvent pas être distingués : gérez ce cas dans votre script.
- **Vitesse :** quelques secondes par appel (environ 3 à 4 s ici), car tout l'arbre de l'interface est parcouru.
- **Windows uniquement**, avec PowerShell 5.1 ou plus récent. Le script doit être lancé avec `stdin=DEVNULL`
  depuis Smode (déjà fait dans `readSelection()`), sinon `subprocess` échoue avec
  `OSError(9, 'The handle is invalid')`.
- **Testé :** Smode Compose 15.5 sous Windows 11, interface en anglais, une seule machine, Smode sur l'écran
  principal. Les autres langues d'interface, les autres échelles d'affichage et Smode sur un écran secondaire ne
  sont pas vérifiés.
- Le titre du Viewport (qui affiche aussi un nom d'élément) est volontairement ignoré ; la détection s'appuie sur
  la forme du titre du panneau, donc une évolution future de l'interface de Smode pourrait la casser.

## Licence

MIT — voir [LICENSE](LICENSE).
