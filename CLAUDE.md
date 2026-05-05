# AutoDND

Solo one-shot D&D Dungeon Master. Prioritizes interactive storytelling over rules fidelity.

## Goal

A deterministic program wrapped around a creative oracle, with **structural** defenses against two LLM failure modes:

1. **Yes-man drift** — bare LLMs follow the player's framing; no real twists, foreshadowing, or pushback.
2. **Context flooding** — mechanical queries (HP, dice math) in the same conversation as narrative pollute it.

## Architecture

Five components. Each LLM session is single-purpose and isolated.

- **Engine** (Python, `autodnd/engine/`) — single source of truth. Owns `WorldModel`, `render_omniscient`/`render_player`, `apply_world_delta` (with append-only validation). Implements dice/checks/combat deterministically.
- **Narrator** (LLM, `autodnd/llm/narrator.py`) — renders one turn as prose. Sees only `render_player(world)` + transient scene log + Creative Thinker injection. Cannot decide outcomes; cannot mutate canon.
- **Director** (Python, `autodnd/engine/director.py`) — scene-boundary scheduler. No LLM persona of its own.
- **Creative Thinker** (LLM, `autodnd/llm/creative.py`) — plot brain. Given `render_omniscient(world)` + scene log, returns a structured `WorldDelta` (events to mint, knowledge to append, thread description updates, optional new entities, optional Narrator injection). Pacing is the LLM's call.
- **Sidebar** (LLM, `autodnd/llm/sidebar.py`) — separate session for `/hp` `/log` `/inv`. Never feeds into Narrator context.

## Key design choices

- **Commit-then-narrate.** Outcomes resolved by deterministic dice + engine *before* the Narrator's turn. Narrator only renders.
- **Three-layer world model.**
  - *Atoms*: `Location`, `Item`, `Event` (with monotonic `t`, location, participants, NL description = full truth).
  - *Organization*: `Character` (NPC; player is **not** a Character), `Thread` (forest via `parent_id`; owns events).
  - *Perspective*: `KnowledgeEntry` (Optional `event_id`, NL `text` — may be partial / wrong / a tell / pure assumption), `PlayerState` (location, stats, items, append-only `knowledge`).
- **Storage is normalized; LLM-facing rendering is tree-shaped.** `render_omniscient(world)` walks the thread forest for the Creative Thinker; `render_player(world)` produces a chronological knowledge timeline + current-scene state for the Narrator. Pydantic stays normalized.
- **Plan B: events minted at scene boundary only.** Per-turn the Narrator writes to a transient `scene_log`. At each scene boundary the Creative Thinker condenses the log into atomic canon events (public + private) and authors knowledge entries. No per-turn canon mutation.
- **Append-only at the entity level.** `Location.description`, `Character.description`, `Item.description`, individual `Event` records — all write-once. `Thread.description` is updateable; events list, knowledge list grow.
- **False knowledge is first-class.** `KnowledgeEntry.event_id` is `Optional`; `text` is NL. Misinterpretations, tells, and pure assumptions all fit. Supersession via chronology — append newer entry, latest-on-subject wins for present-tense rendering.
- **Items subsume skills.** A skill is an `Item` with NL `description`. One concept, one schema.
- **Bootstrap = commit upfront, append on the fly.** Most canon authored at game start. Player surprises trigger new entity mints (turn-time, not scene-boundary).
- **No compaction in MVP.** Feed each LLM all of what it needs and only what it needs.
- **PydanticAI** for all three LLM call sites — provider-agnostic, native structured output, clean tool-use.

## Conventions

- Python 3.14, `uv` for deps, `ruff` + `pyright` + `pytest` configured.
- Run REPL: `uv run autodnd` or `uv run python main.py`.
- Secrets in `.env` (gitignored); see `.env.example`.
- Tests for the deterministic layer (visibility wrapper, seeded dice, schema-validated deltas). The real bar is **end-to-end playtest reads as natural / fun / logical** — not unit-test green.

## Status

Scope is one-shot, in-memory, no persistence. Lightweight 5e combat (HP/AC/saves/conditions); no spells, feats, action economy, or RAW initiative.
