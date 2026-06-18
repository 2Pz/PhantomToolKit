_no_weight_addr = None


def toggle_cheat(cheat_name: str, enabled: bool):
    try:
        import fspy

        global _no_weight_addr

        if cheat_name == "noWeight":
            if getattr(fspy, "aob_scan", None) is None:
                return {"success": False, "message": "No Weight not supported by this fspy version"}
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
                return {"success": False, "message": "Failed to patch memory for No Weight"}
            return {"success": False, "message": "No Weight signature not found"}

        native_cheats = {"noDead": 0, "noDamage": 1, "noFP": 2, "noStamina": 3, "noGoods": 0, "noHit": 3}
        if cheat_name in native_cheats:
            if getattr(fspy, "get_main_player_ptr", None) is None:
                return {
                    "success": False,
                    "message": "Native cheats not supported by fspy (missing get_main_player_ptr)",
                }

            player_ptr = fspy.get_main_player_ptr()
            if player_ptr == 0:
                return {"success": False, "message": "Player not fully loaded"}

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
            elif cheat_name == "noHit":
                apply_bit_flag(player_ptr + 0x530)
                return {"success": True}
            elif cheat_name == "noGoods":
                apply_bit_flag(player_ptr + 0x532)
                return {"success": True}
            return {"success": False, "message": f"Failed to set {cheat_name} (pointers unresolved)"}

        # Fallbacks to DbgFlags for remaining like noArrow
        dbg = fspy.PyWorldChrManDbgFlags.get_instance()
        if dbg is None or getattr(dbg, "is_null", True):
            return {"success": False, "message": "Game debug flags not loaded"}

        mapping = {"noArrow": "all_no_arrow_consume"}
        if cheat_name in mapping:
            setattr(dbg, mapping[cheat_name], enabled)
            return {"success": True}
        else:
            return {"success": False, "message": "Unknown or unsupported cheat"}
    except Exception as e:
        return {"success": False, "message": str(e)}
