# -*- coding: utf-8 -*-

"""
Config file of the package
"""

# import needed external libs
from os.path import join

# Logger constants
LOG_FOLDER: str = join("cache", "logs")
LOG_DEBUG: bool = True

# Stats constants
BASE_STATS: int = 50

# Path constants
ASSETS_FOLDER: str = join("assets")
CHARACTERS_FOLDER: str = join(ASSETS_FOLDER, "characters")
SPELLS_FOLDER: str = join(ASSETS_FOLDER, "spells")
ITEMS_FOLDER: str = join(ASSETS_FOLDER, "items")
SHEETS_FOLDER: str = join(ASSETS_FOLDER, "sheets")
