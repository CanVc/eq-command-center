# Lucy RAW notes

Exploration rapide faite à partir de :

- item : <https://lucy.allakhazam.com/itemraw.html?id=10895>
- spell : <https://lucy.allakhazam.com/spellraw.html?id=1806&source=Live>

## Item 10895 — Fungus Covered Great Staff

Champs RAW utiles observés :

```text
id: 10895
name: Fungus Covered Great Staff
lore: Fungus Covered Great Staff
icon: 601
slots: 8192
classes: 49696
races: 65535
itemtype: 4
damage: 18
delay: 35
ac: 0
hp: 0
mana: 0
endur: 0
regen: 0
manaregen: 0
endurregen: 0
nodrop: 1
norent: 1
magic: 1
spellid0: 1806
effecttype0: 1
casttime0: 0
efflevel0: 0
```

Conclusion : les effets d'items ne devraient pas être stockés comme texte libre dans `items`.
Lucy expose plutôt une liste `spellid0..spellidN` + métadonnées associées.

## Spell 1806 — Fungal Regrowth

Champs RAW utiles observés :

```text
id: 1806
name: Fungal Regrowth
spelltype: Beneficial
targettype: Self
skill: Alteration
range: 100
duration: 50
durationformula: 9
recasttime: 0

Slot 1 description: Increase Hitpoints by 5 per tick. Max: 15 per tick
attrib1: 0
base1: 5
max1: 15
calc1: 101

Slot 2 description: Decrease Movement by 10% (L1) to 84% (L130)
attrib2: 3
base2: -10
max2: 90
calc2: 101
```

Conclusion : une table `spells` + une table `spell_effect_slots` est préférable.
Elle permet de jointer :

```text
items -> item_effects -> spells -> spell_effect_slots
```

## Décision de modèle

Ajouts au modèle :

- `items.hp_regen`
- `items.mana_regen`
- `items.endurance_regen`
- `character_equipment.hp_regen`
- `character_equipment.mana_regen`
- `character_equipment.endurance_regen`
- `spells`
- `spell_effect_slots`
- `item_effects`

Les champs RAW Lucy correspondants sont :

```text
items.hp_regen        <- itemraw.regen
items.mana_regen      <- itemraw.manaregen
items.endurance_regen <- itemraw.endurregen
```

Pour les effets d'item :

```text
item_effects.effect_slot     <- suffixe N dans spellidN/effecttypeN
item_effects.spell_id        <- spellidN
item_effects.effect_type_raw <- effecttypeN
item_effects.cast_time_ms    <- casttimeN
item_effects.effective_level <- efflevelN
```

`trigger_type` reste volontairement textuel (`click`, `proc`, `worn`, `focus`, `unknown`) car il faudra confirmer le mapping exact des `effecttypeN` selon les sources.
