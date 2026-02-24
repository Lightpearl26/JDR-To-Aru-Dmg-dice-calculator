# JDR To Aru Dmg dice calculator

 programme d'assistance à mon jdr to aru

## Widget fiche personnage (pygame)

Un widget prêt à l'emploi est disponible dans `character_sheet_widget.py` : `CharacterSheetWidget`.

Exemple d'intégration rapide :

```python
from pygame import Rect
from pygame_ui import UIApp
from character_sheet_widget import CharacterSheetWidget
from libs.character import Character

app = UIApp((1280, 720))
layer = app.add_layer()
character = Character.from_name("Alistair")

sheet = CharacterSheetWidget(None, Rect(20, 20, 700, 520), character)
layer.add(sheet)
```

Fonctionnalités incluses :

- onglets `Stats`, `Modifs`, `Jets`, `Inventaire`, `Sorts`
- panneau résumé (niveau, HP, stamina, santé mentale/drug)
- scroll molette dans le contenu de la fiche
- méthode `set_character(...)` pour changer de personnage dynamiquement
