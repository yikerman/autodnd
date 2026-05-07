# AutoDND

Solo one-shot D&D Dungeon Master. Storytelling over rules fidelity.

## Goal

Deterministic program wrapped around a creative oracle, with **structural** defenses against:

1. **Yes-man drift** — bare LLMs follow the player's framing.
2. **Context flooding** — mechanical queries pollute narrative context.

## Components

- **Engine** (`autodnd/engine/`) — `WorldModel`, `render_omniscient(world)`, per-mutation `apply_*` validators, dice/checks/combat.
- **Director** (`autodnd/llm/director.py`) — the only narrative LLM. Omniscient. Reads world + prior prose + player input, calls dice + mutation tools, emits prose. Same agent runs bootstrap (`world.turn = -1`) and per-turn play.
- **Sidebar** (`autodnd/llm/sidebar.py`) — separate session for `/hp` `/log` `/inv`. Read-only.

## Key invariants

- **Director owns everything narrative.** Canon, dice, prose. Mutations are tool calls; the engine validates each and returns errors inline so the Director self-corrects. Anything narrated as a state change must canonize via the matching mutation tool, or next turn's render contradicts it.
- **Prose-feedback loop.** Director's per-turn prompt includes `render_omniscient(world)` + raw player input + the *prior* turn's prose; it canonizes, overrides, or contradicts improvised details from the last turn.
- **Three-layer world model.** Atoms (`Location`, `Item`, `Event`) → organization (`Character` NPC-only, `Thread` forest) → perspective (`PlayerState.log: list[str]`, append-only NL log of what the player perceived). Player is **not** a `Character`.
- **Per-field mutability.** Entity `description`s and full `Event`s are write-once; `Thread.description`, `Item.description`, `Character.location_id`/`stats`, `PlayerState.location_id`/`stats`/`items` are mutable via dedicated tools. `log` is append-only.
- **False knowledge is emergent.** Tells, misinterpretations, and pure assumptions are all just NL log lines. Chronology supersedes — the latest entry wins for present-tense rendering.
- **Director-emitted ids; engine-assigned `t`.** Director picks entity ids; engine auto-increments `Event.t`.
- **Skills as items, mods on stats.** `Item` description is flavor; the mechanical bonus lives in `stats.mods` + `item.effects` (`resolve_check` reads from there).
- **Hidden info stays in canon, not prose.** Director sees omniscient state but writes prose from the player's POV. Private events / NPC motives / un-perceived foreshadowing never appear in prose. Prompt discipline is the only safeguard (no separate Narrator).
- **No compaction in MVP.** The Director gets all of what it needs and only what it needs.
- **PydanticAI** for both call sites (Director, Sidebar); single OpenAI-compatible endpoint via `MODEL_ENDPOINT` / `MODEL_KEY` / `MODEL_NAME`.

## Conventions

- Python 3.14, `uv` for deps, `ruff` + `pyright` + `pytest`.
- REPL: `uv run autodnd` or `uv run python main.py`.
- Secrets in `.env` (gitignored); see `.env.example`.
- Tests cover the deterministic layer (seeded dice, validators, mutability). Real bar = **end-to-end playtest reads as natural / fun / logical**.

## Status

One-shot, in-memory; `/save FILE` and `--load FILE` resume mid-session. Lightweight 5e combat (HP/AC/saves/conditions); no spells, feats, action economy, RAW initiative.
