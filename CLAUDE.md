# AutoDND

Solo one-shot D&D Dungeon Master. Storytelling over rules fidelity. Source of truth: `plan/PLAN.md`; worked example: `plan/example.md`.

## Goal

Deterministic program wrapped around a creative oracle, with **structural** defenses against:

1. **Yes-man drift** — bare LLMs follow the player's framing.
2. **Context flooding** — mechanical queries pollute narrative context.

## Components

- **Engine** (`autodnd/engine/`) — `WorldModel`, `render_omniscient(world)`, `apply_world_delta` / `apply_bootstrap` with per-field mutability validation, dice/checks/combat.
- **Director** (`autodnd/llm/director.py`) — omniscient, has dice tools. Per turn: emits `TurnDirective` (beats + `WorldDelta` + `end_scene`). At `world.turn = -1`: emits `BootstrapDirective` (entities + threads + backstory events + initial knowledge + initial player state + opening beats).
- **Narrator** (`autodnd/llm/narrator.py`) — no world access, no tools. Restyles directive beats into prose.
- **Sidebar** (`autodnd/llm/sidebar.py`) — separate session for `/hp` `/log` `/inv`. Read-only.

## Key invariants

- **Decide-then-render split.** Director owns canon and dice; Narrator owns prose. No outcome authority, no canon access for the Narrator.
- **Prose-feedback loop.** Director's per-turn prompt includes `render_omniscient(world)` + raw player input + the *prior* Narrator prose. Director canonizes, overrides, or contradicts any improvised details; Narrator hallucinations don't drift.
- **Three-layer world model.** Atoms (`Location`, `Item`, `Event`) → organization (`Character` NPC-only, `Thread` forest) → perspective (`KnowledgeEntry` with `Optional[event_id]`, append-only `PlayerState.knowledge`). Player is **not** a `Character`.
- **Per-field mutability** (see PLAN.md table). Entity `description`s and full `Event`s are write-once; `Thread.description`, `Character.location_id`/`stats`, and `PlayerState.location_id`/`stats`/`items` are mutable via typed channels in `WorldDelta`. `knowledge` is append-only.
- **False knowledge is first-class.** `KnowledgeEntry.event_id` Optional → covers pure assumptions, misinterpretations, and tells. Supersession via chronology.
- **Director-emitted ids and `t`.** Engine validates uniqueness/monotonicity. Validator failure → one Director retry with the error appended → abort on second failure.
- **Skills as items, mods on stats.** `Item` description is flavor; the mechanical bonus lives in `stats.mods` (`resolve_check` reads from there).
- **Speaker is a display name** (`"Hadrian"`), not a character id. Director resolves at emission.
- **No compaction in MVP.** Each LLM gets all of what it needs and only what it needs.
- **PydanticAI** for all three call sites; single OpenAI-compatible endpoint via `MODEL_ENDPOINT` / `MODEL_KEY` / `MODEL_NAME`.

## Conventions

- Python 3.14, `uv` for deps, `ruff` + `pyright` + `pytest`.
- REPL: `uv run autodnd` or `uv run python main.py`.
- Secrets in `.env` (gitignored); see `.env.example`.
- Tests cover the deterministic layer (seeded dice, validator, mutability). Real bar = **end-to-end playtest reads as natural / fun / logical**.

## Status

One-shot, in-memory, no persistence. Lightweight 5e combat (HP/AC/saves/conditions); no spells, feats, action economy, RAW initiative.
