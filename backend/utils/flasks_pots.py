from __future__ import annotations

from functools import lru_cache
from typing import Protocol


class _PotGroupsProto(Protocol):
    @classmethod
    def get_group_for_item(cls, item_id: int) -> int | None: ...

    @classmethod
    def get_group_items(cls, group_num: int) -> list[int]: ...

    @classmethod
    def is_pot(cls, item_id: int) -> bool: ...


class _BaseGroup:
    GROUP_1: list[int] = []
    GROUP_2: list[int] = []
    GROUP_3: list[int] = []
    GROUP_4: list[int] = []

    @classmethod
    def get_group_for_item(cls, item_id: int) -> int | None:
        if item_id in cls.GROUP_1:
            return 1
        if item_id in cls.GROUP_2:
            return 2
        if item_id in cls.GROUP_3:
            return 3
        if item_id in cls.GROUP_4:
            return 4
        return None

    @classmethod
    def get_group_items(cls, group_num: int) -> list[int]:
        if group_num == 1:
            return list(cls.GROUP_1)
        if group_num == 2:
            return list(cls.GROUP_2)
        if group_num == 3:
            return list(cls.GROUP_3)
        if group_num == 4:
            return list(cls.GROUP_4)
        return []


class _FallbackPotGroups(_BaseGroup):
    # Source of truth for Elden Ring item groups.
    GROUP_1 = [3500, 3510, 3520, 3550, 3580, 3610]
    GROUP_2 = [
        300,
        380,
        660,
        320,
        350,
        370,
        330,
        340,
        2000710,
        600,
        650,
        430,
        400,
        470,
        2000760,
        510,
        420,
        460,
        450,
        440,
        490,
        640,
    ]
    GROUP_3 = [301, 302, 661, 321, 2000700, 351, 670, 360, 2000740, 630, 390, 391, 610]
    GROUP_4 = [
        2000300,
        2000680,
        2000380,
        2000660,
        2000320,
        2000690,
        2000370,
        2000330,
        2000670,
        2000340,
        2000360,
        2000620,
        2000310,
        2000600,
        2000650,
    ]

    @classmethod
    def is_pot(cls, item_id: int) -> bool:
        return cls.get_group_for_item(item_id) is not None


@lru_cache(maxsize=1)
def get_pot_groups() -> type[_PotGroupsProto]:
    return _FallbackPotGroups


class _FallbackFlaskGroups(_BaseGroup):
    # Source of truth for DS3 item groups.
    GROUP_1 = list(range(150, 172))
    GROUP_2 = list(range(190, 212))

    @classmethod
    def is_flask(cls, item_id: int) -> bool:
        return cls.get_group_for_item(item_id) is not None


@lru_cache(maxsize=1)
def get_flask_groups() -> type[_PotGroupsProto]:
    return _FallbackFlaskGroups


class _FallbackERFlaskGroups(_BaseGroup):
    GROUP_1 = list(range(1000, 1026))
    GROUP_2 = list(range(1050, 1076))

    @classmethod
    def is_er_flask(cls, item_id: int) -> bool:
        return cls.get_group_for_item(item_id) is not None


@lru_cache(maxsize=1)
def get_er_flask_groups() -> type[_PotGroupsProto]:
    return _FallbackERFlaskGroups
