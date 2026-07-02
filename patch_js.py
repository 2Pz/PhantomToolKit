import os

build_path = os.path.join("static", "js", "tabs", "build_tab.js")
with open(build_path, encoding="utf-8") as f:
    text = f.read()

replacements = {
    "'Waiting for game load...'": "window.t('build_waiting', 'Waiting for game load...')",
    ">Confirm & Equip<": ">${window.t('build_confirm', 'Confirm & Equip')}<",
    ">Dismiss<": ">${window.t('build_dismiss', 'Dismiss')}<",
    ">Customize Weapon<": ">${window.t('build_customize', 'Customize Weapon')}<",
    ">Select Slot<": ">${window.t('build_select_slot_title', 'Select Slot')}<",
    ">Status<": ">${window.t('build_status', 'Status')}<",
    ">Ready<": ">${window.t('build_ready', 'Ready')}<",
    ">ID<": ">${window.t('build_id', 'ID')}<",
    ">Category<": ">${window.t('build_category', 'Category')}<",
    ">Ash of War<": ">${window.t('build_aow', 'Ash of War')}<",
    ">None<": ">${window.t('build_none', 'None')}<",
    "Selected: ": "${window.t('build_selected', 'Selected:')} ",
    ">Affinity<": ">${window.t('build_affinity', 'Affinity')}<",
    "Upgrade +": "${window.t('build_upgrade', 'Upgrade +')}",
    "Spirit Upgrade": "${window.t('build_spirit_upg', 'Spirit Upgrade')}",
    "Quantity ": "${window.t('build_quantity', 'Quantity')} ",
    "'KEEP'": "window.t('build_keep', 'KEEP')",
    ">No item equipped. Use search below to choose one.<": ">${window.t('build_no_equip', 'No item equipped. Use search below to choose one.')}<",
}

for old, new in replacements.items():
    text = text.replace(old, new)

with open(build_path, "w", encoding="utf-8") as f:
    f.write(text)

main_path = os.path.join("static", "js", "tabs", "main_tab.js")
with open(main_path, encoding="utf-8") as f:
    text = f.read()

text = text.replace(
    ">No recent players tracked yet.<", ">${window.t('main_no_recent_players', 'No recent players tracked yet.')}<"
)

with open(main_path, "w", encoding="utf-8") as f:
    f.write(text)

print("Patched JS files!")
