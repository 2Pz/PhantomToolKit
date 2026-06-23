from __future__ import annotations

import csv
import os
import unicodedata
import zipfile
from dataclasses import asdict, dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

from backend.utils.item_catalog import SENTINEL_IDS, csv_hints_for_slot, lookup

SPIRIT_SUMMON_CATEGORIES = frozenset({"Spirit Summon - Lesser", "Spirit Summon - Greater"})


@dataclass(frozen=True)
class ItemRow:
    id: int
    name: str
    normalized_name: str
    icon_id: str | None = None
    max_upgrade: int = 0
    category: str | None = None
    is_only_one: bool = False
    is_equip: bool = False
    max_num: int | None = None
    raw: dict[str, Any] | None = None


def normalize_text(text: str) -> str:
    if not text:
        return ""
    text = unicodedata.normalize("NFKC", text).casefold()
    return "".join(char for char in unicodedata.normalize("NFD", text) if unicodedata.category(char) != "Mn")


def item_to_dict(item: ItemRow | dict | None) -> dict | None:
    if item is None:
        return None
    out = dict(item) if isinstance(item, dict) else asdict(item)
    out.pop("normalized_name", None)
    out.pop("raw", None)
    return out


def _append_variants(result_list, base_item, item_group):
    variants = [{"id": item["id"], "name": item["name"]} for item in item_group if item["id"] != base_item["id"]]
    result_list.append({**base_item, "base_id": base_item["id"], "base_name": base_item["name"], "variants": variants})


def group_weapon_variants(items: list[dict]) -> list[dict]:
    weapon_items = [item for item in items if str(item.get("category", "")).lower() not in ("arrow", "bolt")]
    ammo_items = [item for item in items if str(item.get("category", "")).lower() in ("arrow", "bolt")]

    groups: dict[int, list[dict]] = {}
    for item in weapon_items:
        base_id = item["id"] - (item["id"] % 10000)
        groups.setdefault(base_id, []).append(item)

    result = list(ammo_items)
    for group in groups.values():
        group.sort(key=lambda item: item["id"])
        if len(group) == 1:
            result.append({**group[0], "variants": None})
            continue

        base = next((item for item in group if item["id"] % 10000 == 0), group[0])
        _append_variants(result, base, group)
    return result


def group_spirit_summons(items: list[dict], *, bases_only: bool = True) -> list[dict]:
    spirit_items = [item for item in items if item.get("category") in SPIRIT_SUMMON_CATEGORIES]
    other_items = [item for item in items if item.get("category") not in SPIRIT_SUMMON_CATEGORIES]

    groups: dict[int, list[dict]] = {}
    for item in spirit_items:
        base_id = item["id"] - (item["id"] % 1000)
        groups.setdefault(base_id, []).append(item)

    result = list(other_items)
    for group in groups.values():
        group.sort(key=lambda item: item["id"])
        base = next((item for item in group if item["id"] % 1000 == 0), group[0])
        if bases_only and base["id"] != min(item["id"] for item in group):
            base = min(group, key=lambda item: item["id"])
        _append_variants(result, base, group)
    return result


def expand_weapon_families(items: list[dict], all_items: list[dict]) -> list[dict]:
    family_ids = {
        item["id"] - (item["id"] % 10000)
        for item in items
        if str(item.get("category", "")).lower() not in ("arrow", "bolt")
    }
    if not family_ids:
        return items
    expanded = [item for item in all_items if item["id"] - (item["id"] % 10000) in family_ids]
    ammo = [item for item in items if str(item.get("category", "")).lower() in ("arrow", "bolt")]
    return [*ammo, *expanded]


def expand_spirit_families(items: list[dict], all_items: list[dict]) -> list[dict]:
    family_ids = {
        item["id"] - (item["id"] % 1000) for item in items if item.get("category") in SPIRIT_SUMMON_CATEGORIES
    }
    if not family_ids:
        return items
    expanded = [item for item in all_items if item["id"] - (item["id"] % 1000) in family_ids]
    others = [item for item in items if item.get("category") not in SPIRIT_SUMMON_CATEGORIES]
    return [*others, *expanded]


class ItemAssetService:
    def items_dir(self) -> Path:
        override = os.environ.get("PHANTOM_ITEMS_DIR", "").strip()
        if override:
            path = Path(override)
            if path.exists():
                return path

        import sys

        if hasattr(sys, "fspy_base_dir"):
            return Path(sys.fspy_base_dir) / "items"

        project_root = Path(__file__).resolve().parent.parent.parent
        return project_root / "items"

    def list_csv_files(self) -> list[str]:
        return sorted(path.name for path in self.items_dir().glob("*.csv"))

    def read_icon(self, icon_id: str) -> tuple[bytes, str] | None:
        if not icon_id:
            return None
        zip_path = self.items_dir() / "images.zip"
        if not zip_path.exists():
            zip_path = self.items_dir() / "Images.zip"
        if not zip_path.exists():
            return None

        with zipfile.ZipFile(zip_path, "r") as archive:
            target = _find_icon_entry(archive.namelist(), str(icon_id))
            if target is None:
                return None
            data = archive.read(target)
            suffix = Path(target).suffix.lower().lstrip(".") or "bin"
            mimetype = "image/webp" if suffix == "webp" else f"image/{suffix}"
            return data, mimetype

    def _load_csv(self, csv_name: str, language: str = "en") -> dict[int, ItemRow]:
        return _load_csv(self.items_dir() / csv_name, language)

    def get_distinct_categories(self, csv_name: str, column: str) -> list[str]:
        return list(_distinct_csv_values(self.items_dir() / csv_name, column))

    def get_slot_categories(self, slot: str) -> list[str]:
        resolved = lookup(slot)
        if resolved is None:
            return []
        csv_name, column, categories = resolved
        if categories is not None:
            return categories
        categories = self.get_distinct_categories(csv_name, column)
        if csv_name == "EquipParamWeapon.csv":
            return [category for category in categories if category.lower() not in ("arrow", "bolt")]
        return categories

    def find_item_any_csv(self, item_id: int, hints: list[str] | None = None, language: str = "en") -> ItemRow | None:
        if item_id in SENTINEL_IDS:
            return None

        raw_id = item_id & 0x0FFFFFFF
        candidates = hints or self.list_csv_files()
        for candidate_id in _candidate_ids(raw_id):
            for csv_name in candidates:
                table = self._load_csv(csv_name, language)
                if candidate_id in table:
                    return table[candidate_id]
        return None

    def enrich_slot_item(self, slot: str, value: Any) -> dict | None:
        payload = _coerce_item_payload(value)
        if payload is None:
            return None

        hints = csv_hints_for_slot(slot)
        item = None
        if _is_weapon_slot_name(slot):
            item = self.enrich_weapon(payload["id"])
        elif _is_goods_slot_name(slot):
            item = self.enrich_goods(payload["id"])
        item = item or item_to_dict(self.find_item_any_csv(payload["id"], hints=hints))
        if item is None:
            item = {
                "id": payload["id"],
                "name": f"Unknown [{payload['id']}]",
                "icon_id": None,
                "category": None,
                "max_upgrade": 0,
                "is_only_one": True,
                "is_equip": False,
                "max_num": 1,
            }
        item.update({key: value for key, value in payload.items() if key != "id"})
        item["id"] = payload["id"]
        return item

    def enrich_weapon(self, item_id: int, language: str = "en") -> dict | None:
        table = self._load_csv("EquipParamWeapon.csv", language)
        raw_id = item_id & 0x0FFFFFFF
        found_id = next((candidate for candidate in _candidate_ids(raw_id) if candidate in table), None)
        if found_id is None:
            return None
        target = table[found_id]
        if target.category and target.category.lower() in ("arrow", "bolt"):
            return item_to_dict(target)

        base_id = found_id - (found_id % 10000)
        rows = [item_to_dict(row) for row in table.values() if row.id - (row.id % 10000) == base_id]
        grouped = group_weapon_variants([row for row in rows if row is not None])
        return grouped[0] if grouped else item_to_dict(target)

    def enrich_goods(self, item_id: int, language: str = "en") -> dict | None:
        table = self._load_csv("EquipParamGoods.csv", language)
        raw_id = item_id & 0x0FFFFFFF
        if raw_id not in table:
            return None

        target = table[raw_id]
        if target.category not in SPIRIT_SUMMON_CATEGORIES:
            return item_to_dict(target)

        base_id = raw_id - (raw_id % 1000)
        rows = [item_to_dict(row) for row in table.values() if row.id - (row.id % 1000) == base_id]
        grouped = group_spirit_summons([row for row in rows if row is not None])
        if not grouped:
            return item_to_dict(target)
        enriched = grouped[0]
        if raw_id != enriched["id"]:
            enriched = {**enriched, "id": raw_id, "name": target.name, "icon_id": target.icon_id}
        return enriched

    def search_items(
        self,
        *,
        q: str = "",
        slot: str | None = None,
        csv_name: str | None = None,
        category: str | None = None,
        equip_only: bool = False,
        limit: int = 50,
    ) -> list[dict]:
        resolved_categories = None
        slot_info = lookup(slot) if slot else None
        if slot_info:
            csv_name = csv_name or slot_info[0]
        if category:
            resolved_categories = [category]
        elif slot_info:
            resolved_categories = slot_info[2]

        qn = normalize_text(q)
        sources = [csv_name] if csv_name else self.list_csv_files()
        hits: list[ItemRow] = []
        internal_limit = limit * 20 if csv_name in {"EquipParamWeapon.csv", "EquipParamGoods.csv"} else limit

        for source in sources:
            table = self._load_csv(source)
            for item in table.values():
                if (
                    resolved_categories
                    and "ALL" not in resolved_categories
                    and item.category not in resolved_categories
                ):
                    continue
                if equip_only and not _is_equippable(item):
                    continue
                if qn and qn not in item.normalized_name and qn not in str(item.id):
                    continue
                hits.append(item)
                if len(hits) >= internal_limit:
                    break
            if len(hits) >= internal_limit:
                break

        out = [item_to_dict(item) for item in hits]
        if csv_name == "EquipParamWeapon.csv":
            all_rows = [item_to_dict(item) for item in self._load_csv(csv_name).values()]
            out = expand_weapon_families(
                [item for item in out if item is not None], [item for item in all_rows if item is not None]
            )
            out = group_weapon_variants(out)
        elif csv_name == "EquipParamGoods.csv":
            all_rows = [item_to_dict(item) for item in self._load_csv(csv_name).values()]
            out = expand_spirit_families(
                [item for item in out if item is not None], [item for item in all_rows if item is not None]
            )
            out = group_spirit_summons(out)
        return [item for item in out if item is not None][:limit]


def _coerce_item_payload(value: Any) -> dict | None:
    if isinstance(value, dict):
        item_id = value.get("id")
        if item_id in SENTINEL_IDS or item_id is None:
            return None
        payload = dict(value)
        payload["id"] = int(item_id) & 0x0FFFFFFF
        return payload
    if value in SENTINEL_IDS or value is None:
        return None
    return {"id": int(value) & 0x0FFFFFFF}


def _is_weapon_slot_name(slot: str) -> bool:
    if slot.startswith("weapon_"):
        return True
    if slot.endswith("_wep"):
        return True
    return slot in {"primary_arrow", "secondary_arrow", "primary_bolt", "secondary_bolt"}


def _is_goods_slot_name(slot: str) -> bool:
    return (
        slot.startswith("quick_item_")
        or slot.startswith("magic_slot_")
        or slot.startswith("physick_tear_")
        or slot == "great_rune"
    )


def _candidate_ids(item_id: int) -> list[int]:
    candidates = [item_id]
    for divisor in (100, 10):
        normalized = item_id - (item_id % divisor)
        if normalized not in candidates:
            candidates.append(normalized)
    return candidates


def _is_equippable(item: ItemRow) -> bool:
    if not item.category:
        return False
    if item.category in {
        "Key Item",
        "Info Item",
        "Reinforcement Material",
        "Regenerative Material",
        "Crafting Material",
    }:
        return False
    return not (not item.is_equip and item.category in {"Normal Item", "Consumable"})


def _find_icon_entry(names: list[str], icon_id: str) -> str | None:
    stems = {Path(name).stem: name for name in names}
    for candidate in (icon_id, icon_id.zfill(5), f"MENU_Knowledge_{icon_id}", f"MENU_Knowledge_{icon_id.zfill(5)}"):
        if candidate in stems:
            return stems[candidate]
    for stem, name in stems.items():
        if stem.endswith(f"_{icon_id}") or stem.endswith(f"_{icon_id.zfill(5)}"):
            return name
    return None


@lru_cache(maxsize=32)
def _distinct_csv_values(path: Path, column: str) -> tuple[str, ...]:
    if not path.exists():
        return ()

    values: set[str] = set()
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        for row in csv.DictReader(file):
            value = row.get(column)
            if value:
                value = value.strip('" ')
                if value:
                    values.add(value)
    return tuple(sorted(values))


@lru_cache(maxsize=32)
def _load_csv(path: Path, language: str) -> dict[int, ItemRow]:
    if not path.exists():
        return {}

    out: dict[int, ItemRow] = {}
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        for row in csv.DictReader(file):
            raw_id = row.get("ID")
            if not raw_id or not str(raw_id).isdigit():
                continue

            item_id = int(raw_id)
            name = row.get(language) or row.get("en") or row.get("name") or str(item_id)
            category = row.get("category") or row.get("goods_type") or None
            if category:
                category = category.strip('" ')

            upgrade_type = row.get("Upgrade")
            max_upgrade = 0
            if upgrade_type == "Smithing Stones":
                max_upgrade = 25
            elif upgrade_type in {"Somber Smithing Stones", "Titanite"}:
                max_upgrade = 10
            elif upgrade_type in {"Twinkling Titanite", "Titanite Scale"}:
                max_upgrade = 5
            elif category and "Spirit Summon" in category:
                max_upgrade = 10

            raw_max = (row.get("maxNum") or "").replace('"', "").strip()
            max_num = int(raw_max) if raw_max.isdigit() else None
            if category and category.lower() in {"arrow", "bolt"}:
                max_num = 99

            out[item_id] = ItemRow(
                id=item_id,
                name=str(name),
                normalized_name=normalize_text(str(name)),
                icon_id=str(row.get("icon_id")) if row.get("icon_id") else None,
                max_upgrade=max_upgrade,
                category=category,
                is_only_one=(row.get("isOnlyOne", "0").replace('"', "").strip() == "1"),
                is_equip=(row.get("isEquip", "0").replace('"', "").strip() == "1"),
                max_num=max_num,
                raw=row,
            )
    return out
