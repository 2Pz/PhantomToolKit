SENTINEL_IDS = frozenset((-1, 0xFFFFFFFF, 0x0FFFFFFF, 0))

SPELL_CATEGORIES = ["Sorcery", "Incantation", "Self Buff - Sorcery", "Self Buff - Incantation"]

QUICK_ITEM_CATEGORIES = [
    "Normal Item",
    "Key Item",
    "Crafting Material",
    "Regenerative Material",
    "Reinforcement Material",
    "Info Item",
    "Wondrous Physick",
    "Remembrance",
    "Spirit Summon - Lesser",
    "Spirit Summon - Greater",
]

SLOT_DEFINITIONS = {
    "helmet": ("EquipParamProtector.csv", "category", ["Head"]),
    "armor": ("EquipParamProtector.csv", "category", ["Body"]),
    "gauntlet": ("EquipParamProtector.csv", "category", ["Arms"]),
    "leggings": ("EquipParamProtector.csv", "category", ["Legs"]),
    "head": ("EquipParamProtector.csv", "category", ["Head"]),
    "chest": ("EquipParamProtector.csv", "category", ["Body"]),
    "hands": ("EquipParamProtector.csv", "category", ["Arms"]),
    "legs": ("EquipParamProtector.csv", "category", ["Legs"]),
    "accessory": ("EquipParamAccessory.csv", "category", ["Accessory"]),
    "talisman": ("EquipParamAccessory.csv", "category", ["Accessory"]),
    "talisman_1": ("EquipParamAccessory.csv", "category", ["Accessory"]),
    "talisman_2": ("EquipParamAccessory.csv", "category", ["Accessory"]),
    "talisman_3": ("EquipParamAccessory.csv", "category", ["Accessory"]),
    "talisman_4": ("EquipParamAccessory.csv", "category", ["Accessory"]),
    "accessory_1": ("EquipParamAccessory.csv", "category", ["Accessory"]),
    "accessory_2": ("EquipParamAccessory.csv", "category", ["Accessory"]),
    "accessory_3": ("EquipParamAccessory.csv", "category", ["Accessory"]),
    "accessory_4": ("EquipParamAccessory.csv", "category", ["Accessory"]),
    "weapon": ("EquipParamWeapon.csv", "category", None),
    "wep": ("EquipParamWeapon.csv", "category", None),
    "weapon_r_1": ("EquipParamWeapon.csv", "category", None),
    "weapon_r_2": ("EquipParamWeapon.csv", "category", None),
    "weapon_r_3": ("EquipParamWeapon.csv", "category", None),
    "weapon_l_1": ("EquipParamWeapon.csv", "category", None),
    "weapon_l_2": ("EquipParamWeapon.csv", "category", None),
    "weapon_l_3": ("EquipParamWeapon.csv", "category", None),
    "arrow": ("EquipParamWeapon.csv", "category", ["arrow"]),
    "bolt": ("EquipParamWeapon.csv", "category", ["bolt"]),
    "ammo_1_1": ("EquipParamWeapon.csv", "category", ["arrow"]),
    "ammo_1_2": ("EquipParamWeapon.csv", "category", ["arrow"]),
    "ammo_2_1": ("EquipParamWeapon.csv", "category", ["bolt"]),
    "ammo_2_2": ("EquipParamWeapon.csv", "category", ["bolt"]),
    "spell": ("EquipParamGoods.csv", "goods_type", SPELL_CATEGORIES),
    "magic": ("EquipParamGoods.csv", "goods_type", SPELL_CATEGORIES),
    "quick": ("EquipParamGoods.csv", "goods_type", QUICK_ITEM_CATEGORIES),
    "quick_item": ("EquipParamGoods.csv", "goods_type", QUICK_ITEM_CATEGORIES),
    "great_rune": ("EquipParamGoods.csv", "goods_type", ["Great Rune"]),
    "physick": ("EquipParamGoods.csv", "goods_type", ["Wondrous Physick Tear"]),
    "physick_tear_1": ("EquipParamGoods.csv", "goods_type", ["Wondrous Physick Tear"]),
    "physick_tear_2": ("EquipParamGoods.csv", "goods_type", ["Wondrous Physick Tear"]),
    "gem": ("EquipParamGem.csv", "category", None),
    "ash_of_war": ("EquipParamGem.csv", "category", None),
}


def lookup(slot_key: str):
    if slot_key in SLOT_DEFINITIONS:
        return SLOT_DEFINITIONS[slot_key]

    candidates = [(len(key), value) for key, value in SLOT_DEFINITIONS.items() if key in slot_key]
    if not candidates:
        return None
    candidates.sort(key=lambda item: item[0], reverse=True)
    return candidates[0][1]


def csv_hints_for_slot(slot_key: str) -> list[str] | None:
    resolved = lookup(slot_key)
    if resolved is None:
        return None
    return [resolved[0]]


def csv_names() -> set[str]:
    return {csv_name for csv_name, _column, _categories in SLOT_DEFINITIONS.values()}
