"""
Build data module — reads equipment/stats from the game via fspy,
converts between backend (build.json / fspy) and frontend (dashboard) formats,
and applies builds back into the game.
"""

import contextlib

import fspy

from backend.utils.items import ItemAssetService

# ─── Sentinel / empty values ───────────────────────────────────────────────────

SENTINEL_IDS = frozenset((-1, 0, 0xFFFFFFFF, 0x0FFFFFFF))
ATTRIBUTES = ("vigor", "mind", "endurance", "strength", "dexterity", "intelligence", "faith", "arcane")


# ─── Backend ↔ Frontend slot mapping ──────────────────────────────────────────

# Backend keys are what fspy.apply_build / build.json uses.
# Frontend keys are what the dashboard equipment grid uses.

_BACKEND_TO_FRONTEND = {
    "primary_right_wep": "weapon_r_1",
    "secondary_right_wep": "weapon_r_2",
    "tertiary_right_wep": "weapon_r_3",
    "primary_left_wep": "weapon_l_1",
    "secondary_left_wep": "weapon_l_2",
    "tertiary_left_wep": "weapon_l_3",
    "primary_arrow": "ammo_1_1",
    "secondary_arrow": "ammo_1_2",
    "primary_bolt": "ammo_2_1",
    "secondary_bolt": "ammo_2_2",
    "helmet": "head",
    "armor": "chest",
    "gauntlet": "hands",
    "leggings": "legs",
    "accessory_1": "talisman_1",
    "accessory_2": "talisman_2",
    "accessory_3": "talisman_3",
    "accessory_4": "talisman_4",
    "physick_tear_1": "physick_tear_1",
    "physick_tear_2": "physick_tear_2",
    "great_rune": "great_rune",
}

# Quick items: quick_item_1..10 → quick_1_1..quick_1_5, quick_2_6..quick_2_10
for _i in range(1, 6):
    _BACKEND_TO_FRONTEND[f"quick_item_{_i}"] = f"quick_1_{_i}"
for _i in range(6, 11):
    _BACKEND_TO_FRONTEND[f"quick_item_{_i}"] = f"quick_2_{_i}"

# Spells: magic_slot_0..13 → spell_1..14
for _i in range(14):
    _BACKEND_TO_FRONTEND[f"magic_slot_{_i}"] = f"spell_{_i + 1}"

_FRONTEND_TO_BACKEND = {v: k for k, v in _BACKEND_TO_FRONTEND.items()}


# ─── Item name resolution via ItemAssetService ────────────────────────────────

_service = None


def _get_service():
    global _service
    if _service is None:
        _service = ItemAssetService()
    return _service


def _resolve_item_name(item_id: int, frontend_slot: str):
    """Look up item name + icon from the CSV catalog for display in the dashboard."""
    if item_id in SENTINEL_IDS or item_id <= 0:
        return None

    svc = _get_service()
    enriched = svc.enrich_slot_item(frontend_slot, item_id)
    if not enriched:
        out = {"id": item_id, "name": f"Item {item_id}"}
    else:
        out = {
            "id": enriched.get("base_id", enriched.get("id", item_id)),
            "name": enriched.get("name", f"Item {item_id}"),
            "icon_id": enriched.get("icon_id"),
            "category": enriched.get("category"),
            "max_num": enriched.get("max_num"),
        }

    # For weapons, extract the upgrade level from the item ID
    if frontend_slot.startswith("weapon_"):
        upgrade = item_id % 100
        if upgrade > 0:
            out["upgrade"] = upgrade
            out["id"] = item_id - upgrade

    return out


# ─── GaitemImp helper (for ash-of-war and handle resolution) ──────────────────

_gaitem_imp = None


def _get_gaitem_imp():
    global _gaitem_imp
    if _gaitem_imp is None:
        with contextlib.suppress(Exception):
            _gaitem_imp = fspy.PyCSGaitemImp.get_instance()
    return _gaitem_imp


def _resolve_gaitem_handle(handle):
    """Resolve a gaitem handle to a param ID."""
    imp = _get_gaitem_imp()
    if imp is None:
        return -1
    try:
        result = imp.param_id_from_handle(handle)
        return result if result is not None and result > 0 else -1
    except Exception:
        return -1


def _get_ash_of_war(weapon_handle):
    """Get the Ash of War param ID for a weapon via its gaitem handle."""
    imp = _get_gaitem_imp()
    if imp is None:
        return -1
    try:
        result = imp.gaitem_ins_by_handle(weapon_handle)
        if result is None:
            return -1

        addr = result if isinstance(result, int) else result.address
        if addr == 0:
            return -1

        wep_ins = fspy.PyCSWepGaitemIns(addr)
        if wep_ins.is_null:
            return -1

        gem_slots = wep_ins.gem_slot_table.gem_slots
        if not gem_slots:
            return -1

        raw_slot = gem_slots[0]
        gem_slot = fspy.PyCSGemSlot(raw_slot) if isinstance(raw_slot, int) else raw_slot
        if gem_slot.gaitem_handle_is_none():
            return -1

        return _resolve_gaitem_handle(gem_slot.gaitem_handle)
    except Exception:
        return -1


# ─── Reading equipment from PlayerGameData ────────────────────────────────────


def _read_equipment_from_pgd(pgd):
    """
    Read the full equipment dict from a PlayerGameData object.
    Returns a dict with backend keys (same format as build.json / debug equipment.py).
    """
    eq = pgd.equipment
    entries = eq.equipment_entries
    magic = eq.equip_magic_data
    item_data = eq.equip_item_data

    # Build param_id → gaitem_handle map for ash of war lookups
    chr_asm = eq.chr_asm
    param_to_handle = {}
    handles = chr_asm.gaitem_handles
    param_ids = chr_asm.equipment_param_ids
    for i in range(min(len(handles), len(param_ids))):
        if param_ids[i] != -1 and handles[i] != 0:
            param_to_handle[param_ids[i]] = handles[i]

    def get_weapon_handle(item_id):
        if item_id.is_null:
            return None
        return param_to_handle.get(item_id.param_id())

    def wpn(item_id, raw_handle=None):
        if item_id.is_null:
            return -1
        pid = item_id.param_id()
        if raw_handle is not None:
            ash = _get_ash_of_war(raw_handle)
            if ash > 0:
                return {"id": pid, "ash_of_war": ash}
        return pid

    def ammo_item(val):
        if val <= 0:
            return -1

        # Respect the CSV max quantity, defaulting to 99 if not found
        item_info = _get_service().find_item_any_csv(val, hints=["EquipParamWeapon.csv"])
        count = item_info.max_num if item_info and item_info.max_num else 99

        try:
            inv_data = pgd.equipment.equip_inventory_data.items_data
            found = False
            # Check normal items first as ammo is almost always here
            for entry in inv_data.normal_entries_list():
                if (entry.item_id.param_id() & 0x0FFFFFFF) == val:
                    count = getattr(entry, "quantity", 99)
                    found = True
                    break

            if not found:
                for entry in inv_data.key_entries_list():
                    if (entry.item_id.param_id() & 0x0FFFFFFF) == val:
                        count = getattr(entry, "quantity", 99)
                        break
        except Exception:
            pass

        return {"id": val, "count": count}

    def equip_data_item(data_item):
        def resolve_inventory_index(index):
            try:
                inv_data = pgd.equipment.equip_inventory_data.items_data
                key_cap = inv_data.key_items_capacity
                if index < key_cap:
                    inv_entries = inv_data.key_entries_list()
                    idx_to_check = index
                else:
                    inv_entries = inv_data.normal_entries_list()
                    idx_to_check = index - key_cap

                if 0 <= idx_to_check < len(inv_entries):
                    entry = inv_entries[idx_to_check]
                    item_id = entry.item_id.param_id() & 0x0FFFFFFF
                    if item_id > 0:
                        return {"id": item_id, "count": getattr(entry, "quantity", 1)}
            except Exception:
                pass
            return None

        if isinstance(data_item, int):
            if data_item in (-1, 0, 0xFFFFFFFF):
                return -1
            res = resolve_inventory_index(data_item)
            if res:
                return res
            handle = data_item
        else:
            if data_item.is_null:
                return -1

            if hasattr(data_item, "index"):
                res = resolve_inventory_index(data_item.index)
                if res:
                    return res

            if hasattr(data_item, "gaitem_handle_is_none") and not data_item.gaitem_handle_is_none():
                handle = data_item.gaitem_handle
            else:
                return -1

        pid = _resolve_gaitem_handle(handle)
        return {"id": pid} if pid > 0 else -1

    result = {}

    # Magic slots
    if magic is not None:
        for i, raw in enumerate(magic.entries):
            if raw.is_null:
                result[f"magic_slot_{i}"] = -1
            else:
                pid = raw.param_id
                result[f"magic_slot_{i}"] = {"id": pid} if pid > 0 else -1

    # Quick items
    for i, data_item in enumerate(item_data.quick_slots):
        result[f"quick_item_{i + 1}"] = equip_data_item(data_item)

    # Physick tears
    try:
        tear_1 = getattr(eq, "physick_tear_1", 0)
        tear_2 = getattr(eq, "physick_tear_2", 0)

        rune = getattr(eq, "great_rune", 0)

        result["physick_tear_1"] = {"id": tear_1 & 0x0FFFFFFF} if tear_1 not in (0, 0xFFFFFFFF) else -1
        result["physick_tear_2"] = {"id": tear_2 & 0x0FFFFFFF} if tear_2 not in (0, 0xFFFFFFFF) else -1
        result["great_rune"] = {"id": rune & 0x0FFFFFFF} if rune not in (0, 0xFFFFFFFF) else -1
    except Exception:
        result["physick_tear_1"] = -1
        result["physick_tear_2"] = -1
        result["great_rune"] = -1

    # Accessories (talismans)
    accessory_ids = list(entries.accessories)
    while len(accessory_ids) < 4:
        accessory_ids.append(-1)

    # Weapons
    result["primary_right_wep"] = wpn(entries.weapon_primary_right, get_weapon_handle(entries.weapon_primary_right))
    result["secondary_right_wep"] = wpn(
        entries.weapon_secondary_right, get_weapon_handle(entries.weapon_secondary_right)
    )
    result["tertiary_right_wep"] = wpn(entries.weapon_tertiary_right, get_weapon_handle(entries.weapon_tertiary_right))
    result["primary_left_wep"] = wpn(entries.weapon_primary_left, get_weapon_handle(entries.weapon_primary_left))
    result["secondary_left_wep"] = wpn(entries.weapon_secondary_left, get_weapon_handle(entries.weapon_secondary_left))
    result["tertiary_left_wep"] = wpn(entries.weapon_tertiary_left, get_weapon_handle(entries.weapon_tertiary_left))

    # Armor
    result["helmet"] = wpn(entries.protector_head)
    result["armor"] = wpn(entries.protector_chest)
    result["gauntlet"] = wpn(entries.protector_hands)
    result["leggings"] = wpn(entries.protector_legs)

    # Accessories
    result["accessory_1"] = accessory_ids[0] if len(accessory_ids) > 0 else -1
    result["accessory_2"] = accessory_ids[1] if len(accessory_ids) > 1 else -1
    result["accessory_3"] = accessory_ids[2] if len(accessory_ids) > 2 else -1
    result["accessory_4"] = accessory_ids[3] if len(accessory_ids) > 3 else -1

    # Ammo
    result["primary_arrow"] = ammo_item(entries.arrow_primary)
    result["secondary_arrow"] = ammo_item(entries.arrow_secondary)
    result["primary_bolt"] = ammo_item(entries.bolt_primary)
    result["secondary_bolt"] = ammo_item(entries.bolt_secondary)

    return result


def _read_stats_from_pgd(pgd):
    """Read stats from a PlayerGameData object."""
    stats = {}
    for attr in ATTRIBUTES:
        with contextlib.suppress(Exception):
            stats[attr] = int(getattr(pgd, attr, 0) or 0)
    for source, target in (
        ("level", "level"),
        ("rune_count", "runes"),
        ("scadutree_blessing", "scadutree_blessing"),
        ("reversed_spirit_ash", "revered_spirit_ash"),
    ):
        with contextlib.suppress(Exception):
            stats[target] = int(getattr(pgd, source, 0) or 0)
    return stats


def _read_appearance_from_pgd(pgd):
    """Read appearance data (gender, voice, face data) from PlayerGameData."""
    app = {}
    with contextlib.suppress(Exception):
        app["gender"] = int(pgd.gender)
    with contextlib.suppress(Exception):
        app["voice_type"] = int(pgd.voice_type)
    with contextlib.suppress(Exception):
        if pgd.face_data and pgd.face_data.face_data_buffer:
            app["face_data"] = list(pgd.face_data.face_data_buffer.buffer)
    return app


# ─── Convert backend equipment dict to frontend slots dict ────────────────────


def _backend_equipment_to_frontend_slots(equipment: dict) -> dict:
    """
    Convert a backend equipment dict (build.json format) to frontend slots dict
    with resolved item names and icons for the dashboard.
    """
    slots = {}
    for backend_key, frontend_key in _BACKEND_TO_FRONTEND.items():
        raw = equipment.get(backend_key, -1)
        if raw is None or raw == -1:
            continue

        # Parse the raw value
        if isinstance(raw, dict):
            item_id = raw.get("id", -1)
            ash_of_war = raw.get("ash_of_war", -1)
            count = raw.get("count")
        elif isinstance(raw, int):
            item_id = raw
            ash_of_war = -1
            count = None
        else:
            continue

        if item_id in SENTINEL_IDS or item_id <= 0:
            continue

        # Resolve item name from catalog
        resolved = _resolve_item_name(item_id, frontend_key)
        if resolved is None:
            resolved = {"id": item_id, "name": f"Item {item_id}"}

        slot_data = {**resolved}
        if ash_of_war is not None and ash_of_war > 0:
            slot_data["ash_of_war"] = ash_of_war
            ash_item = _get_service().find_item_any_csv(ash_of_war, hints=["EquipParamGem.csv"])
            if ash_item:
                slot_data["ash_of_war_name"] = ash_item.name
        if count is not None:
            slot_data["count"] = count

        slots[frontend_key] = slot_data

    return slots


# ─── Convert frontend slots back to backend equipment dict ────────────────────


def _frontend_slots_to_backend_equipment(slots: dict) -> dict:
    """
    Convert frontend slots dict back to backend equipment dict (build.json format)
    for passing to fspy.apply_build.
    """
    equipment = {}
    for frontend_key, backend_key in _FRONTEND_TO_BACKEND.items():
        item = slots.get(frontend_key)
        if item is None:
            equipment[backend_key] = -1
            continue

        item_id = item.get("id", -1) if isinstance(item, dict) else -1
        if item_id in SENTINEL_IDS or item_id <= 0:
            equipment[backend_key] = -1
            continue

        # For weapons, encode the upgrade level into the ID
        effective_id = item_id
        if frontend_key.startswith("weapon_"):
            upgrade = item.get("upgrade", 0) if isinstance(item, dict) else 0
            if upgrade and upgrade > 0:
                effective_id = (item_id - (item_id % 100)) + upgrade

        # Build the value
        out = {"id": effective_id}
        if isinstance(item, dict):
            count = item.get("count")
            if count is not None:
                out["count"] = int(count)
            ash = item.get("ash_of_war", -1)
            if ash is not None and ash > 0:
                out["ash_of_war"] = int(ash)

        # Simplify: if only id, use plain int
        if list(out.keys()) == ["id"]:
            equipment[backend_key] = out["id"]
        else:
            equipment[backend_key] = out

    return equipment


# ═══════════════════════════════════════════════════════════════════════════════
#  Public API — used by app.py and game_data.py
# ═══════════════════════════════════════════════════════════════════════════════


def _iter_players():
    try:
        world = fspy.PyWorldChrMan.get_instance()
        if world is not None and not world.is_null:
            for p in world.player_chr_set.characters():
                pgd = p.player_game_data
                if pgd:
                    yield p, pgd
    except Exception:
        pass


def _find_main_player():
    """Find the main player's PlayerGameData."""
    for _, pgd in _iter_players():
        if pgd.equipment.is_main_player:
            return pgd
    return None


def _find_player_by_index(player_index: int):
    """Find a player's PlayerGameData by index in the chr set."""
    for idx, (_, pgd) in enumerate(_iter_players()):
        if idx == player_index:
            return pgd
    return None


def _find_player_by_steam_id(steam_id: int):
    """Find a player's PlayerGameData by Steam ID."""
    for p, pgd in _iter_players():
        with contextlib.suppress(Exception):
            entry = p.session_manager_player_entry
            if entry is not None and not entry.is_null and int(entry.steam_id) == steam_id:
                return pgd
    return None


def _fill_missing_slots_from_local(pgd, equipment, local_eq=None):
    """
    If pgd is a remote player, fill empty spell and quick item slots
    using the local player's equipment to avoid clearing them.
    """
    with contextlib.suppress(Exception):
        if pgd and not pgd.equipment.is_main_player:
            if local_eq is None:
                local_pgd = _find_main_player()
                if local_pgd:
                    local_eq = _read_equipment_from_pgd(local_pgd)
            if local_eq:
                for i in range(14):
                    k = f"magic_slot_{i}"
                    if equipment.get(k, -1) == -1 and k in local_eq:
                        equipment[k] = local_eq[k]
                for i in range(1, 11):
                    k = f"quick_item_{i}"
                    if equipment.get(k, -1) == -1 and k in local_eq:
                        equipment[k] = local_eq[k]


def _read_full_player_data(pgd, local_eq=None):
    equipment = _read_equipment_from_pgd(pgd)
    _fill_missing_slots_from_local(pgd, equipment, local_eq)
    stats = _read_stats_from_pgd(pgd)
    appearance = _read_appearance_from_pgd(pgd)
    slots = _backend_equipment_to_frontend_slots(equipment)
    return stats, slots, appearance


def _handle_build_error(e):
    import traceback

    traceback.print_exc()
    if "not initialized" in str(e):
        return {"loaded": False, "message": "Game not loaded."}
    return {"loaded": False, "message": str(e)}


def get_build_snapshot_from_pgd(pgd, local_eq=None):
    """
    Build a snapshot dict from a PlayerGameData (for caching / recent players).
    Returns {status: {...}, build: {slots: {...}}} or None on error.
    Used by game_data.py to capture other players' builds.
    """
    try:
        stats, slots, appearance = _read_full_player_data(pgd, local_eq)
        return {"status": stats, "build": {"slots": slots}, "appearance": appearance}
    except Exception:
        import traceback

        traceback.print_exc()
        return None


def get_build_data(steam_id=None, player_index=None):
    """
    Retrieve build data for a player (defaults to local/main player).
    Returns the format the dashboard expects:
      {loaded: True, build: {slots: {…}}, status: {…}}
    Used by app.py /api/build endpoint.
    """
    try:
        pgd = None
        if player_index is not None:
            pgd = _find_player_by_index(player_index)
        elif steam_id:
            pgd = _find_player_by_steam_id(steam_id)
        else:
            pgd = _find_main_player()

        if pgd is None:
            return {"loaded": False, "message": "Player not found or game not loaded."}

        stats, slots, appearance = _read_full_player_data(pgd)

        return {
            "loaded": True,
            "build": {"slots": slots},
            "status": stats,
            "appearance": appearance,
        }
    except Exception as e:
        return _handle_build_error(e)


def apply_build(payload: dict):
    """
    Apply a build to the local player via fspy.apply_build.
    payload comes from the dashboard: {slots: {...}, status: {...} | null}
    Returns updated build state after applying.
    Used by app.py /api/build/apply endpoint.
    """
    try:
        pgd = _find_main_player()
        if pgd is None:
            return {"loaded": False, "message": "Player not found or game not loaded."}

        status = payload.get("status")
        equipment = None
        if "slots" in payload and payload["slots"] is not None:
            frontend_slots = payload.get("slots", {})
            equipment = _frontend_slots_to_backend_equipment(frontend_slots)

        # Build stats dict for fspy.apply_build
        stats_dict = None
        if status:
            stats_dict = {}
            for attr in ATTRIBUTES:
                val = status.get(attr)
                if val is not None:
                    stats_dict[attr] = int(val)
            val = status.get("level")
            if val is not None:
                stats_dict["level"] = int(val)
            # DLC blessings
            for src, dst in (
                ("scadutree_blessing", "scadutree_blessing"),
                ("revered_spirit_ash", "revered_spirit_ash_blessing"),
            ):
                val = status.get(src)
                if val is not None:
                    stats_dict[dst] = int(val)

        # Apply via fspy if there's anything to apply
        ok = True
        if equipment is not None or stats_dict is not None:
            ok = fspy.apply_build(equipment, stats=stats_dict)

        # Apply appearance if requested
        appearance = payload.get("appearance")
        if appearance and pgd:
            with contextlib.suppress(Exception):
                if "gender" in appearance and pgd.gender != int(appearance["gender"]):
                    pgd.gender = int(appearance["gender"])
                if "voice_type" in appearance:
                    pgd.voice_type = int(appearance["voice_type"])
                if "face_data" in appearance and pgd.face_data and pgd.face_data.face_data_buffer:
                    buf = appearance["face_data"]
                    if isinstance(buf, list):
                        sz = pgd.face_data.face_data_buffer.buffer_size
                        pgd.face_data.face_data_buffer.buffer = (buf + [0] * sz)[:sz]

        # Re-read the state after applying
        pgd = _find_main_player()
        if pgd is not None:
            new_stats, new_slots, new_app = _read_full_player_data(pgd)

            msg = "Build applied successfully." if ok else "Build applied with some errors."

            return {
                "loaded": True,
                "build": {"slots": new_slots},
                "status": new_stats,
                "appearance": new_app,
                "message": msg,
            }

        return {"loaded": True, "message": "Build applied." if ok else "Build applied with errors."}
    except Exception as e:
        return _handle_build_error(e)


def inspect_saved_build(payload: dict):
    """
    Parse a saved build file (build.json format) and convert it to the
    dashboard's frontend format for previewing. Does NOT apply anything.
    payload: {equipment: {...}, stats: {...}, shadow_of_erdtree: {...}}
    Used by app.py /api/build/inspect endpoint.
    """
    try:
        equipment = payload.get("equipment", {})
        if not equipment or not isinstance(equipment, dict):
            return {"success": False, "message": "Invalid build file: missing equipment."}

        # Convert backend equipment to frontend slots
        slots = _backend_equipment_to_frontend_slots(equipment)

        # Parse stats
        raw_stats = payload.get("stats", {})
        sote = payload.get("shadow_of_erdtree", {})
        status = {}
        for attr in ATTRIBUTES:
            val = raw_stats.get(attr)
            if val is not None:
                status[attr] = int(val)
        val = raw_stats.get("level")
        if val is not None:
            status["level"] = int(val)
        if sote:
            scadu = sote.get("scadutree_blessing")
            if scadu is not None:
                status["scadutree_blessing"] = int(scadu)
            spirit = sote.get("revered_spirit_ash_blessing")
            if spirit is not None:
                status["revered_spirit_ash"] = int(spirit)

        return {
            "success": True,
            "build": {"slots": slots},
            "status": status,
            "appearance": payload.get("appearance", {}),
        }
    except Exception as e:
        return {"success": False, "message": str(e)}
