import contextlib
import time

import fspy

from backend.tabs.build_tab import _find_main_player, _read_equipment_from_pgd, get_build_snapshot_from_pgd

_recent_players = {}
_recent_build_snapshots = {}


def get_recent_build_snapshot(steam_id: int):
    snapshot = _recent_build_snapshots.get(int(steam_id))
    if not snapshot:
        return {"loaded": False, "message": "No cached build snapshot for this recent player."}
    return {"loaded": True, "readonly": True, **snapshot}


def _get_player_game_data(entry):
    try:
        gdm = fspy.PyGameDataMan.get_instance()
        if gdm is None or gdm.is_null:
            return None, None

        if entry.is_local_player:
            pgd = gdm.main_player_game_data
            if pgd and not pgd.is_null:
                return pgd.character_name or "", pgd.level
            return None, None

        idx = entry.game_data_index
        if idx < 0:
            return None, None
        pgd_list = gdm.player_game_data_list
        if idx < len(pgd_list):
            pgd = pgd_list[idx]
            if not pgd.is_null:
                return pgd.character_name or "", pgd.level
    except Exception:
        pass
    return None, None


def _get_main_player_hp():
    try:
        wcm = fspy.PyWorldChrMan.get_instance()
        if wcm.is_null:
            return 0, 1
        player = wcm.main_player
        if player is None or player.is_null or player.chr_ins.is_null:
            return 0, 1
        dm = player.chr_ins.modules.data
        if not dm.is_null:
            return dm.hp, dm.max_hp
    except Exception:
        pass
    return 0, 1


def get_player_data():
    global _recent_players
    try:
        try:
            world = fspy.PyWorldChrMan.get_instance()
        except RuntimeError as e:
            if "not initialized" in str(e):
                world = None
            else:
                raise

        if world is None or getattr(world, "is_null", False):
            recent_out = [p for _, p in sorted(_recent_players.items(), key=lambda x: x[1]["last_seen"], reverse=True)]
            return {"loaded": False, "recent_players": recent_out}

        chr_set = getattr(world, "player_chr_set", None)
        if chr_set is None or getattr(chr_set, "is_null", False):
            recent_out = [p for _, p in sorted(_recent_players.items(), key=lambda x: x[1]["last_seen"], reverse=True)]
            return {"loaded": False, "recent_players": recent_out}

        players_out = []
        current_steam_ids = set()

        local_eq = None
        main_pgd = _find_main_player()
        if main_pgd:
            with contextlib.suppress(Exception):
                local_eq = _read_equipment_from_pgd(main_pgd)

        try:
            characters_list = chr_set.characters()
        except Exception:
            characters_list = []

        for player_index, player_ins in enumerate(characters_list):
            try:
                if player_ins is None or getattr(player_ins, "is_null", False):
                    continue

                pgd = player_ins.player_game_data
                if pgd is None or getattr(pgd, "is_null", False):
                    continue

                name = pgd.character_name
                if isinstance(name, bytes):
                    name = name.decode("utf-16-le", errors="replace")
                name = name.replace("\0", "").strip() or "?"

                steam_id = 0
                steam_name = "?"
                is_local = False
                is_host = False

                with contextlib.suppress(Exception):
                    entry = player_ins.session_manager_player_entry
                    if entry is not None and not entry.is_null:
                        steam_id = int(entry.steam_id)
                        steam_name = entry.steam_name.to_python_string().replace("\0", "").strip() or "?"
                        is_local = entry.is_local_player
                        is_host = entry.is_host

                is_main_player = False
                with contextlib.suppress(Exception):
                    is_main_player = pgd.equipment.is_main_player

                if steam_id == 0 and not is_local and not is_main_player:
                    continue

                hp = pgd.current_hp
                max_hp = pgd.current_max_hp
                level = pgd.level

                final_name = (
                    name if name != "?" else (steam_name if steam_name != "?" else f"Player_{steam_id & 0xFFFF:04X}")
                )

                player_obj = {
                    "name": final_name,
                    "level": level or 0,
                    "hp": hp,
                    "max_hp": max_hp,
                    "is_local": is_local or is_main_player,
                    "is_host": is_host,
                    "steam_id": steam_id,
                    "player_index": player_index,
                    "last_seen": time.time(),
                }

                if not player_obj["is_local"]:
                    with contextlib.suppress(Exception):
                        snapshot = get_build_snapshot_from_pgd(pgd, local_eq=local_eq)
                        if snapshot:
                            player_obj["build_snapshot"] = snapshot
                            if steam_id != 0:
                                _recent_build_snapshots[steam_id] = snapshot

                players_out.append(player_obj)
                if steam_id != 0:
                    current_steam_ids.add(steam_id)
                    if not player_obj["is_local"]:
                        _recent_players[steam_id] = player_obj
            except Exception:
                import traceback

                traceback.print_exc()
                continue

        # Prepare recent players list (exclude current players)
        recent_out = []
        for sid, p in sorted(_recent_players.items(), key=lambda x: x[1]["last_seen"], reverse=True):
            if sid not in current_steam_ids:
                recent_out.append(p)

        if not players_out:
            return {"loaded": False, "recent_players": recent_out}

        return {"loaded": True, "players": players_out, "recent_players": recent_out}
    except Exception as e:
        import traceback

        traceback.print_exc()
        return {"loaded": False, "_debug": {"error": str(e)}}


def perform_game_action(action_type):
    try:
        if action_type == "fix_infinite_loading":
            try:
                import time

                #    Write grace ID warp target to GameMan before warping
                try:
                    gm = fspy.PyGameMan.get_instance()
                    if gm and not gm.is_null:
                        warp_bytes = list((11102950).to_bytes(4, "little"))
                        fspy.patch_memory(gm.address + 0xB60, warp_bytes)
                except Exception:
                    pass

                # Safety check: not in multiplayer
                try:
                    wcm = fspy.PyWorldChrMan.get_instance()
                    if wcm and not wcm.is_null:
                        chr_set = getattr(wcm, "player_chr_set", None)
                        if chr_set and not chr_set.is_null:
                            players = chr_set.characters()
                            if len(players) > 1:
                                return {"success": False, "message": "Cannot warp while in multiplayer."}
                except Exception:
                    pass

                # Warp with retry (up to 5 seconds)
                warped = False
                end_time = time.time() + 5.0
                while time.time() < end_time and not warped:
                    try:
                        if fspy.trigger_lua_warp(11102950):
                            warped = True
                            break
                    except Exception:
                        pass
                    time.sleep(0.5)

                return {
                    "success": warped,
                    "message": "Warping to Roundtable Hold to fix infinite loading."
                    if warped
                    else "Failed to warp after multiple attempts.",
                }
            except Exception as e:
                return {"success": False, "message": f"Warp error: {e}"}

        elif action_type == "quit_to_menu":
            try:
                gm = fspy.PyGameMan.get_instance()
                if gm is None or gm.is_null:
                    return {"success": False, "message": "GameMan not found."}
                gm.unk8 = 1
                gm.warp_requested = True
                gm.save_requested = True
                return {"success": True, "message": "Quit to menu triggered."}
            except Exception as e:
                return {"success": False, "message": f"Quit error: {e}"}

        world_chr_man = fspy.PyWorldChrMan.get_instance()
        if world_chr_man.is_null:
            return {"success": False, "message": "Game not loaded"}

        player = world_chr_man.main_player
        if player is None or player.is_null or player.chr_ins.is_null:
            return {"success": False, "message": "Player not found"}

        if action_type == "heal":
            data_module = player.chr_ins.modules.data
            if not data_module.is_null:
                data_module.hp = data_module.max_hp
                with contextlib.suppress(Exception):
                    data_module.mp = getattr(data_module, "max_mp", data_module.mp)
                with contextlib.suppress(Exception):
                    data_module.fp = getattr(data_module, "max_fp", data_module.fp)
                return {"success": True, "message": "Healed to full"}
            return {"success": False, "message": "Data module not available"}

        elif action_type == "fog_wall":
            mods = player.chr_ins.modules
            if mods and not mods.is_null:
                evt = mods.event
                if evt and not evt.is_null:
                    evt.request_animation_id = 60060
                    return {"success": True, "message": "Fog wall animation triggered."}
            return {"success": False, "message": "Could not trigger fog wall animation."}

        elif action_type == "add_runes":
            return {"success": True, "message": "Rune modification is view-only in this example"}
        elif action_type == "toggle_god_mode":
            return {"success": True, "message": "God mode toggled (mocked)"}

        return {"success": False, "message": "Unknown action"}
    except Exception as e:
        if "not initialized" in str(e):
            return {"success": False, "message": "Game not loaded"}
        return {"success": False, "message": str(e)}
