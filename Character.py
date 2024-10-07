#-*-coding:utf-8-*-

from os.path import join, exists
from os import listdir
from json import dump, load
from typing import Any

# Create constants of the module
BASE_STATS = {
    "Force": 50,
    "Dexterité": 50,
    "Constitution": 50,
    "Sagesse": 50,
    "Agilité": 50,
    "Charisme": 50,
    "Intelligence": 50,
    "Perception": 50,
    "Chance": 50,
    "Survie": 50
}

# Create objects of the module
class Character:
    """
    Base instance of character object
    """
    def __init__(self, name: str) -> None:
        self.name = name
        self.stats = BASE_STATS
        self.hp = self.get_max_hp()
        self.stamina = 100
        if exists(join("Characters", self.name)):
            self.load()

    def __getattribute__(self, name: str) -> Any:
        if name in object.__getattribute__(self, "stats"):
            return object.__getattribute__(self, "stats")[name]
        else:
            return object.__getattribute__(self, name)

    def get_max_hp(self) -> int:
        return 10 + int(self.stats["Constitution"]/10) + int(self.stats["Sagesse"]/10)
    
    def load(self) -> None:
        with open(join("Characters", self.name), "r", encoding="utf-8") as file:
            dict = load(file)
            self.name = dict["name"]
            self.stats = dict["stats"]
            self.hp = dict["hp"]
            self.stamina = dict["stamina"]
            file.close()

    def save(self) -> None:
        with open(join("Characters", self.name), "w", encoding="utf-8") as file:
            dump(
                {
                    "name": self.name,
                    "stats": self.stats,
                    "hp": self.hp,
                    "stamina": self.stamina
                },
                file
            )
            file.close()

# Create Functions of the module
def load_characters() -> dict:
    characters = {}
    for name in listdir("Characters"):
        characters[name] = Character(name)
    return characters
