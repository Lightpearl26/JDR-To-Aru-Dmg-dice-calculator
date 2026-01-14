# -*- coding: utf-8 -*-

"""
JDR main setup
"""

from libs.character import Character


# ----- Create main group ----- #
GROUP = [
    alistair := Character.from_name("Alistair"),
    heilari := Character.from_name("Heilari"),
    hella := Character.from_name("Hella"),
    saru := Character.from_name("Saru"),
    dexter := Character.from_name("Dexter")
]

# ----- Create basic enemies ----- #
ENEMIES = [
    dummy := Character.from_name("Dummy"),
    robot := Character.from_name("Robot"),
    mage := Character.from_name("Mage"),
    skillout_sbire := Character.from_name("Skillout Sbire"),
    skillout_captain := Character.from_name("Skillout Captain")
]

# ----- Create allies ----- #
ALLIES = [
    lena := Character.from_name("Lena"),
    julie := Character.from_name("Julie"),
    lee_sin := Character.from_name("LeeSin"),
    maximillien := Character.from_name("Maximillien"),
    red_robin := Character.from_name("RedRobin"),
    benoit := Character.from_name("Benoit"),
    bernard := Character.from_name("Bernard"),
    charles := Character.from_name("Charles"),
]

# ----- Create bosses ----- #
BOSSES = [
    harold := Character.from_name("Harold"),
    jean_pierre := Character.from_name("JeanPierre"),
]

def update_all_characters():
    """ Update all characters' stats """
    for char in GROUP + ENEMIES + ALLIES + BOSSES:
        char.create_sheet()
