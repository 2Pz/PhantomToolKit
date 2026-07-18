import threading
import time

_no_weight_addr = None
_active_cheats = {}
_cheat_thread_started = False


def _cheat_loop():
    import fspy

    native_cheats = {"noDead": 0, "noDamage": 1, "noFP": 2, "noStamina": 3, "noGoods": 0}

    # Store previous state for hook-based cheats to detect toggles
    prev_no_hit = False

    while True:
        try:
            current_no_hit = _active_cheats.get("noHit", False)
            if current_no_hit != prev_no_hit:
                if hasattr(fspy, "toggle_no_hit"):
                    fspy.toggle_no_hit(current_no_hit)
                prev_no_hit = current_no_hit
            if getattr(fspy, "get_main_player_ptr", None) is not None:
                player_ptr = fspy.get_main_player_ptr()
                if player_ptr != 0:
                    base_flags_ptr = fspy.read_ptr(player_ptr + 0x190)
                    base_flags = fspy.read_ptr(base_flags_ptr + 0x0) if base_flags_ptr != 0 else 0

                    def apply_bit_flag_loop(target_ptr, bit):
                        cur = fspy.read_u8(target_ptr)
                        nxt = cur | (1 << bit)
                        if nxt != cur:
                            fspy.write_u8(target_ptr, nxt)

                    for cheat_name in ["noDead", "noDamage", "noFP", "noStamina"]:
                        if _active_cheats.get(cheat_name) and base_flags != 0:
                            apply_bit_flag_loop(base_flags + 0x19B, native_cheats[cheat_name])

                    if _active_cheats.get("noGoods"):
                        apply_bit_flag_loop(player_ptr + 0x532, native_cheats["noGoods"])

            if _active_cheats.get("noArrow"):
                dbg = fspy.PyWorldChrManDbgFlags.get_instance()
                if dbg and not getattr(dbg, "is_null", True) and not dbg.all_no_arrow_consume:
                    dbg.all_no_arrow_consume = True
        except Exception:
            pass
        time.sleep(1)


def get_active_cheats():
    global _active_cheats
    return _active_cheats


def toggle_cheat(cheat_name: str, enabled: bool):
    try:
        import fspy

        global _no_weight_addr, _active_cheats, _cheat_thread_started

        if not _cheat_thread_started:
            t = threading.Thread(target=_cheat_loop, daemon=True)
            t.start()
            _cheat_thread_started = True

        _active_cheats[cheat_name] = enabled
        if cheat_name == "noWeight":
            if getattr(fspy, "aob_scan", None) is None:
                return {"success": False, "message": "sys_no_weight_unsupported"}
            if _no_weight_addr is None:
                a1 = fspy.aob_scan("FF C3 83 FB 05 7C CB 4C 8D 5C 24 70")
                if a1 != 0:
                    _no_weight_addr = a1
                else:
                    a2 = fspy.aob_scan("0F 57 F6 90 90 7C CB 4C 8D 5C 24 70")
                    if a2 != 0:
                        _no_weight_addr = a2

            if _no_weight_addr:
                patch = [0x0F, 0x57, 0xF6, 0x90, 0x90] if enabled else [0xFF, 0xC3, 0x83, 0xFB, 0x05]
                if fspy.patch_memory(_no_weight_addr, patch):
                    return {"success": True}
                return {"success": False, "message": "sys_no_weight_failed"}
            return {"success": False, "message": "sys_no_weight_no_sig"}

        native_cheats = {"noDead": 0, "noDamage": 1, "noFP": 2, "noStamina": 3, "noGoods": 0}

        if cheat_name == "noHit":
            if hasattr(fspy, "toggle_no_hit") and fspy.toggle_no_hit(enabled):
                return {"success": True}
            return {"success": False}

        if cheat_name in native_cheats:
            if getattr(fspy, "get_main_player_ptr", None) is None:
                return {
                    "success": False,
                    "message": "sys_native_cheats_unsupported",
                }

            player_ptr = fspy.get_main_player_ptr()
            if player_ptr == 0:
                return {"success": False, "message": "sys_player_not_fully_loaded"}

            def apply_bit_flag(target_ptr):
                cur = fspy.read_u8(target_ptr)
                bit = native_cheats[cheat_name]
                nxt = (cur | (1 << bit)) if enabled else (cur & ~(1 << bit))
                if nxt != cur:
                    fspy.write_u8(target_ptr, nxt)

            if cheat_name in ["noDead", "noDamage", "noFP", "noStamina"]:
                base_flags_ptr = fspy.read_ptr(player_ptr + 0x190)
                if base_flags_ptr != 0:
                    base_flags = fspy.read_ptr(base_flags_ptr + 0x0)
                    if base_flags != 0:
                        apply_bit_flag(base_flags + 0x19B)
                        return {"success": True}
            elif cheat_name == "noGoods":
                apply_bit_flag(player_ptr + 0x532)
                return {"success": True}
            return {"success": False, "message": f"Failed to set {cheat_name} (pointers unresolved)"}

        # Fallbacks to DbgFlags for remaining like noArrow
        dbg = fspy.PyWorldChrManDbgFlags.get_instance()
        if dbg is None or getattr(dbg, "is_null", True):
            return {"success": False, "message": "sys_debug_flags_not_loaded"}

        mapping = {"noArrow": "all_no_arrow_consume"}
        if cheat_name in mapping:
            setattr(dbg, mapping[cheat_name], enabled)
            return {"success": True}
        else:
            return {"success": False, "message": "sys_unknown_cheat"}
    except Exception as e:
        return {"success": False, "message": str(e)}
