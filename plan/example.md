# Worked example

A traced session through the architecture in [PLAN.md](./PLAN.md). One bootstrap call plus three turns at a roadside inn. Each step shows: model **input**, model **output**, and **world DB diff**.

The setup: PC is **Mara**, a courier in the kingdom of **Vellor**. She carries a sealed letter from the spymaster Korel to a contact, Olwen, in a Sken-border town. She's stopping at the Crow's Foot Inn for the night. The innkeeper Hadrian is secretly a bandit-crew informant — she doesn't know.

## Bootstrap (turn = -1)

### Director input

```
world.turn = -1
world is empty.
player_input: <none — bootstrap mode>
system: "Author the initial world. Use narrative_time strings for backstory events
         (year/season/relative). Mint locations, characters, items, threads,
         backstory events, and the player's initial knowledge."
```

### Director output (`BootstrapDirective`)

```json
{
  "entities": {
    "locations": [
      { "id": "vellor_capital", "name": "Vellor capital",
        "description": "Walled city on the river. Seat of Vellor's court and the spymaster's office." },
      { "id": "north_road", "name": "the north road",
        "description": "Main route from Vellor capital to the Sken border. Quiet lately; some traffic to the southern fork." },
      { "id": "inn", "name": "Crow's Foot Inn",
        "description": "Roadside inn at dusk. Smoky common room, four trestle tables, stewpot over coals. The candle-on-the-outer-windowsill is the local bandit-crew's signal." },
      { "id": "heavyfall_pass", "name": "Heavyfall Pass",
        "description": "Mountain pass on the disputed Vellor–Sken border. Site of the 1047 skirmish." },
      { "id": "sken_border_town", "name": "Mawley",
        "description": "Sken-side market town. Olwen's residence." },
      { "id": "bandit_camp", "name": "bandit camp",
        "description": "Half a mile north of the inn, behind a stand of pines. Six bandits under Grell." }
    ],
    "characters": [
      { "id": "hadrian", "name": "Hadrian", "location_id": "inn",
        "stats": { "hp": 14, "ac": 11, "mods": {} },
        "description": "Ruddy innkeeper in his fifties, talkative, generous with stew. Informant for Grell's bandit crew; sizes up travellers and signals an ambush if any are worth robbing." },
      { "id": "korel", "name": "Spymaster Korel", "location_id": "vellor_capital",
        "stats": { "hp": 18, "ac": 12, "mods": {} },
        "description": "Vellor's spymaster. Sent Mara north with the sealed letter; the letter contains coded intelligence on Sken troop movements." },
      { "id": "olwen", "name": "Olwen", "location_id": "sken_border_town",
        "stats": { "hp": 16, "ac": 12, "mods": {} },
        "description": "Vellor agent embedded in Sken. Awaits Korel's letter." },
      { "id": "mara_father", "name": "Tomas (deceased)", "location_id": "heavyfall_pass",
        "stats": { "hp": 0, "ac": 0, "mods": {} },
        "description": "Mara's father. Killed at Heavyfall Pass in the 1047 skirmish." },
      { "id": "grell", "name": "Grell", "location_id": "bandit_camp",
        "stats": { "hp": 22, "ac": 14, "mods": {} },
        "description": "Bandit chief. Awaits Hadrian's signal candle." }
    ],
    "items": [
      { "id": "sealed_letter", "name": "sealed letter",
        "description": "Wax-sealed parchment, addressed to Olwen. Contents: coded Sken troop intelligence (Mara doesn't know)." },
      { "id": "gold_pouch", "name": "gold pouch",
        "description": "Mara's purse. Heavier than she'd like — three weeks' courier wages plus expense money." },
      { "id": "shortsword", "name": "shortsword", "description": "Plain blade, well-kept." },
      { "id": "persuasion_skill", "name": "persuasion (skill)",
        "description": "Trained ability — Mara can read a room. (Mechanical bonus lives in player.stats.mods.persuasion.)" }
    ]
  },
  "threads": [
    { "id": "vellor_sken_tensions", "parent_id": null, "name": "Vellor–Sken tensions",
      "description": "Vellor and Sken have an uneasy peace since the Treaty of Three Rivers (1043). Border skirmishes recur. Sken troop movements have been observed lately." },
    { "id": "courier_mission", "parent_id": "vellor_sken_tensions", "name": "Mara's courier mission",
      "description": "Deliver Korel's sealed letter to Olwen in Mawley within seven days. Discretion paramount; no copies." },
    { "id": "inn_night", "parent_id": "courier_mission", "name": "Night at Crow's Foot",
      "description": "Mara stops at Crow's Foot Inn. If she reveals wealth, Hadrian likely tips the bandits — ambush at dawn on the north road. If unobtrusive, she passes." }
  ],
  "backstory_events": [
    { "id": "e_treaty",      "t": 0, "narrative_time": "year 1043, spring",
      "location_id": "vellor_capital", "participants": [],
      "description": "Vellor and Sken signed the Treaty of Three Rivers, ending open war.",
      "thread_id": "vellor_sken_tensions" },
    { "id": "e_skirmish",    "t": 1, "narrative_time": "year 1047, summer",
      "location_id": "heavyfall_pass", "participants": ["mara_father"],
      "description": "Border skirmish at Heavyfall Pass. Mara's father Tomas killed.",
      "thread_id": "vellor_sken_tensions" },
    { "id": "e_recruitment", "t": 2, "narrative_time": "year 1048, autumn",
      "location_id": "vellor_capital", "participants": [],
      "description": "Mara took up courier work to pay off Tomas's debts.",
      "thread_id": "courier_mission" },
    { "id": "e_briefing",    "t": 3, "narrative_time": "year 1049, three weeks ago",
      "location_id": "vellor_capital", "participants": ["korel"],
      "description": "Korel handed Mara the sealed letter. Said: 'Discretion. No copies.' Did not disclose contents.",
      "thread_id": "courier_mission" },
    { "id": "e_departure",   "t": 4, "narrative_time": "year 1049, yesterday morning",
      "location_id": "vellor_capital", "participants": [],
      "description": "Mara departed the capital northbound.",
      "thread_id": "courier_mission" },
    { "id": "e_arrival",     "t": 5, "narrative_time": "today, dusk",
      "location_id": "inn", "participants": ["hadrian"],
      "description": "Mara arrived at Crow's Foot Inn at dusk. Hadrian welcomed her with stew. Mara has not yet shown wealth.",
      "thread_id": "inn_night" }
  ],
  "initial_knowledge": [
    { "event_id": "e_skirmish",    "text": "Two summers ago, your father Tomas died in the skirmish at Heavyfall Pass. You wear the loss like a second cloak.", "learned_at": -1 },
    { "event_id": "e_recruitment", "text": "You took courier work after his death — his debts wouldn't pay themselves.", "learned_at": -1 },
    { "event_id": "e_briefing",    "text": "Three weeks ago, Spymaster Korel handed you a sealed letter for one Olwen, in Mawley. 'Discretion,' he said. 'No copies.' He didn't say what was in it.", "learned_at": -1 },
    { "event_id": "e_departure",   "text": "You left the capital yesterday morning.", "learned_at": -1 },
    { "event_id": "e_arrival",     "text": "You reached the Crow's Foot Inn at dusk. The innkeeper, Hadrian, welcomed you in with stew.", "learned_at": -1 }
  ],
  "initial_player_state": {
    "location_id": "inn",
    "stats": { "hp": 24, "ac": 13, "mods": { "persuasion": 2 } },
    "items": ["sealed_letter", "gold_pouch", "shortsword", "persuasion_skill"],
    "knowledge": []
  },
  "opening_beats": [
    { "kind": "observation",
      "text": "Two summers since Heavyfall — the loss still sits on Mara's shoulders like a second cloak." },
    { "kind": "observation",
      "text": "Three weeks after Korel pressed the sealed letter into her hand with 'discretion, no copies', she is within a day's ride of the Sken border." },
    { "kind": "observation",
      "text": "The Crow's Foot Inn meets her at dusk: smoky common room, four trestle tables, a stewpot muttering over coals." },
    { "kind": "action",
      "text": "Hadrian — broad-faced, ruddy, fifties — waves her in with a generous spoon." },
    { "kind": "dialogue", "speaker": "Hadrian",
      "text": "Settle in, traveller." }
  ]
}
```

### World DB diff

```diff
+ locations: { vellor_capital, north_road, inn, heavyfall_pass, sken_border_town, bandit_camp }
+ characters: { hadrian @ inn, korel @ vellor_capital, olwen @ sken_border_town,
+               mara_father @ heavyfall_pass, grell @ bandit_camp }
+ items: { sealed_letter, gold_pouch, shortsword, persuasion_skill }
+ threads: { vellor_sken_tensions → courier_mission → inn_night }
+ events: { e_treaty(t=0), e_skirmish(t=1), e_recruitment(t=2),
+           e_briefing(t=3), e_departure(t=4), e_arrival(t=5) }
+ player.knowledge: 5 entries (all learned_at=-1)
+ player.location_id = inn
+ player.stats     = { hp: 24, ac: 13, mods: { persuasion: 2 } }
+ player.items     = [sealed_letter, gold_pouch, shortsword, persuasion_skill]
- world.turn: -1 → 0
```

### Opening Narrator call

Same contract as any turn — Narrator restyles `opening_beats`. No special path, no peek at world state.

**Input:** narration history (empty) + the 5 `opening_beats` above.

**Output (prose):**

> *Two summers since Heavyfall, and the loss still rides on your shoulders like a second cloak. You took the courier wages because Tomas's debts wouldn't pay themselves — and now, three weeks after Spymaster Korel pressed a sealed letter into your hand and murmured "discretion, no copies," you've come within a day's ride of the Sken border. The Crow's Foot Inn meets you at dusk: smoky common room, four trestle tables, a stewpot muttering over the coals. The innkeeper — broad-faced, ruddy, fifties — waves you in with a generous spoon.*
>
> *"Settle in, traveller."*

---

## Turn 1 — "I order a meal and ask Hadrian about the road north."

### Director input

```
render_omniscient(world):
  Threads:
    vellor_sken_tensions: "Vellor and Sken have an uneasy peace..."
      Events: e_treaty (1043 spring), e_skirmish (1047 summer)
      Children:
        courier_mission: "Deliver Korel's sealed letter to Olwen..."
          Events: e_recruitment, e_briefing, e_departure
          Children:
            inn_night: "Mara stops at Crow's Foot. If she reveals wealth..."
              Events: e_arrival
  Characters:
    hadrian @ inn — "Ruddy innkeeper... informant for Grell's bandit crew..."
    korel @ vellor_capital, olwen @ sken_border_town, ...
  Locations: ...  Items: ...
  Player: at inn, stats={hp:24, ac:13, mods:{persuasion:2}},
          items=[sealed_letter, gold_pouch, shortsword, persuasion_skill],
          knowledge=<5 entries from bootstrap>

prior_narration: <opening prose>

player_input: "I order a meal and ask Hadrian about the road north."
```

### Director tool calls + output

Director calls `resolve_check(skill="persuasion", dc=10)` → engine reads `player.stats.mods.persuasion = +2`, rolls `14 + 2 = 16` → `Resolution(outcome="success")`.

```json
{
  "beats": [
    { "kind": "action",      "text": "Mara takes a seat at one of the trestle tables." },
    { "kind": "action",      "text": "Hadrian wipes his hands on his apron, ladles a bowl of stew, sets it down." },
    { "kind": "dialogue",    "speaker": "Hadrian",
      "text": "North? Quiet road this week. Caravans took the southern fork." },
    { "kind": "observation", "text": "Hadrian ladles an extra spoonful without being asked." }
  ],
  "world_delta": {
    "events_to_mint": [
      { "id": "e_inn_meal", "t": 6, "narrative_time": "today, dusk (a few minutes later)",
        "location_id": "inn", "participants": ["hadrian"],
        "description": "Mara ate stew; asked about the north road. Hadrian volunteered freely while sizing her up. Mara has not yet shown wealth.",
        "thread_id": "inn_night" }
    ],
    "knowledge_to_append": [
      { "event_id": "e_inn_meal",
        "text": "You ate stew; Hadrian was friendly and forthcoming about the road north — caravans took the southern fork this week.",
        "learned_at": 0 }
    ]
  },
  "end_scene": false
}
```

### World DB diff

```diff
+ events: { e_inn_meal(t=6, narrative_time="today, dusk (a few minutes later)") }
+ player.knowledge[5] = KE(e_inn_meal, "You ate stew; Hadrian was friendly...", learned_at=0)
- world.turn: 0 → 1
```

### Narrator input

```
narration history: <opening prose only>
directive.beats: [4 beats above]
```

### Narrator output (prose)

> *You ease onto the bench at one of the worn trestle tables. Hadrian wipes his hands on a stained apron, ladles stew into a wooden bowl, and sets it before you. "North?" He chuckles, eyes crinkling. "Quiet road this week. Caravans took the southern fork." You notice he ladles an extra spoonful without you asking.*

---

## Turn 2 — "I pay him with a gold coin from my pouch."

### Director input

```
render_omniscient(world): same as turn 1, plus e_inn_meal and the new knowledge entry.

Director sees Hadrian's full description — "informant for Grell's bandit crew;
sizes up travellers and signals an ambush if any are worth robbing." It also sees
thread inn_night's precondition: "If she reveals wealth, Hadrian likely tips the
bandits." Mara is about to reveal wealth. The trigger fires.

player_input: "I pay him with a gold coin from my pouch."
```

### Director output (no dice needed)

```json
{
  "beats": [
    { "kind": "action",      "text": "Mara fishes a gold coin from a visibly fat pouch." },
    { "kind": "observation", "text": "Hadrian's eyes catch on the pouch a beat too long before he pockets the coin." },
    { "kind": "dialogue",    "speaker": "Hadrian", "text": "Much obliged, traveller." }
  ],
  "world_delta": {
    "events_to_mint": [
      { "id": "e_inn_payment",     "t": 7, "narrative_time": "today, dusk (still at the bar)",
        "location_id": "inn", "participants": ["hadrian"],
        "description": "Mara paid with a gold coin from a fat pouch. Hadrian noted the pouch.",
        "thread_id": "inn_night" },
      { "id": "e_hadrian_decides", "t": 8, "narrative_time": "today, dusk (private)",
        "location_id": "inn", "participants": ["hadrian"],
        "description": "Hadrian privately decided to signal Grell tonight — Mara's gold is worth ambushing for at dawn on the north road.",
        "thread_id": "inn_night" }
    ],
    "knowledge_to_append": [
      { "event_id": "e_inn_payment",
        "text": "You paid with a gold coin; Hadrian's gaze caught on your pouch a moment too long.",
        "learned_at": 1 }
    ],
    "threads_to_update": {
      "inn_night": "Hadrian has decided to betray Mara. Bandit ambush scheduled for dawn on the north road; signal candle pending."
    }
  },
  "end_scene": false
}
```

### World DB diff

```diff
+ events: { e_inn_payment(t=7, public),
+           e_hadrian_decides(t=8, private — no knowledge entry points at it) }
+ player.knowledge[6] = KE(e_inn_payment, "...gaze caught on your pouch...", learned_at=1)
~ threads.inn_night.description: "Mara stops at Crow's Foot..."
                              → "Hadrian has decided to betray Mara..."
- world.turn: 1 → 2
```

`e_hadrian_decides` is **private canon**: the Director (omniscient) can reason from it in future turns; no knowledge entry refers to it; the Narrator never sees it.

### Narrator input

```
narration history: <opening prose, turn 1 prose>
directive.beats: [3 beats above]
```

### Narrator output

> *You fish a gold coin from your pouch — heavier than you'd like to admit, even now — and slide it across the bar. Hadrian's gaze catches on the pouch for a beat too long before he pockets the coin with a practiced gesture. "Much obliged, traveller," he murmurs.*

The eye-flick is structurally legitimate: the Director (omniscient, with `hadrian.description` and `inn_night.description` in view) authored the observation beat. The Narrator only restyled.

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

### Director output

```json
{
  "beats": [
    { "kind": "action",      "text": "Mara climbs the creaking stairs." },
    { "kind": "observation", "text": "Through the landing window, a single tallow candle burns on the outer sill below — odd hour for one." },
    { "kind": "transition",  "text": "Mara reaches the room and closes the door." }
  ],
  "world_delta": {
    "events_to_mint": [
      { "id": "e_pc_retires",      "t": 9,  "narrative_time": "today, just after dusk",
        "location_id": "inn", "participants": [],
        "description": "Mara climbed the stairs to retire; passed the landing window.",
        "thread_id": "inn_night" },
      { "id": "e_hadrian_signals", "t": 10, "narrative_time": "today, just after dusk (concurrent)",
        "location_id": "inn", "participants": ["hadrian"],
        "description": "Hadrian set a single tallow candle on the outer windowsill — Grell's signal.",
        "thread_id": "inn_night" }
    ],
    "knowledge_to_append": [
      { "event_id": "e_pc_retires",
        "text": "You climbed the stairs to your room.", "learned_at": 2 },
      { "event_id": "e_hadrian_signals",
        "text": "A candle on the outer windowsill — odd hour for an innkeeper to leave one out.",
        "learned_at": 2 }
    ]
  },
  "end_scene": true
}
```

### World DB diff

```diff
+ events: { e_pc_retires(t=9), e_hadrian_signals(t=10) }
+ player.knowledge[7] = KE(e_pc_retires, "You climbed the stairs...", learned_at=2)
+ player.knowledge[8] = KE(e_hadrian_signals, "A candle on the outer windowsill — odd hour...", learned_at=2)
- world.turn: 2 → 3
```

(Engine separately notes the `end_scene` boundary in its own bookkeeping — see PLAN.md Flow §6 — but this is not a `WorldModel` field.)

Note: the player's knowledge of the candle is partial — they see it but don't know its meaning. The canonical event makes its meaning explicit ("Grell's signal"); the knowledge entry is the player's incomplete reading.

### Narrator input

```
narration history: <opening, turn 1, turn 2 prose>
directive.beats: [3 beats above]
```

### Narrator output

> *You climb the creaking stairs, the gold-pouch glance still nagging at you. At the landing window you glance down — on the sill below, a single tallow candle burns steady against the cool wind. An odd thing for an innkeeper to leave out at this hour. You reach the room and close the door behind you.*

---

## What this trace demonstrates

- **Bootstrap has its own shape.** `BootstrapDirective` mints the world plus an `opening_beats` list; the Narrator restyles those beats with the same contract as any turn — no special opening pipeline.
- **Bootstrap is canon**, not exposition. Backstory events are normal `Event`s with `narrative_time` strings, in the same events table. Player knowledge of them is an ordinary `KnowledgeEntry`.
- **NPC knowledge is implicit**: the Director knows Hadrian saw Mara's gold because `e_inn_payment.participants` includes `hadrian`. No `Character.knowledge` field needed.
- **Append-only canon**: across bootstrap + 3 turns, no entity description was rewritten. Only `Thread.description` was updated (`inn_night` once). Events and knowledge entries grew. No mutable-state channels (`character_moves`, `player_stats`, etc.) needed firing this scene; in a fight or travel scene they would.
- **Skill mods live on `stats.mods`.** `resolve_check("persuasion", dc=10)` reads `player.stats.mods.persuasion = +2` directly. The `persuasion_skill` item is flavor only.
- **Speaker is a display name.** Beats use `"speaker": "Hadrian"`, not `"hadrian"`. The Narrator never resolves character ids.
- **Private canon**: `e_hadrian_decides` is fully canon, used by the Director in subsequent turns to drive Hadrian's behavior, but no knowledge entry points at it — the player never sees it directly.
- **Tells without leakage**: the eye-flick (turn 2) and the candle (turn 3) are Director-authored observations grounded in omniscient state. The Narrator restyled prose-ready beats; it never touched `hadrian.description`.
- **Tone via narration history**: each Narrator call sees all prior prose. Turn 2's "even now" callback to "wear the loss like a second cloak" (opening) is the kind of continuity this enables.
- **Prose-feedback channel**: each Director call also receives the *prior turn's* Narrator prose. If the Narrator had improvised "a hooded patron in the corner," the Director would either canonize it (mint a Character + Event) or contradict it next turn — Narrator hallucinations don't drift unchecked.
