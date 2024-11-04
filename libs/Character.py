#-*- coding: utf-8 -*-

# Create metainfos
__version__ = "1.0"
__author__ = "Franck Lafiteau"

# Import external modules
from json import dumps, loads
from os.path import join, dirname
from os import makedirs

# Create globals
FILE_PATH = join("Data", "characters.data")
VALID_ARGS = ["name", "HP", "FOR", "DEX", "CON", "WIS", "INT", "CHA", "PER", "AGI", "LUC", "SUR", "stamina", "mental_health", "drug_health"]
DEFAULT_VALUES = {
    "name": None,
    "HP": 20,
    "FOR": 50,
    "DEX": 50,
    "CON": 50,
    "WIS": 50,
    "INT": 50,
    "INT": 50,
    "CHA": 50,
    "PER": 50,
    "AGI": 50,
    "LUC": 50,
    "SUR": 50,
    "stamina": 100,
    "mental_health": 100,
    "drug_health": 100
}

# Quick setuping directories
makedirs(dirname(FILE_PATH), exist_ok=True)
open(FILE_PATH, "a").close()

# Create function of the module
def new_character(**kwargs) -> dict:
    """
    Create a new character
    """
    character = {name: kwargs.get(name, DEFAULT_VALUES.get(name)) for name in VALID_ARGS}
    save_character(character)
    return character

def load_characters() -> list[dict]:
    """
    load all characters from file and return a list of them
    """
    characters = []
    with open(FILE_PATH, "r") as file:
        for line in file:
            characters.append(loads(line))
        file.close()
    return characters

def save_characters(characters: list[dict]) -> None:
    """
    Save a list of characters in the file
    """
    with open(FILE_PATH, "w") as file:
        file.write("\n".join([dumps(character) for character in characters]))
        file.close()

def load_character(name: str) -> dict | None:
    """
    Load a specific character from the file and return it
    """
    with open(FILE_PATH, "r") as file:
        for line in file:
            character = loads(line)
            if character["name"] == name:
                return character
        file.close()
    return None

def save_character(character: dict) -> None:
    """
    overwrite the file with the character
    """
    characters = load_characters()
    found = False
    for i, c in enumerate(characters):
        if c["name"] == character["name"]:
            characters[i] = character
            found = True
    if not found:
        characters.append(character)
    save_characters(characters)

def update_character(name: str, **kwargs) -> None:
    character = load_character(name)
    if character:
        save_character({label: kwargs.get(label, character.get(label)) for label in VALID_ARGS})
