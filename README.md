# JDR To Aru DMG Dice Calculator

Outil desktop pygame pour assister les parties JDR avec gestion de personnages, ressources et résolutions d'actions.

## Aperçu rapide

- Interface par onglets: `Session`, `Combat`, `Ressources`
- Gestion des ressources JSON: personnages, objets, sorts
- Résolution assistée: `Strike`, `Shoot`, `Cast Spell`
- Sauvegarde des personnages + génération de fiche PNG
- Logs automatiques dans `cache/logs`

## Captures

> Captures d'écran à ajouter (UI principale, panneau Session, panneau Ressources, popup Cast Spell).

## Installation

Prérequis:
- Python 3.10+
- `pygame`

```bash
python -m venv .venv
```

Windows (PowerShell):
```powershell
.\.venv\Scripts\Activate.ps1
pip install pygame
```

Linux / macOS:
```bash
source .venv/bin/activate
pip install pygame
```

## Lancement

```bash
python app.py
```

## Fonctionnalités

### Session
- Affichage du groupe actif
- Liste complète des personnages chargés
- Recherche, ajout/retrait au groupe
- Cartes personnage avec actions rapides

### Résolution d'actions
- `Strike`: attaquant/cible + dés d100 optionnels
- `Shoot`: tireur/cible + dés d100 optionnels
- `Cast Spell`: lanceur/sort/cible + dés custom par stat

### Ressources
- Sous-onglets `Characters`, `Items`, `Spells`
- CRUD JSON via l'UI (`Create`, `Load`, `Modify`, `Remove`)
- Prévisualisation des ressources

### Fiche personnage
- Widget `CharacterSheetWidget` dans `libs/gui/character_sheet_widget.py`
- Onglets `Stats`, `Modifs`, `Inventaire`, `Sorts`
- Popup de d100 animé pour les checks
- Sauvegarde depuis la fiche

## Roadmap

- [ ] Finaliser le contenu du panneau `Combat`
- [ ] Ajouter des captures d'écran dans ce README
- [ ] Ajouter un fichier de dépendances (`requirements.txt`)
- [ ] Ajouter des tests automatiques sur les mécaniques cœur (dés, formules, chargement JSON)

## Documentation technique

### Arborescence utile
- `app.py`: point d'entrée
- `libs/`: logique métier + managers + widgets/panels
- `assets/characters`: personnages JSON
- `assets/items`: objets JSON
- `assets/spells`: sorts JSON
- `assets/sheets`: fiches PNG générées
- `cache/logs`: fichiers logs

### Formats JSON (résumé)

Character:
```json
{
  "name": "Alistair",
  "stats": {
    "str": 105,
    "dex": 55,
    "con": 110,
    "int": 30,
    "wis": 100,
    "cha": 20,
    "per": 20,
    "agi": 60,
    "luc": 30,
    "sur": 50,
    "stamina": 100,
    "mental_health": 100,
    "drug_health": 100
  },
  "modifiers": {
    "hp": 0,
    "str": 0,
    "dex": 0,
    "con": 0,
    "int": 0,
    "wis": 0,
    "cha": 0,
    "per": 0,
    "agi": 0,
    "luc": 0,
    "sur": 0,
    "stamina": 0,
    "mental_health": 0,
    "drug_health": 0
  },
  "spells": ["Shock sphere"],
  "inventory": [["Matraque", 1]]
}
```

Item:
```json
{
  "name": "Matraque",
  "description": "...",
  "modifier": [["str", 15]]
}
```

Spell:
```json
{
  "name": "Railgun",
  "description": "...",
  "cost": 20,
  "effects": [
    {
      "target": "target",
      "target_stat": "hp",
      "effect": "malus",
      "formula": "5 + diceratio(user.int, 20) - diceratio(target.wis, 10)"
    }
  ]
}
```

### Formules de sort

Support:
- opérations `+ - * /`
- parenthèses
- accès `user.<stat>` / `target.<stat>`
- fonctions `diceratio(...)` et `diceattack(...)`

L'évaluation est sécurisée (pas d'exécution dynamique arbitraire).

## Changelog

### 2026-02-24
- Sécurisation de l'évaluation des formules de sorts
- Suppression du préchargement global des sorts à l'import
- Ajout d'un cache d'items dans l'inventaire
- Harmonisation logger + exceptions ciblées dans les panels UI
- Nettoyage des warnings statiques dans `app.py`
