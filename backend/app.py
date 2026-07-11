import glob
import io
import json
import os
import sys

from flask import Flask, jsonify, render_template, request, send_file

from backend.tabs.backup_tab import backup_bp
from backend.tabs.build_tab import apply_build, get_build_data, inspect_saved_build
from backend.tabs.inventory_tab import inventory_bp
from backend.tabs.main_tab import get_player_data, get_recent_build_snapshot, perform_game_action
from backend.utils.config import read_language, set_language
from backend.utils.item_catalog import lookup
from backend.utils.items import ItemAssetService

base_dir = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
app = Flask(
    __name__, template_folder=os.path.join(base_dir, "templates"), static_folder=os.path.join(base_dir, "static")
)


def get_dll_base_dir():
    import os

    return getattr(sys, "fspy_base_dir", os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/stats")
def stats():
    data = get_player_data()
    if not isinstance(data, dict):
        data = {"loaded": False}

    try:
        return jsonify(data)
    except Exception as e:
        return jsonify({"loaded": False, "error": str(e)})


@app.route("/api/build")
def build():
    steam_id = request.args.get("steam_id", default=0, type=int)
    player_index = request.args.get("player_index", default=-1, type=int)
    return jsonify(get_build_data(steam_id or None, player_index if player_index >= 0 else None))


@app.route("/api/build/apply", methods=["POST"])
def build_apply():
    return jsonify(apply_build(request.get_json(silent=True) or {}))


@app.route("/api/build/inspect", methods=["POST"])
def build_inspect():
    return jsonify(inspect_saved_build(request.get_json(silent=True) or {}))


@app.route("/api/build/recent/<int:steam_id>")
def build_recent(steam_id):
    return jsonify(get_recent_build_snapshot(steam_id))


@app.route("/api/builds/list")
def list_builds():
    builds_dir = os.path.join(get_dll_base_dir(), "builds")
    os.makedirs(builds_dir, exist_ok=True)
    files = glob.glob(os.path.join(builds_dir, "*.json"))
    builds = [os.path.basename(f) for f in files]
    return jsonify({"builds": builds})


@app.route("/api/builds/load/<name>")
def load_build_file(name):
    builds_dir = os.path.join(get_dll_base_dir(), "builds")
    # Sanitize name
    name = os.path.basename(name)
    file_path = os.path.join(builds_dir, name)
    if not os.path.exists(file_path):
        return jsonify({"success": False, "message": "sys_file_not_found"}), 404
    try:
        with open(file_path, encoding="utf-8") as f:
            data = json.load(f)
        return jsonify(inspect_saved_build(data))
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


@app.route("/api/builds/save", methods=["POST"])
def save_build_file_api():
    payload = request.get_json(silent=True) or {}
    name = payload.get("name", "phantom-build.json")
    if not name.endswith(".json"):
        name += ".json"

    # Sanitize name
    name = os.path.basename(name)

    builds_dir = os.path.join(get_dll_base_dir(), "builds")
    os.makedirs(builds_dir, exist_ok=True)
    file_path = os.path.join(builds_dir, name)

    try:
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(payload.get("data", {}), f, indent=2)
        return jsonify({"success": True, "message": f"Saved as {name}"})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


@app.route("/api/items/search")
def item_search():
    service = ItemAssetService()
    limit = request.args.get("limit", default=50, type=int)
    return jsonify(
        {
            "items": service.search_items(
                q=request.args.get("q", ""),
                slot=request.args.get("slot") or None,
                csv_name=request.args.get("csv") or None,
                category=request.args.get("category") or None,
                equip_only=request.args.get("equip_only", "1") not in {"0", "false", "False"},
                limit=max(1, min(limit, 1000)),
            )
        }
    )


@app.route("/api/items/categories")
def item_categories():
    service = ItemAssetService()
    slot = request.args.get("slot", "")
    csv_name = request.args.get("csv", "")
    all_cats = request.args.get("all", "0")

    if all_cats == "1":
        categories = set()
        categories.update(service.get_distinct_categories("EquipParamWeapon.csv", "wep_type"))
        categories.update(service.get_distinct_categories("EquipParamProtector.csv", "protect_category"))
        categories.update(service.get_distinct_categories("EquipParamAccessory.csv", "accessory_category"))
        categories.update(service.get_distinct_categories("EquipParamGoods.csv", "goods_type"))
        categories.add("Gesture")  # Ensure Gestures always show up in the filter
        return jsonify({"categories": sorted(categories)})

    if slot:
        return jsonify({"categories": service.get_slot_categories(slot)})
    if csv_name:
        resolved = lookup(csv_name)
        column = resolved[1] if resolved else ("goods_type" if csv_name == "EquipParamGoods.csv" else "category")
        return jsonify({"categories": service.get_distinct_categories(csv_name, column)})
    return jsonify({"categories": []})


@app.route("/api/items/enrich/weapon")
def enrich_weapon():
    item_id = request.args.get("id", default=0, type=int)
    return jsonify({"item": ItemAssetService().enrich_weapon(item_id)})


@app.route("/api/items/enrich/goods")
def enrich_goods():
    item_id = request.args.get("id", default=0, type=int)
    return jsonify({"item": ItemAssetService().enrich_goods(item_id)})


@app.route("/api/icons/<icon_id>")
def item_icon(icon_id):
    found = ItemAssetService().read_icon(icon_id)
    if found is None:
        return ("", 404)
    data, mimetype = found
    return send_file(io.BytesIO(data), mimetype=mimetype, max_age=86400)


@app.route("/api/action/<action_type>", methods=["POST"])
def perform_action(action_type):
    result = perform_game_action(action_type)
    return jsonify(result)


@app.route("/api/cheats/toggle", methods=["POST"])
def toggle_cheat_route():
    data = request.json
    cheat = data.get("cheat")
    enabled = data.get("enabled")
    if not cheat or enabled is None:
        return jsonify({"success": False, "message": "sys_invalid_payload"})

    from backend.tabs.cheats_tab import toggle_cheat

    res = toggle_cheat(cheat, enabled)
    return jsonify(res)


app.register_blueprint(backup_bp)
app.register_blueprint(inventory_bp)


@app.route("/api/settings/language", methods=["GET"])
def get_language():
    return jsonify({"language": read_language()})


@app.route("/api/settings/language", methods=["POST"])
def update_language():
    data = request.json
    lang = data.get("language")
    if lang:
        set_language(lang)
        return jsonify({"success": True})
    return jsonify({"success": False, "message": "sys_no_language"})


@app.route("/api/locales")
def list_locales():
    import json

    from backend.utils.config import get_base_dir

    locales_dir = os.path.join(get_base_dir(), "static", "local")
    if not os.path.exists(locales_dir):
        return jsonify({"locales": [{"code": "en", "name": "English"}]})
    locales = []
    has_en = False
    for f in os.listdir(locales_dir):
        if f.endswith(".json"):
            code = f.replace(".json", "")
            if code == "en":
                has_en = True
            name = code.upper()
            try:
                with open(os.path.join(locales_dir, f), encoding="utf-8") as jf:
                    data = json.load(jf)
                    name = data.get("app_lang_name", name)
            except Exception:
                pass
            locales.append({"code": code, "name": name})
    if not has_en:
        locales.append({"code": "en", "name": "English"})

    # Optional sorting by code
    locales = sorted(locales, key=lambda x: x["code"])
    return jsonify({"locales": locales})


@app.route("/static/local/<path:filename>")
def serve_external_local(filename):
    from flask import send_from_directory

    from backend.utils.config import get_base_dir

    local_dir = os.path.join(get_base_dir(), "static", "local")
    return send_from_directory(local_dir, filename)


@app.route("/error_log/<path:msg>")
def handle_error_log(msg):
    print(f"Frontend JS Log: {msg}")
    return jsonify({"success": True})


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
