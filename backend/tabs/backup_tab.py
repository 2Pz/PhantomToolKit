import ast
import configparser
import contextlib
import io
import json
import os
import shutil
import threading
import time
import zipfile
from datetime import datetime

from flask import Blueprint, jsonify, request

backup_bp = Blueprint("backup", __name__, url_prefix="/api/backup")

auto_backup_thread = None
auto_backup_running = False


def get_base_dir():
    import sys

    return getattr(sys, "fspy_base_dir", os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


def get_settings_path():
    return os.path.join(get_base_dir(), "phantomtoolkit.ini")


def get_default_settings():
    return {
        "save_directory": "",
        "backup_directory": os.path.join(get_base_dir(), "backups"),
        "save_file_type": ".sl2",
        "save_file_name": "",
        "backup_method": 0,
        "auto_backup_interval": 5,
        "sleep_between_saves": 1,
        "max_backups": 20,
        "quit_to_menu_before_load": False,
        "notification_volume": 50,
        "keybind_save": "",
        "keybind_load": "",
        "keybind_auto_start": "",
        "keybind_auto_stop": "",
    }


def read_settings():
    path = get_settings_path()
    settings = get_default_settings()
    if os.path.exists(path):
        try:
            config = configparser.ConfigParser()
            config.read(path, encoding="utf-8")
            if "Backup" in config:
                loaded = dict(config["Backup"])
                for k, v in loaded.items():
                    if k in [
                        "backup_method",
                        "auto_backup_interval",
                        "sleep_between_saves",
                        "max_backups",
                        "notification_volume",
                    ]:
                        settings[k] = int(v)
                    elif k in ["quit_to_menu_before_load"]:
                        settings[k] = v.lower() == "true"
                    elif k.endswith("_vks"):
                        try:
                            settings[k] = ast.literal_eval(v)
                        except Exception:
                            settings[k] = []
                    else:
                        settings[k] = v
        except Exception:
            pass
    return settings


def write_settings(settings):
    path = get_settings_path()
    config = configparser.ConfigParser()
    if os.path.exists(path):
        config.read(path, encoding="utf-8")
    if "Backup" not in config:
        config["Backup"] = {}
    for k, v in settings.items():
        if isinstance(v, bool):
            config["Backup"][k] = "true" if v else "false"
        else:
            config["Backup"][k] = str(v)
    with open(path, "w", encoding="utf-8") as f:
        config.write(f)


@backup_bp.route("/settings", methods=["GET"])
def get_settings():
    return jsonify(read_settings())


@backup_bp.route("/settings", methods=["POST"])
def save_settings():
    new_settings = request.get_json(silent=True) or {}
    settings = read_settings()
    settings.update(new_settings)
    write_settings(settings)
    return jsonify({"success": True})


@backup_bp.route("/auto-find", methods=["GET"])
def auto_find():
    paths = []
    search_dirs = []

    appdata = os.environ.get("APPDATA", "")
    if appdata:
        search_dirs.append(os.path.join(appdata, "EldenRing"))

    home = os.path.expanduser("~")
    search_dirs.extend(
        [
            os.path.join(
                home, ".steam/steam/steamapps/compatdata/1245620/pfx/drive_c/users/steamuser/AppData/Roaming/EldenRing"
            ),
            os.path.join(
                home,
                ".local/share/Steam/steamapps/compatdata/1245620/pfx/drive_c/users/steamuser/AppData/Roaming/EldenRing",
            ),
        ]
    )

    for elden_ring_path in search_dirs:
        if os.path.exists(elden_ring_path):
            for d in os.listdir(elden_ring_path):
                dir_path = os.path.join(elden_ring_path, d)
                if os.path.isdir(dir_path) and len(d) == 17 and d.isdigit():
                    paths.append({"path": dir_path, "game": "ELDEN_RING", "steam_id": d})
    return jsonify({"paths": paths})


@backup_bp.route("/save-files", methods=["GET"])
def list_save_files():
    save_dir = request.args.get("save_dir", "")
    ext = request.args.get("ext", ".sl2")
    if not os.path.isdir(save_dir):
        return jsonify({"files": []})
    files = [f for f in os.listdir(save_dir) if f.endswith(ext) or ext == "*"]
    return jsonify({"files": files})


def get_pinned_list(backup_dir):
    pinned_path = os.path.join(backup_dir, "pinned.json")
    if os.path.exists(pinned_path):
        with contextlib.suppress(Exception), open(pinned_path, encoding="utf-8") as f:
            return json.load(f)
    return []


def set_pinned_list(backup_dir, pinned):
    pinned_path = os.path.join(backup_dir, "pinned.json")
    os.makedirs(backup_dir, exist_ok=True)
    with open(pinned_path, "w", encoding="utf-8") as f:
        json.dump(pinned, f, indent=4)


def _get_backup_paths(settings):
    save_dir = settings.get("save_directory")
    save_file = settings.get("save_file_name")
    backup_dir = settings.get("backup_directory") or os.path.join(get_base_dir(), "backups")
    return save_dir, save_file, backup_dir


def _request_fspy_save(settings):
    try:
        import fspy

        gm = fspy.PyGameMan.get_instance()
        if gm and not gm.is_null:
            gm.save_requested = True
        time.sleep(settings.get("sleep_between_saves", 1))
    except Exception as e:
        print("Failed to request save from game:", e)


def _update_pinned_and_return(backup_dir, pinned):
    set_pinned_list(backup_dir, pinned)
    return jsonify({"success": True})


def capture_screenshot_mss():
    try:
        import mss

        with mss.mss() as sct:
            sct_img = sct.grab(sct.monitors[1])

            try:
                import io

                from PIL import Image

                pil_img = Image.frombytes("RGB", sct_img.size, sct_img.rgb)
                pil_img = pil_img.resize((320, 180), Image.LANCZOS)

                img_byte_arr = io.BytesIO()
                pil_img.save(img_byte_arr, format="PNG")
                return img_byte_arr.getvalue(), "screenshot.png"
            except ImportError:
                return mss.tools.to_png(sct_img.rgb, sct_img.size), "screenshot.png"
    except Exception as e:
        print("Screenshot error:", e)
        return None, None


@backup_bp.route("/screenshot/<name>", methods=["GET"])
def get_screenshot(name):
    settings = read_settings()
    backup_dir = settings.get("backup_directory") or os.path.join(get_base_dir(), "backups")
    path = os.path.join(backup_dir, name)
    if os.path.exists(path) and path.endswith(".zip"):
        import contextlib
        import io
        import zipfile

        with contextlib.suppress(Exception), zipfile.ZipFile(path, "r") as zf:
            if "screenshot.jpg" in zf.namelist():
                from flask import send_file

                return send_file(io.BytesIO(zf.read("screenshot.jpg")), mimetype="image/jpeg")
            elif "screenshot.png" in zf.namelist():
                from flask import send_file

                return send_file(io.BytesIO(zf.read("screenshot.png")), mimetype="image/png")
    return "", 404


@backup_bp.route("/list", methods=["GET"])
def list_backups():
    settings = read_settings()
    backup_dir = settings.get("backup_directory") or os.path.join(get_base_dir(), "backups")
    os.makedirs(backup_dir, exist_ok=True)

    pinned_names = get_pinned_list(backup_dir)
    pinned = []
    regular = []

    for f in sorted(os.listdir(backup_dir), reverse=True):
        if f.endswith(".zip") or f.endswith(".sl2"):
            path = os.path.join(backup_dir, f)
            mtime = os.path.getmtime(path)
            date_str = datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M:%S")

            has_screenshot = False
            source_files = ""
            if f.endswith(".zip"):
                with contextlib.suppress(Exception), zipfile.ZipFile(path, "r") as zf:
                    names = zf.namelist()
                    has_screenshot = "screenshot.png" in names or "screenshot.jpg" in names
                    source_files = ", ".join(n for n in names if n != "screenshot.png" and n != "screenshot.jpg")

            entry = {
                "name": f,
                "path": path,
                "date": date_str,
                "hasScreenshot": has_screenshot,
                "sourceFiles": source_files,
                "isPinned": f in pinned_names,
            }
            if f in pinned_names:
                pinned.append(entry)
            else:
                regular.append(entry)

    return jsonify({"pinned": pinned, "regular": sorted(regular, key=lambda x: x["date"], reverse=True)})


def play_notification(name):
    settings = read_settings()
    volume = settings.get("notification_volume", 50)
    if volume == 0:
        return

    import os
    import struct
    import sys
    import threading
    import wave
    import winsound

    base = getattr(sys, "fspy_base_dir", os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    path = os.path.join(base, "notifications", f"{name}.wav")
    if not os.path.exists(path):
        path = os.path.join(base, "dist", "notifications", f"{name}.wav")

    if not os.path.exists(path):
        return

    if volume >= 100:
        winsound.PlaySound(path, winsound.SND_FILENAME | winsound.SND_ASYNC | winsound.SND_NODEFAULT)
        return

    def _play_vol():
        try:
            with wave.open(path, "rb") as w:
                p = w.getparams()
                frames = w.readframes(w.getnframes())
            if p.sampwidth == 2:
                fmt = f"<{len(frames) // 2}h"
                scaled = [max(min(int(s * (volume / 100.0)), 32767), -32768) for s in struct.unpack(fmt, frames)]
                frames = struct.pack(fmt, *scaled)
            out = io.BytesIO()
            with wave.open(out, "wb") as w:
                w.setparams(p)
                w.writeframes(frames)
            winsound.PlaySound(out.getvalue(), winsound.SND_MEMORY | winsound.SND_NODEFAULT)
        except Exception:
            pass

    threading.Thread(target=_play_vol, daemon=True).start()


def do_create_backup():
    settings = read_settings()
    save_dir, save_file, backup_dir = _get_backup_paths(settings)

    if not save_dir or not save_file:
        return None

    src_path = os.path.join(save_dir, save_file)
    if not os.path.exists(src_path):
        return None

    os.makedirs(backup_dir, exist_ok=True)
    _request_fspy_save(settings)

    screenshot_bytes, ext = capture_screenshot_mss()

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_name = f"backup_{timestamp}.zip"
    dst_path = os.path.join(backup_dir, backup_name)

    with zipfile.ZipFile(dst_path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.write(src_path, arcname=save_file)
        if screenshot_bytes:
            zf.writestr(ext, screenshot_bytes)

    max_backups = settings.get("max_backups", 20)
    pinned_names = get_pinned_list(backup_dir)
    all_backups = sorted(
        [f for f in os.listdir(backup_dir) if (f.endswith(".sl2") or f.endswith(".zip")) and f not in pinned_names],
        key=lambda x: os.path.getmtime(os.path.join(backup_dir, x)),
        reverse=True,
    )

    if len(all_backups) > max_backups:
        for old in all_backups[max_backups:]:
            with contextlib.suppress(Exception):
                os.remove(os.path.join(backup_dir, old))

    play_notification("save_notification")
    return backup_name


@backup_bp.route("/create", methods=["POST"])
def create_backup():
    name = do_create_backup()
    if not name:
        return jsonify({"detail": "Failed to create backup"}), 400
    return jsonify({"name": name, "success": True})


def _restore_file(src_path, dst_path, settings):
    if settings.get("quit_to_menu_before_load"):
        with contextlib.suppress(Exception):
            import fspy

            gm = fspy.PyGameMan.get_instance()
            if gm and not gm.is_null:
                gm.unk8 = 1
                gm.warp_requested = True
                gm.save_requested = True
            time.sleep(1.5)

    if src_path.endswith(".zip"):
        with zipfile.ZipFile(src_path, "r") as zf:
            members = [m for m in zf.namelist() if m != "screenshot.png"]
            if members:
                with zf.open(members[0]) as source, open(dst_path, "wb") as target:
                    shutil.copyfileobj(source, target)
    else:
        shutil.copy2(src_path, dst_path)

    play_notification("load_notification")


def do_restore_latest():
    settings = read_settings()
    save_dir, save_file, backup_dir = _get_backup_paths(settings)
    if not save_dir or not save_file:
        return

    backups = []
    if os.path.exists(backup_dir):
        for f in os.listdir(backup_dir):
            if f.endswith(".zip") or f.endswith(".sl2"):
                backups.append(f)
    if not backups:
        return

    backups.sort(key=lambda x: os.path.getmtime(os.path.join(backup_dir, x)), reverse=True)
    latest = backups[0]

    src_path = os.path.join(backup_dir, latest)
    dst_path = os.path.join(save_dir, save_file)
    _restore_file(src_path, dst_path, settings)


@backup_bp.route("/load", methods=["POST"])
def load_backup():
    name = request.args.get("name")
    if not name:
        return jsonify({"detail": "No backup name provided"}), 400

    settings = read_settings()
    save_dir, save_file, backup_dir = _get_backup_paths(settings)

    src_path = os.path.join(backup_dir, name)
    dst_path = os.path.join(save_dir, save_file)

    if not os.path.exists(src_path):
        return jsonify({"detail": "Backup not found"}), 404

    _restore_file(src_path, dst_path, settings)
    return jsonify({"success": True})


@backup_bp.route("/<name>", methods=["DELETE"])
def delete_backup(name):
    settings = read_settings()
    backup_dir = settings.get("backup_directory") or os.path.join(get_base_dir(), "backups")
    path = os.path.join(backup_dir, name)
    if os.path.exists(path):
        os.remove(path)

    pinned = get_pinned_list(backup_dir)
    if name in pinned:
        pinned.remove(name)
        return _update_pinned_and_return(backup_dir, pinned)

    return jsonify({"success": True})


@backup_bp.route("/pin/<name>", methods=["POST"])
def pin_backup(name):
    settings = read_settings()
    backup_dir = settings.get("backup_directory") or os.path.join(get_base_dir(), "backups")
    req_data = request.get_json(silent=True) or {}
    pin = req_data.get("pin", True)

    pinned = get_pinned_list(backup_dir)
    if pin and name not in pinned:
        pinned.append(name)
    elif not pin and name in pinned:
        pinned.remove(name)

    return _update_pinned_and_return(backup_dir, pinned)


@backup_bp.route("/rename", methods=["POST"])
def rename_backup():
    settings = read_settings()
    backup_dir = settings.get("backup_directory") or os.path.join(get_base_dir(), "backups")
    req_data = request.get_json(silent=True) or {}
    old_name = req_data.get("oldName")
    new_name = req_data.get("newName")

    if not new_name.endswith(".sl2") and not new_name.endswith(".zip"):
        new_name += ".sl2" if old_name.endswith(".sl2") else ".zip"

    old_path = os.path.join(backup_dir, old_name)
    new_path = os.path.join(backup_dir, new_name)

    if os.path.exists(old_path):
        os.rename(old_path, new_path)
        pinned = get_pinned_list(backup_dir)
        if old_name in pinned:
            pinned.remove(old_name)
            pinned.append(new_name)
            return _update_pinned_and_return(backup_dir, pinned)

    return jsonify({"success": True})


def auto_backup_worker():
    global auto_backup_running
    while auto_backup_running:
        settings = read_settings()
        interval = settings.get("auto_backup_interval", 5) * 60
        for _ in range(int(interval)):
            if not auto_backup_running:
                break
            time.sleep(1)

        if auto_backup_running:
            try:
                save_dir, save_file, backup_dir = _get_backup_paths(settings)
                if save_dir and save_file and os.path.exists(os.path.join(save_dir, save_file)):
                    _request_fspy_save(settings)
                    screenshot_bytes, ext = capture_screenshot_mss()

                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    backup_name = f"autobackup_{timestamp}.zip"
                    dst_path = os.path.join(backup_dir, backup_name)

                    with zipfile.ZipFile(dst_path, "w", zipfile.ZIP_DEFLATED) as zf:
                        zf.write(os.path.join(save_dir, save_file), arcname=save_file)
                        if screenshot_bytes:
                            zf.writestr(ext, screenshot_bytes)
            except Exception as e:
                print("Auto-backup failed:", e)


def start_auto_worker():
    global auto_backup_running, auto_backup_thread
    if not auto_backup_running:
        auto_backup_running = True
        play_notification("start_auto_save_notification")
        auto_backup_thread = threading.Thread(target=auto_backup_worker, daemon=True)
        auto_backup_thread.start()


def stop_auto_worker():
    global auto_backup_running
    if auto_backup_running:
        auto_backup_running = False
        play_notification("stop_auto_save_notification")


@backup_bp.route("/auto/start", methods=["POST"])
def start_auto():
    start_auto_worker()
    return jsonify({"success": True})


@backup_bp.route("/auto/stop", methods=["POST"])
def stop_auto():
    stop_auto_worker()
    return jsonify({"success": True})


@backup_bp.route("/auto/status", methods=["GET"])
def auto_status():
    global auto_backup_running
    return jsonify({"running": auto_backup_running})


@backup_bp.route("/active", methods=["POST"])
def active_backup():
    return jsonify({"success": True})


@backup_bp.route("/api/fs/list", methods=["POST"])
def fs_list():
    data = request.get_json(silent=True) or {}
    path = data.get("path", "")

    try:
        import string

        # If path is empty, return drives
        if not path:
            drives = []
            if os.name == "nt":
                import ctypes

                bitmask = ctypes.windll.kernel32.GetLogicalDrives()
                for letter in string.ascii_uppercase:
                    if bitmask & 1:
                        drives.append(f"{letter}:\\")
                    bitmask >>= 1
            else:
                drives = ["/"]

            return jsonify({"drives": drives, "folders": [], "current": ""})

        path = os.path.normpath(path)
        if os.name == "nt" and len(path) == 2 and path[1] == ":":
            path += "\\"

        folders = []
        if os.path.exists(path) and os.path.isdir(path):
            try:
                for d in os.listdir(path):
                    full_path = os.path.join(path, d)
                    if os.path.isdir(full_path):
                        is_hidden = d.startswith(".")
                        if os.name == "nt":
                            try:
                                import ctypes

                                attrs = ctypes.windll.kernel32.GetFileAttributesW(str(full_path))
                                if attrs != -1 and (attrs & 2):  # FILE_ATTRIBUTE_HIDDEN
                                    is_hidden = True
                            except Exception:
                                pass
                        folders.append({"name": d, "path": full_path, "hidden": is_hidden})
            except PermissionError:
                pass

        folders.sort(key=lambda x: x["name"].lower())

        parent = os.path.dirname(path)
        if parent == path:
            parent = ""

        return jsonify({"drives": [], "folders": folders, "current": path, "parent": parent})
    except Exception as e:
        print("FS List error:", e)
        return jsonify({"error": str(e), "current": path, "parent": os.path.dirname(path), "folders": []})


def get_async_key_state(vk):
    import ctypes

    return (ctypes.windll.user32.GetAsyncKeyState(vk) & 0x8000) != 0


VK_MAP_FALLBACK = {
    "ctrl": 0x11,
    "shift": 0x10,
    "alt": 0x12,
    "f1": 0x70,
    "f2": 0x71,
    "f3": 0x72,
    "f4": 0x73,
    "f5": 0x74,
    "f6": 0x75,
    "f7": 0x76,
    "f8": 0x77,
    "f9": 0x78,
    "f10": 0x79,
    "f11": 0x7A,
    "f12": 0x7B,
    "space": 0x20,
    "enter": 0x0D,
    "tab": 0x09,
    "esc": 0x1B,
    "escape": 0x1B,
    "backspace": 0x08,
    "up": 0x26,
    "arrowup": 0x26,
    "down": 0x28,
    "arrowdown": 0x28,
    "left": 0x25,
    "arrowleft": 0x25,
    "right": 0x27,
    "arrowright": 0x27,
    "insert": 0x2D,
    "delete": 0x2E,
    "home": 0x24,
    "end": 0x23,
    "pageup": 0x21,
    "pagedown": 0x22,
    "capslock": 0x14,
    "scrolllock": 0x91,
    "numlock": 0x90,
    "pause": 0x13,
    "`": 0xC0,
    "-": 0xBD,
    "=": 0xBB,
    "[": 0xDB,
    "]": 0xDD,
    "\\": 0xDC,
    ";": 0xBA,
    "'": 0xDE,
    ",": 0xBC,
    ".": 0xBE,
    "/": 0xBF,
}
for c in "abcdefghijklmnopqrstuvwxyz":
    VK_MAP_FALLBACK[c] = ord(c.upper())
for c in "0123456789":
    VK_MAP_FALLBACK[c] = ord(c)


def get_vks(settings, key):
    # Try the new array format first
    vks = settings.get(f"{key}_vks", [])
    if isinstance(vks, list) and len(vks) > 0 and all(isinstance(x, int) for x in vks):
        return vks

    # Fallback to old string parsing if missing
    hotkey_str = settings.get(key, "")
    if not hotkey_str or hotkey_str == "NONE":
        return []
    parts = hotkey_str.lower().replace(" ", "").split("+")
    fb_vks = []
    for p in parts:
        if p in VK_MAP_FALLBACK:
            fb_vks.append(VK_MAP_FALLBACK[p])
        else:
            return []
    return fb_vks


def hotkey_poller():
    import builtins
    import uuid

    my_id = str(uuid.uuid4())
    builtins.__phantom_hotkey_poller_id = my_id

    last_state = {}
    while getattr(builtins, "__phantom_hotkey_poller_id", None) == my_id:
        try:
            settings = read_settings()
            binds = {
                "save": (get_vks(settings, "keybind_save"), do_create_backup),
                "load": (get_vks(settings, "keybind_load"), do_restore_latest),
                "start": (get_vks(settings, "keybind_auto_start"), start_auto_worker),
                "stop": (get_vks(settings, "keybind_auto_stop"), stop_auto_worker),
            }

            for name, (vks, action) in binds.items():
                if not vks:
                    continue
                pressed = all(get_async_key_state(vk) for vk in vks)
                was_pressed = last_state.get(name, False)
                if pressed and not was_pressed:
                    threading.Thread(target=action, daemon=True).start()
                last_state[name] = pressed
        except Exception:
            pass
        time.sleep(0.05)


def init_hotkeys():
    threading.Thread(target=hotkey_poller, daemon=True).start()


# Run once on load
init_hotkeys()
