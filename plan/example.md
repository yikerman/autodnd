# Worked example

A traced session through the architecture in [PLAN.md](./PLAN.md). One bootstrap call plus three turns at a roadside inn. Each step shows: model **input**, **tool calls + prose output**, and **world DB diff**.

The setup: PC is **Mara**, a courier in the kingdom of **Vellor**. She carries a sealed letter from the spymaster Korel to a contact, Olwen, in a Sken-border town. She's stopping at the Crow's Foot Inn for the night. The innkeeper Hadrian is secretly a bandit-crew informant — she doesn't know.

## Bootstrap (turn = -1)

### Director input

```
world.turn = -1
world is empty.
player_input: <none — bootstrap mode>
system: "Mint the initial world. Use narrative_time strings for backstory events.
         Mint locations, characters, items, threads, backstory events, initial
         player state, initial player-log entries. Then write the opening prose."
```

### Director tool calls

Locations:

```
create_location(id="vellor_capital", name="Vellor capital",
                description="Walled city on the river. Seat of Vellor's court and the spymaster's office.")
create_location(id="north_road", name="the north road",
                description="Main route from Vellor capital to the Sken border. Quiet lately.")
create_location(id="inn", name="Crow's Foot Inn",
                description="Roadside inn at dusk. Smoky common room, four trestle tables, stewpot over coals. The candle-on-the-outer-windowsill is the local bandit-crew's signal.")
create_location(id="heavyfall_pass", name="Heavyfall Pass",
                description="Mountain pass on the disputed Vellor–Sken border. Site of the 1047 skirmish.")
create_location(id="sken_border_town", name="Mawley",
                description="Sken-side market town. Olwen's residence.")
create_location(id="bandit_camp", name="bandit camp",
                description="Half a mile north of the inn. Six bandits under Grell.")
```

Characters (NPCs):

```
create_character(id="hadrian", name="Hadrian", location_id="inn",
                 stats=CharacterStats(hp=14, ac=11),
                 description="Ruddy innkeeper in his fifties, talkative. Informant for Grell's bandit crew; sizes up travellers and signals an ambush if any are worth robbing.")
create_character(id="korel", name="Spymaster Korel", location_id="vellor_capital", stats=…,
                 description="Vellor's spymaster. Sent Mara north with the sealed letter; the letter contains coded intelligence on Sken troop movements.")
create_character(id="olwen", name="Olwen", location_id="sken_border_town", stats=…,
                 description="Vellor agent embedded in Sken. Awaits Korel's letter.")
create_character(id="grell", name="Grell", location_id="bandit_camp", stats=…,
                 description="Bandit chief. Awaits Hadrian's signal candle.")
```

Items (incl. skills):

```
create_item(id="sealed_letter", name="sealed letter",
            description="Wax-sealed parchment, addressed to Olwen. Contents: coded Sken troop intelligence (Mara doesn't know).")
create_item(id="gold_pouch", name="gold pouch",
            description="Mara's purse. Heavier than she'd like — three weeks' courier wages plus expense money.")
create_item(id="shortsword", name="shortsword", description="Plain blade, well-kept.")
create_item(id="persuasion_skill", name="persuasion (skill)",
            description="Trained ability — Mara can read a room.",
            effects={"persuasion": 2})
```

Threads:

```
create_thread(id="vellor_sken_tensions", parent_id=None, name="Vellor–Sken tensions",
              description="Vellor and Sken have an uneasy peace since the Treaty of Three Rivers (1043). Sken troop movements have been observed lately.")
create_thread(id="courier_mission", parent_id="vellor_sken_tensions", name="Mara's courier mission",
              description="Deliver Korel's sealed letter to Olwen in Mawley within seven days. Discretion paramount; no copies.")
create_thread(id="inn_night", parent_id="courier_mission", name="Night at Crow's Foot",
              description="Mara stops at Crow's Foot Inn. If she reveals wealth, Hadrian likely tips the bandits — ambush at dawn on the north road. If unobtrusive, she passes.")
```

Backstory events (engine assigns t = 0, 1, 2, 3):

```
mint_event(id="e_treaty", narrative_time="year 1043, spring",
           location_id="vellor_capital", participants=[],
           description="Vellor and Sken signed the Treaty of Three Rivers, ending open war.",
           thread_id="vellor_sken_tensions")
mint_event(id="e_skirmish", narrative_time="year 1047, summer",
           location_id="heavyfall_pass", participants=[],
           description="Border skirmish at Heavyfall Pass. Mara's father Tomas killed.",
           thread_id="vellor_sken_tensions")
mint_event(id="e_briefing", narrative_time="year 1049, three weeks ago",
           location_id="vellor_capital", participants=["korel"],
           description="Korel handed Mara the sealed letter. Said: 'Discretion. No copies.' Did not disclose contents.",
           thread_id="courier_mission")
mint_event(id="e_arrival", narrative_time="today, dusk",
           location_id="inn", participants=["hadrian"],
           description="Mara arrived at Crow's Foot Inn at dusk. Hadrian welcomed her with stew. Mara has not yet shown wealth.",
           thread_id="inn_night")
```

Player state:

```
move_player(location_id="inn")
update_player_stats(stats=CharacterStats(hp=24, ac=13))
add_player_item("sealed_letter")
add_player_item("gold_pouch")
add_player_item("shortsword")
add_player_item("persuasion_skill")
```

(Persuasion +2 lives on the `persuasion_skill` item's `effects`, not on `stats.mods`. `check("persuasion", dc)` sums both via `effective_mods`.)

Initial log:

```
append_player_log("Two summers ago, your father Tomas died in the skirmish at Heavyfall Pass. You wear the loss like a second cloak.")
append_player_log("You took courier work after his death — his debts wouldn't pay themselves.")
append_player_log("Three weeks ago, Spymaster Korel handed you a sealed letter for one Olwen, in Mawley. 'Discretion,' he said. 'No copies.' He didn't say what was in it.")
append_player_log("You reached the Crow's Foot Inn at dusk. The innkeeper, Hadrian, welcomed you in with stew.")
```

### Director prose output (opening)

> *Two summers since Heavyfall, and the loss still rides on your shoulders like a second cloak. You took the courier wages because Tomas's debts wouldn't pay themselves — and now, three weeks after Spymaster Korel pressed a sealed letter into your hand and murmured "discretion, no copies," you've come within a day's ride of the Sken border. The Crow's Foot Inn meets you at dusk: smoky common room, four trestle tables, a stewpot muttering over the coals. The innkeeper — broad-faced, ruddy, fifties — waves you in with a generous spoon.*
>
> *"Settle in, traveller."*

### World DB diff

```diff
+ locations: { vellor_capital, north_road, inn, heavyfall_pass, sken_border_town, bandit_camp }
+ characters: { hadrian @ inn, korel @ vellor_capital, olwen @ sken_border_town, grell @ bandit_camp }
+ items: { sealed_letter, gold_pouch, shortsword, persuasion_skill (effects: persuasion +2) }
+ threads: { vellor_sken_tensions → courier_mission → inn_night }
+ events: { e_treaty(t=0), e_skirmish(t=1), e_briefing(t=2), e_arrival(t=3) }
+ player.location_id = inn
+ player.stats       = { hp:24, ac:13 }
+ player.items       = [sealed_letter, gold_pouch, shortsword, persuasion_skill]
+ player.log: 4 entries
- world.turn: -1 → 0
- world.next_event_t: 0 → 4
```

---

## Turn 1 — "I order a meal and ask Hadrian about the road north."

### Director input

```
render_omniscient(world):
  Threads: vellor_sken_tensions → courier_mission → inn_night
  Characters: hadrian @ inn ("informant for Grell's bandit crew..."), korel, olwen, grell
  Locations / Items / Player state: as above

prior_prose: <opening prose>

player_input: "I order a meal and ask Hadrian about the road north."
```

### Director tool calls

```
check(skill="persuasion", dc=10) → Resolution(roll=14, modifier=2, total=16, outcome="success")

mint_event(id="e_inn_meal", narrative_time="today, dusk (a few minutes later)",
           location_id="inn", participants=["hadrian"],
           description="Mara ate stew; asked about the north road. Hadrian volunteered freely while sizing her up. Mara has not yet shown wealth.",
           thread_id="inn_night")
→ "ok" (engine assigns t=4)

append_player_log("You ate stew; Hadrian was friendly and forthcoming about the road north — caravans took the southern fork this week.")
```

### Director prose output

> *You ease onto the bench at one of the worn trestle tables. Hadrian wipes his hands on a stained apron, ladles stew into a wooden bowl, and sets it before you. "North?" He chuckles, eyes crinkling. "Quiet road this week. Caravans took the southern fork." You notice he ladles an extra spoonful without you asking.*

### World DB diff

```diff
+ events: { e_inn_meal(t=4) }
+ player.log[4] = "You ate stew; Hadrian was friendly..."
- world.turn: 0 → 1
- world.next_event_t: 4 → 5
```

---

## Turn 2 — "I pay him with a gold coin from my pouch."

### Director input

```
render_omniscient(world): as above + e_inn_meal + new log entry.

Director sees Hadrian's full description ("informant for Grell's bandit crew...")
and inn_night's precondition ("If she reveals wealth, Hadrian likely tips the bandits").
Mara is about to reveal wealth. The trigger fires.

player_input: "I pay him with a gold coin from my pouch."
```

### Director tool calls

```
mint_event(id="e_inn_payment", narrative_time="today, dusk (still at the bar)",
           location_id="inn", participants=["hadrian"],
           description="Mara paid with a gold coin from a fat pouch. Hadrian noted the pouch.",
           thread_id="inn_night")
→ "ok" (t=5)

mint_event(id="e_hadrian_decides", narrative_time="today, dusk (private)",
           location_id="inn", participants=["hadrian"],
           description="Hadrian privately decided to signal Grell tonight — Mara's gold is worth ambushing for at dawn on the north road.",
           thread_id="inn_night")
→ "ok" (t=6)   [private canon — no log entry refers to it]

update_thread_description(id="inn_night",
    description="Hadrian has decided to betray Mara. Bandit ambush scheduled for dawn on the north road; signal candle pending.")

append_player_log("You paid with a gold coin; Hadrian's gaze caught on your pouch a moment too long.")
```

### Director prose output

> *You fish a gold coin from your pouch — heavier than you'd like to admit, even now — and slide it across the bar. Hadrian's gaze catches on the pouch for a beat too long before he pockets the coin with a practiced gesture. "Much obliged, traveller," he murmurs.*

The eye-flick is structurally legitimate: the Director (omniscient, reading `hadrian.description` + `inn_night.description`) authored an `append_player_log` entry for the player's perception of it, then wrote prose grounded in that entry. The motive ("decided to betray") lives in `e_hadrian_decides` but does not appear in the prose — the prompt-discipline rule that prose stays in player POV is the safeguard.

### World DB diff

```diff
+ events: { e_inn_payment(t=5, public), e_hadrian_decides(t=6, private) }
+ player.log[5] = "You paid with a gold coin; Hadrian's gaze caught on your pouch..."
~ threads.inn_night.description: "If she reveals wealth..." → "Hadrian has decided to betray Mara..."
- world.turn: 1 → 2
- world.next_event_t: 5 → 7
```

---

## Turn 3 — "I head upstairs to my room for the night."

### Director input

```
render_omniscient(world): updated. inn_night.description now reads
"Hadrian has decided to betray Mara..." — Director knows the candle goes out tonight.

player_input: "I head upstairs to my room for the night."

Director decides: as Mara passes the landing window, author the candle-signal as
a perceivable event. Mark end_scene: Mara has retired.
```

### Director tool calls

```
mint_event(id="e_pc_retires", narrative_time="today, just after dusk",
           location_id="inn", participants=[],
           description="Mara climbed the stairs to retire; passed the landing window.",
           thread_id="inn_night")
→ "ok" (t=7)

mint_event(id="e_hadrian_signals", narrative_time="today, just after dusk (concurrent)",
           location_id="inn", participants=["hadrian"],
           description="Hadrian set a single tallow candle on the outer windowsill — Grell's signal.",
           thread_id="inn_night")
→ "ok" (t=8)

append_player_log("You climbed the stairs to your room.")
append_player_log("A candle on the outer windowsill — odd hour for an innkeeper to leave one out.")

mark_end_scene()
```

### Director prose output

> *You climb the creaking stairs, the gold-pouch glance still nagging at you. At the landing window you glance down — on the sill below, a single tallow candle burns steady against the cool wind. An odd thing for an innkeeper to leave out at this hour. You reach the room and close the door behind you.*

### World DB diff

```diff
+ events: { e_pc_retires(t=7), e_hadrian_signals(t=8) }
+ player.log[6] = "You climbed the stairs to your room."
+ player.log[7] = "A candle on the outer windowsill — odd hour..."
- world.turn: 2 → 3
- world.next_event_t: 7 → 9
- (engine notes scene boundary at turn 2)
```

The player's log of the candle is partial — they see it but don't know its meaning. The canonical event makes its meaning explicit ("Grell's signal"); the log entry is the player's incomplete reading.

---

## What this trace demonstrates

- **One LLM does it all.** The Director makes tool calls (dice + mutations), then writes prose. No separate Narrator pass.
- **Engine owns event `t`.** The Director never picks `t`; `mint_event` returns the assigned value.
- **Bootstrap is just the same agent at turn -1.** Tool calls populate the world; the final prose is the opening.
- **NPC knowledge is implicit**: the Director knows Hadrian saw Mara's gold because `e_inn_payment.participants` includes `hadrian`. No `Character.knowledge` field needed.
- **Append-only canon**: across bootstrap + 3 turns, no entity description was rewritten. Only `Thread.description` was updated (`inn_night` once). Events and log entries grew.
- **Skill mods live on `stats.mods` plus item `effects`.** `check("persuasion", dc=10)` reads the sum (engine-side) and rolls.
- **Private canon**: `e_hadrian_decides` is fully canon, drives Hadrian's behaviour in subsequent turns, but no log entry points at it — the player never reads it directly.
- **Tells without leakage**: the eye-flick (turn 2) and the candle (turn 3) are Director-authored `append_player_log` entries grounded in omniscient state; the prose restyles them. No private detail (motives, the bandit camp) appears in the prose.
- **Prose-feedback loop**: each Director call sees the *prior turn's* prose. If a prior prose invented "a hooded patron in the corner," this turn's Director would either canonize it (mint a Character + Event) or contradict it. No drift.
