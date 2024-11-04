#-*- coding: utf-8 -*-

# Create metainfos
__version__ = "1.0"
__author__ = "Franck Lafiteau"

# Import internal modules
from libs import Character as C

# Create functions of the module
def stat_check(character, stat, dice_result):
    crit = dice_result < 5 or dice_result > 94
    result = dice_result - character[stat]
    return (result <= 0), crit, abs(result)

def stat_fight(character1, stat1, dice_result1, character2, stat2, dice_result2):
    success1, crit1, diff1 = stat_check(character1, stat1, dice_result1)
    success2, crit2, diff2 = stat_check(character2, stat2, dice_result2)
    result = diff2-diff1
    if crit1 and crit2:
        # handle both crits
        if success1 and success2:
            return "DCS", (result <= 0), abs(result)
        elif success1:
            return "H1", (result <= 0), max(0, diff1-diff2)
        elif success2:
            return "H2", (result <= 0), max(0, diff2-diff1)
        else:
            return "DCF", (result <= 0), abs(result)
    elif crit1:
        if success1:
            return "CS1", (result <= 0), max(0, diff1-diff2)
        else:
            return "CF1", (result <= 0), max(0, diff2-diff1)
    elif crit2:
        if success2:
            return "CS2", (result <= 0), max(0, diff2-diff1)
        else:
            return "CF2", (result <= 0), max(0, diff1-diff2)
    else:
        return "SF", (result <= 0), abs(result)

def group_stat_check(character_name_list, stat, *dice_results):
    characters = [C.load_character(name) for name in character_name_list]
    cs = []
    cf = []
    max_diff = -1
    for i, c in enumerate(characters):
        success, crit, diff = stat_check(c, stat, dice_results[i])
        if success:
            if crit:
                cs.append(c["name"])
            else:
                max_diff = max(max_diff, diff)
        elif crit:
            cf.append(c["name"])
    return cs, cf, max_diff

# Create RPG spells
def negativ_zone(dice_result, ennemi, dice_result_ennemi):
    hero = C.load_character("Hella")
    intel = dice_result - hero["INT"]
    sag = dice_result_ennemi - ennemi["WIS"]
    debuff = 10 - intel//20 + (100-hero["mental_health"]) // 10 + sag // 10
    buff = 5  - intel//40 + (100-hero["mental_health"])//20
    return debuff, buff

def base_heal(dice_result):
    hero = C.load_character("Heilari")
    success, crit, _ = stat_check(hero, "DEX", dice_result)
    if crit:
        if success:
            return 10
        else:
            return -5
    else:
        return 5*int(success)

def shock_sphere(ennemi, dice_result):
    success, crit, _ = stat_check(ennemi, "WIS", dice_result)
    return (1 + int(crit))*int(not success)

def fusrodah(dice_result_dex, dice_result_int, ennemi, ennemi_dice_result):
    hero = C.load_character("Saru")
    success, _, _ = stat_check(hero, "DEX", dice_result_dex)
    return success, stat_fight(hero, "INT", dice_result_int, ennemi, "CON", ennemi_dice_result)

def railgun(dice_result, ennemi, ennemi_dice_result):
    hero = C.load_character("DexterCeluiDu")
    INT = dice_result - hero["INT"]
    sag = ennemi_dice_result - ennemi["WIS"]
    return 10 - INT//5 + sag//10

def absolute_defense(dice_result):
    hero = C.load_character("DexterCeluiDu")
    INT = dice_result-hero["INT"]
    return (hero["CON"]+hero["WIS"])//20 - INT//10
