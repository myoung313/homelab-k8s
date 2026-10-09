"""Avatars and dungeon rooms for the Mission Control map (/office)."""

# Agents pick one of these for themselves (choose_avatar tool); the roster can override.
CATALOG = {
    "wizard": ("🧙", "Wizard"),
    "elf-ranger": ("🧝", "Elf Ranger"),
    "ninja": ("🥷", "Ninja"),
    "vampire": ("🧛", "Vampire"),
    "genie": ("🧞", "Genie"),
    "fairy": ("🧚", "Fairy"),
    "merfolk": ("🧜", "Merfolk"),
    "paladin": ("🦸", "Paladin"),
    "shadow-mage": ("🦹", "Shadow Mage"),
    "detective": ("🕵️", "Detective"),
    "king": ("🤴", "King"),
    "queen": ("👸", "Queen"),
    "zombie": ("🧟", "Zombie"),
    "troll": ("🧌", "Troll"),
    "golem": ("🤖", "Golem"),
    "skeleton": ("💀", "Skeleton"),
    "ghost": ("👻", "Ghost"),
    "dragon": ("🐉", "Dragon"),
    "owl": ("🦉", "Owl"),
    "fox": ("🦊", "Fox"),
    "wolf": ("🐺", "Wolf"),
    "black-cat": ("🐈‍⬛", "Black Cat"),
    "frog": ("🐸", "Frog"),
    "unicorn": ("🦄", "Unicorn"),
}
RECRUIT = ("🧑", "Recruit (no avatar yet)")

# (dept id, room name, grid column, grid row). Command sits in the middle.
ROOMS = [
    ("intel", "Scrying Tower", 0, 0),
    ("sales", "Merchant Guild", 1, 0),
    ("content", "Bards' Hall", 2, 0),
    ("delivery", "The Forge", 0, 1),
    ("command", "Throne Room", 1, 1),
    ("success", "Healers' Sanctum", 2, 1),
    ("products", "Alchemy Lab", 0, 2),
    ("finance", "Treasury", 1, 2),
    ("platform", "Warden's Keep", 2, 2),
]
