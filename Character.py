#-*- coding: utf-8 -*-

# Create metainfos
__version__ = "1.0"
__author__ = "Franck Lafiteau"

# Import external modules
from pygame import Surface, Rect, SRCALPHA
from pygame.image import save
from pygame.font import SysFont, init
from json import dumps, loads
from os.path import join, dirname
from os import makedirs

# Create globals
FILE_PATH = join("G:", "Mon Drive", "JDR", "To ARU s2", "CharacterSheets")
STATS = ["HP", "STR", "DEX", "CON", "WIS", "INT", "CHA", "PER", "AGI", "LUC", "SUR", "stamina", "mental_health", "drug_health"]


# Create Objects of the module
class Character[C]:
    """
    Instance of a Character
    """
    name="Default"
    HP = 20
    STR = 50
    DEX = 50
    CON = 50
    WIS = 50
    INT = 50
    CHA = 50
    PER = 50
    AGI = 50
    LUC = 50
    SUR = 50
    stamina = 100
    mental_health = 100
    drug_health = 100

    # System
    def __init__(self: C, **kwargs: dict[str, int | str]) -> None:
        """
        initialize a new Character replacing default values by args passed in kwargs
        """
        for name, value in kwargs.items():
            if name in STATS:
                self.__setattr__(name, value)
            if name == "name":
                self.name = value
            self.modifiers = {name: 0 for name in STATS}

    def get_dict(self: C) -> dict:
        """
        Return the dict corresponding to the Character
        """
        return {"name": self.name, "base": {stat: self.__getattribute__(stat) for stat in STATS}, "modifiers": self.modifiers}

    # Handle modifiers
    def add_modifier(self: C, stat: str, value: int) -> None:
        if stat in STATS:
            self.modifiers[stat] += value

    def reset_modifiers(self: C) -> None:
        for name in STATS:
            self.modifiers[name] = 0

    def set_modifier(self: C, stat: str, value: int) -> None:
        if stat in STATS:
            self.modifiers[stat] = value

    # Handle stats
    def get(self: C, stat: str) -> int | None:
        if stat in STATS:
            return self.__getattribute__(stat) + self.modifiers[stat]

    def get_max_health(self: C) -> int:
        """
        Return the max health stat of the Character
        """
        return 10 + self.CON // 10 + self.WIS // 10

    def update(self: C, **kwargs: dict[str, int | str]) -> None:
        for name, value in kwargs.items():
            if name in STATS:
                self.__setattr__(name, value)

    # GUI
    def get_image(self: C, filename: str) -> str:
        init()
        surf = Surface((600, 400))
        surf.fill((0, 0, 10))
        title_font = SysFont("Arial", 30)
        text_font = SysFont("Arial", 15)
        name = title_font.render(self.name, True, (255, 255, 255))
        surf.blit(name, name.get_rect(midleft=(30, 30)))
        surf.fill((255, 255, 255), Rect(200, 10, 200, 10))
        surf.fill((155, 255, 55), Rect(200, 10, int(200*self.get("HP")/self.HP), 10))
        hp = text_font.render(str(self.get("HP")), True, (255, 255, 255))
        surf.blit(hp, hp.get_rect(midright=(448, 15)))
        label_hp = text_font.render("HP", True, (255, 255, 255))
        surf.blit(label_hp, label_hp.get_rect(midleft=(452, 15)))
        surf.fill((200, 200, 200), Rect(200, 40, 200, 10))
        surf.fill((255, 155, 55), Rect(200, 40, 2*self.get("stamina"), 10))
        stamina = text_font.render(str(self.get("stamina")), True, (255, 255, 255))
        surf.blit(stamina, stamina.get_rect(midright=(448, 45)))
        label_stamina = text_font.render("Stamina", True, (255, 255, 255))
        surf.blit(label_stamina, label_stamina.get_rect(midleft=(452, 45)))
        surf.fill((255, 255, 255), Rect(0, 60, 600, 1))
        surf.fill((255, 255, 255), Rect(400, 60, 1, 340))
        surf.fill((255, 255, 255), Rect(466, 60, 1, 340))
        surf.fill((255, 255, 255), Rect(533, 60, 1, 340))
        text = text_font.render("BASE", True, (255, 255, 255))
        surf.blit(text, text.get_rect(center=(433, 75)))
        text = text_font.render("MODIFIER", True, (255, 255, 255))
        surf.blit(text, text.get_rect(center=(500, 75)))
        text = text_font.render("TOTAL", True, (255, 255, 255))
        surf.blit(text, text.get_rect(center=(566, 75)))
        for i, stat in enumerate(["STR", "DEX", "CON", "WIS", "INT", "AGI", "PER", "CHA", "LUC", "SUR"]):
            text = text_font.render(stat, True, (255, 255, 255))
            surf.blit(text, text.get_rect(midleft=(10, 105+30*i)))
            value = self.__getattribute__(stat)
            color = (255, 0, 0) if value < 50 else (255, 255, 0) if value < 70 else (0, 255, 0) if value < 100 else ((0, 255, 255))
            surf.fill(color, Rect(50, 100+30*i, 2*value, 10))
            text = text_font.render(str(value), True, (255, 255, 255))
            surf.blit(text, text.get_rect(center=(433, 105+30*i)))
            modifier = self.modifiers[stat]
            bar = Surface((2*abs(modifier), 10), SRCALPHA)
            if modifier < 0:
                surf.fill((255, 0, 255), (50+2*(value+modifier), 102+30*i, 2*abs(modifier), 6))
            else:
                surf.fill((255, 0, 255), (50+2*value, 102+30*i, 2*modifier, 6))
            text = text_font.render(str(modifier), True, (255, 255, 255))
            surf.blit(text, text.get_rect(center=(500, 105+30*i)))
            text = text_font.render(str(self.get(stat)), True, (255, 255, 255))
            surf.blit(text, text.get_rect(center=(566, 105+30*i)))
        save(surf, filename)
        return filename

    # Actions available
    def dice_check(self: C, stat: str, dice_result: int) -> bool:
        return dice_result - self.get(stat) <= 0

    def strike(self: C, enemy: C, dice: int, enemy_dice: int) -> str:
        modifier = abs(int(dice < 5) - int(dice > 94) - int(enemy_dice < 5) + int(enemy_dice > 94))
        value = dice - enemy_dice + enemy.get("CON") - self.get("STR")
        if value < 0:
            return f"C:{abs(value)//20}d{4+2*modifier}"
        else:
            return f"E:{abs(value)//20}d{4+2*modifier}"

    def shoot(self: C, enemy: C, dice: int, enemy_dice: int) -> str:
        modifier = abs(int(dice < 5) - int(dice > 94) - int(enemy_dice < 5) + int(enemy_dice > 94))
        value = dice - enemy_dice + enemy.get("AGI") - self.get("DEX")
        if value <= 0:
            return f"{max(1, abs(value)//20)}d{4+2*modifier}"
        else:
            return "Failure"


class CharacterList[CL]:
    """
    Instance of a Character list
    """

    def __init__(self: CL, filename: str=FILE_PATH) -> None:
        makedirs(dirname(filename), exist_ok=True)
        open(filename, "a").close()
        self.filename = filename
        self.characters = {}
        self.load()

    # Handle Characters
    def append(self: CL, character: Character) -> None:
        """
        Append a new Character to the list
        Notice that it will overwrite an existing character with same name
        """
        self.characters[character.name] = character

    def update(self: CL, name: str, **kwargs: dict[str, int]) -> None:
        if name in self.characters.keys():
            self.characters[name].update(**kwargs)
        else:
            raise KeyError(f"The specified character {name} doesn't exist")

    def update_modifier(self: CL, name: str, **kwargs: dict[str, int]) -> None:
        if name in self.characters.keys():
            for stat, value in kwargs.items():
                self.get(name).set_modifier(stat, value)
        else:
            raise KeyError(f"The specified character {name} doesn't exist")

    def new(self: CL, **kwargs: dict[str, int | str]) -> None:
        self.append(Character(**kwargs))

    def get(self: CL, name: str) -> Character | None:
        if name in self.characters.keys():
            return self.characters[name]

    # Save methods
    def load(self: CL) -> None:
        with open(self.filename, "r") as file:
            for line in file:
                infos = loads(line)
                c = Character(name=infos["name"], **infos["base"])
                c.modifiers = infos["modifiers"]
                self.append(c)
            file.close()

    def save(self: CL) -> None:
        with open(self.filename, "w") as file:
            file.write("\n".join([dumps(c.get_dict()) for c in self.characters.values()]))
            file.close()

    # GUI
    def update_images(self: CL, dirname: str) -> None:
        for name in self.characters.keys():
            filename = join(dirname, f"{name}.png")
            self.get(name).get_image(filename)
