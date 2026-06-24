import contextlib

import fspy
from flask import Blueprint, jsonify, request

from backend.tabs.build_tab import _find_main_player, _resolve_item_name

inventory_bp = Blueprint("inventory_tab", __name__)

MAP_EVENT_FLAGS = {
    8600: [63010, 62010],  # Map: Limgrave, West
    8601: [63011, 62011],  # Map: Weeping Peninsula
    8602: [63012, 62012],  # Map: Limgrave, East
    8603: [63020, 62020],  # Map: Liurnia, East
    8604: [63021, 62021],  # Map: Liurnia, North
    8605: [63022, 62022],  # Map: Liurnia, West
    8606: [63030, 62030],  # Map: Altus Plateau
    8607: [63031, 62031],  # Map: Leyndell, Royal Capital
    8608: [63032, 62032],  # Map: Mt. Gelmir
    8609: [63040, 62040],  # Map: Caelid
    8610: [63041, 62041],  # Map: Dragonbarrow
    8611: [63050, 62050],  # Map: Mountaintops of the Giants, West
    8612: [63051, 62051],  # Map: Mountaintops of the Giants, East
    8613: [63060, 62060],  # Map: Ainsel River
    8614: [63061, 62061],  # Map: Lake of Rot
    8615: [63063, 62063],  # Map: Siofra River
    8616: [63062, 62062],  # Map: Mohgwyn Palace
    8617: [63064, 62064],  # Map: Deeproot Depths
    8618: [63052, 62052],  # Map: Consecrated Snowfield
    2008600: [63080, 62080],  # Map: Gravesite Plain
    2008601: [63081, 62081],  # Map: Scadu Altus
    2008602: [63082, 62082],  # Map: Southern Shore
    2008603: [63083, 62083],  # Map: Rauh Ruins
    2008604: [63084, 62084],  # Map: Abyss
}


def _set_map_event_flags(base_id: int, state: bool) -> None:
    if base_id in MAP_EVENT_FLAGS:
        with contextlib.suppress(Exception):
            flag_man = getattr(fspy, "PyCSEventFlagMan", None)
            if flag_man:
                instance = flag_man.get_instance()
                if instance and not getattr(instance, "is_null", True):
                    for flag in MAP_EVENT_FLAGS[base_id]:
                        instance.virtual_memory_flag.set_flag(flag, state)


def get_inventory_items():
    try:
        pgd = _find_main_player()
        if not pgd:
            return {"success": False, "message": "Game not loaded or player not found"}

        inv_data = pgd.equipment.equip_inventory_data.items_data
        lists_to_check = [("normal", inv_data.normal_entries_list()), ("key", inv_data.key_entries_list())]

        items = []
        for list_name, inv_entries in lists_to_check:
            for i, entry in enumerate(inv_entries):
                with contextlib.suppress(Exception):
                    raw_id = entry.item_id.param_id()
                    item_id = raw_id & 0x0FFFFFFF

                    cat_enum = int(entry.item_id.category())
                    if cat_enum == 0:
                        slot_hint = "weapon"
                    elif cat_enum == 1:
                        slot_hint = "armor"
                    elif cat_enum == 2:
                        slot_hint = "accessory"
                    elif cat_enum == 4:
                        slot_hint = "quick_item"
                    elif cat_enum == 8:
                        slot_hint = "gem"
                    else:
                        slot_hint = ""

                    if item_id > 0 and entry.quantity > 0:
                        resolved = _resolve_item_name(item_id, slot_hint)
                        items.append(
                            {
                                "index": i,
                                "list_name": list_name,
                                "item_id": item_id,
                                "raw_id": raw_id,
                                "quantity": entry.quantity,
                                "name": resolved.get("name", f"Item {item_id}") if resolved else f"Item {item_id}",
                                "category": resolved.get("category", "Unknown") if resolved else "Unknown",
                                "icon_id": resolved.get("icon_id") if resolved else None,
                                "max_num": resolved.get("max_num", 99) if resolved else 99,
                            }
                        )

        # Append unlocked Gestures to inventory so they can be viewed and removed
        try:
            gesture_data_ptr = _get_gesture_ptr()

            if gesture_data_ptr != 0:
                for is_dlc, offset in [(False, 0x04), (True, 0xD0)]:
                    for slot in range(0, 64):
                        addr = gesture_data_ptr + offset + (slot * 4)
                        current_val = _read_i32(addr)
                        if current_val not in (0, -1, 0xFFFFFFFF, 4294967295):
                            for key, (g_id, g_dlc, _idx) in GESTURE_MAPPING.items():
                                if g_id == current_val and g_dlc == is_dlc:
                                    resolved = _resolve_item_name(key, "quick_item")
                                    items.append(
                                        {
                                            "index": slot,
                                            "list_name": "gesture_dlc" if is_dlc else "gesture",
                                            "item_id": key,
                                            "raw_id": key | 0x40000000,
                                            "quantity": 1,
                                            "name": resolved.get("name", f"Gesture {key}")
                                            if resolved
                                            else f"Gesture {key}",
                                            "category": "Gesture",
                                            "icon_id": resolved.get("icon_id") if resolved else None,
                                            "max_num": 1,
                                        }
                                    )
                                    break
        except Exception as e:
            print(f"DEBUG GESTURE ERROR: {e}", flush=True)

        return {"success": True, "items": items}
    except Exception as e:
        return {"success": False, "message": str(e)}


@inventory_bp.route("/api/inventory")
def get_inventory():
    return jsonify(get_inventory_items())


@inventory_bp.route("/api/inventory/edit", methods=["POST"])
def edit_inventory_item():
    try:
        data = request.json
        index = data.get("index")
        quantity = data.get("quantity")
        list_name = data.get("list_name", "normal")

        pgd = _find_main_player()
        if not pgd:
            return jsonify({"success": False, "message": "Game not loaded"})

        # Handle Gesture removal
        if list_name.startswith("gesture"):
            if int(quantity) == 0:
                with contextlib.suppress(Exception):
                    is_dlc = list_name == "gesture_dlc"
                    gesture_data_ptr = _get_gesture_ptr(pgd)
                    if gesture_data_ptr != 0:
                        base_offset = 0xD0 if is_dlc else 0x04
                        addr = gesture_data_ptr + base_offset + (int(index) * 4)
                        _write_i32(addr, 0xFFFFFFFF)
            return jsonify({"success": True})

        inv_data = pgd.equipment.equip_inventory_data.items_data
        inv_entries = inv_data.key_entries_list() if list_name == "key" else inv_data.normal_entries_list()

        if 0 <= index < len(inv_entries):
            entry = inv_entries[index]
            entry.quantity = int(quantity)

            # If quantity is being set to 0, check if it's a map and turn off the flags
            if int(quantity) == 0:
                with contextlib.suppress(Exception):
                    base_id = entry.item_id.param_id() & 0x0FFFFFFF
                    _set_map_event_flags(base_id, False)

            return jsonify({"success": True})

        return jsonify({"success": False, "message": "Invalid index"})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)})


GESTURE_MAPPING = {
    9000: (1, False, 1),  # Bow
    9001: (3, False, 2),  # Polite Bow
    9002: (5, False, 3),  # My Thanks
    9003: (7, False, 4),  # Curtsy
    9004: (9, False, 5),  # Reverential Bow
    9005: (11, False, 6),  # My Lord
    9006: (13, False, 7),  # Warm Welcome
    9007: (15, False, 8),  # Wave
    9008: (17, False, 9),  # Casual Greeting
    9009: (19, False, 10),  # Strength!
    9010: (21, False, 11),  # As You Wish
    9011: (41, False, 12),  # Point Forwards
    9012: (43, False, 13),  # Point Upwards
    9013: (45, False, 14),  # Point Downwards
    9014: (47, False, 15),  # Beckon
    9015: (49, False, 16),  # Wait!
    9016: (51, False, 17),  # Calm Down!
    9017: (61, False, 18),  # Nod In Thought
    9018: (81, False, 19),  # Extreme Repentance
    9019: (83, False, 20),  # Grovel For Mercy
    9020: (101, False, 21),  # Rallying Cry
    9021: (103, False, 22),  # Heartening Cry
    9022: (105, False, 23),  # By My Sword
    9023: (107, False, 24),  # Hoslow's Oath
    9024: (109, False, 25),  # Fire Spur Me
    # Note: index 26 is cut content "The Carian Oath"
    9026: (121, False, 27),  # Bravo!
    9027: (141, False, 28),  # Jump for Joy
    9028: (143, False, 29),  # Triumphant Delight
    9029: (145, False, 30),  # Fancy Spin
    9030: (147, False, 31),  # Finger Snap
    9031: (161, False, 32),  # Dejection
    9032: (181, False, 33),  # Patches' Crouch
    9033: (183, False, 34),  # Crossed Legs
    9034: (185, False, 35),  # Rest
    9035: (187, False, 36),  # Sitting Sideways
    9036: (189, False, 37),  # Dozing Cross-Legged
    9037: (191, False, 38),  # Spread Out
    # Note: index 39 is cut content "Fetal Position"
    9039: (195, False, 40),  # Balled Up
    9040: (197, False, 41),  # What Do You Want?
    9041: (201, False, 42),  # Prayer
    9042: (203, False, 43),  # Desperate Prayer
    9043: (205, False, 44),  # Rapture
    9045: (207, False, 45),  # Erudition
    9046: (209, False, 46),  # Outer Order
    9047: (211, False, 47),  # Inner Order
    9048: (213, False, 48),  # Golden Order Totality
    9049: (217, False, 49),  # The Ring 1
    9050: (219, False, 50),  # The Ring 2
    2009001: (223, True, 1),  # May the Best Win
    2009002: (225, True, 2),  # The Two Fingers
    2009000: (227, True, 3),  # Ring of Miquella
    2009003: (229, True, 4),  # Let Us Go Together
    2009004: (231, True, 5),  # O Mother
    # Note: 233 is "Ring of Miquella" co-op, index 6
}


def _write_i32(addr: int, val: int) -> None:
    if hasattr(fspy, "write_i32"):
        fspy.write_i32(addr, val)
    elif hasattr(fspy, "write_u8"):
        fspy.write_u8(addr, val & 0xFF)
        fspy.write_u8(addr + 1, (val >> 8) & 0xFF)
        fspy.write_u8(addr + 2, (val >> 16) & 0xFF)
        fspy.write_u8(addr + 3, (val >> 24) & 0xFF)


def _get_gesture_ptr(pgd=None):
    # Match the CE script exactly using AOB scan for GameDataMan
    try:
        if not hasattr(fspy, "aob_scan") or not hasattr(fspy, "read_ptr"):
            return 0

        aob = fspy.aob_scan("48 8B 05 ?? ?? ?? ?? 48 85 C0 74 05 48 8B 40 58 C3 C3")
        if aob == 0:
            return 0

        offset = _read_i32(aob + 3)
        gdm_ptr_ptr = aob + 7 + offset

        GameDataMan = fspy.read_ptr(gdm_ptr_ptr)
        if GameDataMan == 0:
            return 0

        PlayerGameData = fspy.read_ptr(GameDataMan + 8)
        if PlayerGameData == 0:
            return 0

        GestureGameData = fspy.read_ptr(PlayerGameData + 0x8D8)
        return GestureGameData
    except Exception as e:
        print(f"DEBUG GESTURE PTR ERROR: {e}", flush=True)
    return 0


def _read_i32(addr: int) -> int:
    if hasattr(fspy, "read_i32"):
        return fspy.read_i32(addr)
    elif hasattr(fspy, "read_u8"):
        return (
            fspy.read_u8(addr)
            | (fspy.read_u8(addr + 1) << 8)
            | (fspy.read_u8(addr + 2) << 16)
            | (fspy.read_u8(addr + 3) << 24)
        )
    return 0


@inventory_bp.route("/api/inventory/add", methods=["POST"])
def add_inventory_item():
    try:
        data = request.json
        item_id = data.get("item_id")
        quantity = data.get("quantity", 1)

        global_id = data.get("global_id")
        max_num = data.get("max_num", 99)

        pgd = _find_main_player()
        if not pgd:
            return jsonify({"success": False, "message": "Game not loaded"})

        target_id = int(global_id) if global_id is not None else int(item_id)
        base_id = target_id & 0x0FFFFFFF

        # --- GESTURE INTERCEPTOR ---
        if base_id in GESTURE_MAPPING:
            gesture_id, is_dlc, offset_idx = GESTURE_MAPPING[base_id]
            try:
                gesture_data_ptr = _get_gesture_ptr()

                if gesture_data_ptr != 0:
                    base_offset = 0xD0 if is_dlc else 0x04
                    addr = gesture_data_ptr + base_offset + (offset_idx * 4)
                    _write_i32(addr, gesture_id)

            except Exception as e:
                print(f"DEBUG GESTURE WRITE ERROR: {e}", flush=True)
            # Gestures are written directly to memory, giving the physical item just litters the inventory
            return jsonify({"success": True})

        if hasattr(fspy, "give_item"):
            # Count existing quantity
            inv_data = pgd.equipment.equip_inventory_data.items_data
            current_qty = 0
            for inv_entries in [inv_data.normal_entries_list(), inv_data.key_entries_list()]:
                for entry in inv_entries:
                    with contextlib.suppress(Exception):
                        if (entry.item_id.param_id() & 0x0FFFFFFF) == int(item_id):
                            current_qty += entry.quantity

            if current_qty + int(quantity) > int(max_num):
                return jsonify(
                    {
                        "success": False,
                        "message": f"Cannot acquire: Exceeds max inventory limit ({max_num}). You already have {current_qty}.",
                    }
                )

            # Use default reinforce_level=-1 so the game handles upgrades natively via the ID
            ok = fspy.give_item(target_id, int(quantity))
            if ok:
                base_id = target_id & 0x0FFFFFFF
                _set_map_event_flags(base_id, True)

                return jsonify({"success": True})
            return jsonify({"success": False, "message": "Failed to add item (engine returned false)"})

        return jsonify({"success": False, "message": "give_item not available in current fspy version"})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)})
