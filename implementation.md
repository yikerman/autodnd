# Implementation Notes

Companion to [`first_principles.md`](first_principles.md) and the design plan
at `~/.claude/plans/currently-the-project-is-glimmering-blanket.md`. This
doc covers concrete choices made during the build, what still needs real-LLM
validation, what's rough, and alternatives we didn't take.

## What's built

| Layer         | Files                                                                                             |
| ------------- | ------------------------------------------------------------------------------------------------- |
| Atoms / state | `autodnd/engine/world.py` — Location, Character, Item, History, World                             |
| Mutations     | `autodnd/engine/delta.py` — 9 deltas, `(world, **kwargs) → "ok"\|"error"`                         |
| Dice          | `autodnd/engine/{rules,resolution}.py` — `roll/check/attack/save`                                 |
| Perception    | `autodnd/engine/perception.py` — `who_is_in`, `passive_perception`, `names_leaked_in_description` |
| Renders       | `autodnd/engine/render.py` — `render_arbiter / for_character / for_narrator / for_player`         |
| Persistence   | `autodnd/engine/persistence.py` — JSON world + sibling `.prose.jsonl`                             |
| Agents        | `autodnd/llm/{character,narrator,arbiter,sidebar,bootstrapper}.py`                                |
| Conductor     | `autodnd/llm/arbiter.py::run_cycle`                                                               |
| CLI           | `autodnd/cli/{main,output}.py`                                                                    |
| Trace         | `autodnd/trace.py`                                                                                |
| Fixtures      | `autodnd/fixtures.py` — `vale_inn`, `waymeet_scene` (test.json port)                              |

## Concrete design choices made during build

### Schema

- **Player is `characters["player"]`** — no special atom. The id literal `"player"` is referenced in `render_for_narrator`, `render_for_player`, and the persistence test for spot-check.
- **`History` is frozen** (`model_config = {"frozen": True}` in `world.py`). Required for the cache-prefix invariant in `render_for_character` ("What you remember" is append-only).
- **`ItemPosition` is a discriminated union** of `AtLocation | HeldBy` with `kind` discriminator. Pydantic 2 needs the discriminator annotation — see `world.py:55`.
- **`Abilities` uses full English field names** (`strength`, `dexterity`, …) to avoid clashing with Python builtins (`int`, `str`).
- **`skill_mods` is `dict[str, int]`** — not a fixed enum. Skills are open-ended in fiction; arbiter picks names per check.

### Deltas

- **Errors as return strings, not exceptions.** Each delta returns `"ok: ..."` or `"error: ..."`. The LLM tool wrapper passes the string back as the tool result; LLM self-corrects on the next round. Existing pattern from legacy; carry forward.
- **`update_stats` clamps HP when hp_max is lowered alone** (`delta.py`). When hp is also given, it must respect the new hp_max.
- **`mint_history` engine-assigns id (`h{t}`) and monotonic `t`.** Caller never picks these.
- **Empty `participants` is valid** — cosmic happenings nobody knows. Arbiter still sees them.

### Rendering

- **Determinism via sorted iteration.** Every `dict` traversal in render uses `sorted(...)`. Same world → same render byte-for-byte. Tested in `test_render.py`.
- **`render_arbiter` shows ALL non-in-scene history** (offstage + cosmic + location-less). Earlier draft filtered out `location_id is None`; a test caught it (`test_arbiter_render_includes_all_private_secrets`).
- **`Character.description` is PUBLIC-only by commitment.** Comment in schema enforces it. The waymeet fixture demonstrates the discipline: every spoilable fact (Brona's cellar evidence, Silan's Whisperer brief, Torgal's daughter, Fox's archive readings) lives in a private history record, never in `description`.
- **Other characters' full descriptions are rendered in scene** (in `render_for_character`'s "Present in this scene" section). Safe because descriptions are public-only.
- **Defensive name-leak check** uses word-boundary regex on both `id` and `name`. Reduces false positives ("foxglove" doesn't trigger on player id "fox"). Logs warning + appends to `deps.leak_warnings`; does NOT block the mint.

### Agent topology

- **Pydantic AI 1.x** as the agent framework. Each agent is built with `Agent(model, deps_type=..., output_type=str, system_prompt=...)`; tools registered via `@agent.tool`.
- **Per-character system prompt is dynamic** via `@agent.system_prompt` decorator reading `ctx.deps.character_id`. One agent serves all characters; deps switches the perspective.
- **Tool name mapping**: Arbiter uses local imports aliased with `_` prefix (`_create_location`, etc.) so the tool function names exposed to the LLM stay clean (`create_location`, not `create_location_tool`).
- **`request_dice` is split into 3 tools** for character (`request_dice_check / _attack / _save`) — clearer per-tool schemas than a discriminated union.
- **`act(intent)` returns the intent string in `deps.intents`.** The arbiter sees these in the `invoke_actor` summary and resolves them on its next round (no auto-resolution).
- **`end_cycle` is a soft signal.** Sets `deps.end_requested` (kind of — actually just returns "ok: cycle ending — emit a brief acknowledgment text and stop calling tools"). LLM is instructed to emit text after, which terminates the run naturally.
- **`narrator` has no tools.** Engine auto-mints a `player_perceived` event with the narrator's prose as description. Heaviest cache hit (system prompt is global, not per-character).

### Conductor flow

- **`run_cycle`** opens an arbiter session, calls `agent.run_sync`, returns `ArbiterDeps`. The arbiter runs multi-round; `invoke_actor` calls character/narrator agents synchronously inside.
- **Sub-agent prose accumulates in `deps.prose_blocks`** in invocation order. CLI emits each block after the cycle ends (no streaming yet).
- **`deps.cycle_history_ids` is shared by reference** — sub-agents append directly. The arbiter's render in subsequent rounds sees the freshest state.
- **Witness updates are deterministic via `who_is_in`** in character `say` — minted history records get all present characters as participants.

### Caching strategy (current — passive)

- **No explicit `cache_control` markers yet.** Relies on provider's automatic prefix cache (OpenAI / DeepSeek do this; Anthropic needs explicit markers).
- **Stable prefixes by construction**: per-character system prompt is constant for a given character; "What you remember" appends only; arbiter's background section changes only on character/location creation.
- **State snapshot in character render comes AFTER memory**, so memory's prefix stays cacheable when state mutates.

### CLI

- **`--demo-scene {vale,waymeet}`** loads a fixture; **`--load PATH`** resumes; no flag falls through to one-shot bootstrapper. Mutually exclusive group.
- **Save flow**: `/save PATH` writes WorldDB JSON and starts auto-appending prose to `PATH.prose.jsonl` per cycle.
- **Slash dispatch in `_handle_slash`** returns `(should_quit, save_path)` so the loop can update both. Save path is sticky once `/save`'d.

### Persistence

- **WorldDB serializes via Pydantic** (`model_dump_json` / `model_validate_json`). No custom format.
- **Prose log is separate**, sibling `.jsonl` derived by `prose_log_path`. Reload reads only the LAST entry to print recent context.
- **Save is destructive** (overwrites). No versioning.

## To-be-tested (needs real LLM runs)

The structural firewall is verified by 23 assertions on the waymeet fixture (`test_waymeet_firewall.py`). What still needs empirical validation:

- **Arbiter follows hint discipline** (behavioral, not causal). Prompt instructs it; need traces to confirm hints don't leak causes.
- **Characters deflect on unknowns** rather than hallucinating. `slice4_waymeet_turn15.py` is the first probe.
- **Arbiter calls `invoke_actor` in dramatic order**, not e.g. round-robin. Watch the trace.
- **`act(intent)` round-trip works**: character declares → arbiter sees in `invoke_actor` summary → mints resolution events on next round → reactions follow. The schema supports it; the LLM has to use it correctly.
- **Multi-actor cycles complete** within `MAX_ROUNDS=50` and don't loop. The cap is a guess; tune from traces.
- **Bootstrapper produces public-only descriptions.** Prompt instructs strongly; verify in practice.
- **Narrator avoids character interiority.** Prompt restricts to outward signs; verify.
- **Cache hit rate** per provider — need to either log usage tokens with cache marker, or measure latency.
- **Token budget per render at scale.** Waymeet fixture has 24 history records; a long session could blow past comfortable per-call sizes.
- **`/save` + `/load` round-trip** mid-session preserves state usable by subsequent cycles. Unit test confirms schema round-trip; integration with the conductor is unverified.

## To-be-polished (rough edges)

- **No streaming output.** `LLM.call` is `agent.run_sync`; player sees prose blocks all at once after the cycle ends. Plan calls for token streaming. Needs async refactor.
- **`MAX_ROUNDS` is not actually enforced.** It's defined in `arbiter.py` but `run_cycle` calls `agent.run_sync()` which loops internally without a cap. To enforce, switch to `agent.iter()` with a manual round counter.
- **LLM API errors abort the cycle.** No retry. `cli/main.py` catches `Exception` broadly. Better: per-call retry with backoff in `run_character` / `run_narrator`, then propagate.
- **Defensive name-leak check is post-hoc.** Warns but doesn't block. Could be pre-mint validation that returns `"error: ..."` and forces the LLM to retry with corrected participants.
- **Sidebar uses LLM even for `/hp`** which could be answered by deterministic formatting. Trade-off: LLM uniformity vs latency/cost.
- **`render_for_character` doesn't show ability scores or modifiers**, only HP/AC/gold/inventory/mods. Player has full ability display in `render_for_player`. Inconsistent.
- **Bootstrapper is one-shot.** Q&A interactive version (multiple rounds with the human) was explicitly deferred. Single-shot may produce shallow worlds.
- **`/load` doesn't preserve the trace path** — if you `--trace --load X`, you start fresh in a new trace file rather than continuing the old one.
- **No way to view trace mid-session** without `tail -f` in another terminal.
- **`read_input` returns `None` on EOF/Ctrl-C silently.** No "Ctrl-D to exit" hint.
- **Recent in-scene history cap (~30) is hardcoded** in `render_arbiter`. Should be tunable when sessions get long.
- **No `History.scheduled_at`** for engine-fired offstage events. Arbiter has to remember pending things by re-reading event text every cycle.
- **No `/undo` or cycle abort** once started. If the arbiter goes off-rails mid-cycle, the only recourse is `/quit` and reload from `/save`.

## Alternative designs (not taken)

| Choice                                        | Took | Alternative                                                          | Why not                                                                                                                                                         |
| --------------------------------------------- | ---- | -------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Per-actor LLMs                                | Yes  | Single Director with restricted view                                 | Single LLM still has the leak vector; per-actor input IS the firewall. See plan for full reasoning.                                                             |
| Arbiter as conductor                          | Yes  | Pre-planned `ActOrder` then per-actor calls                          | Plan can become stale mid-cycle if a character does something unforeseen (the user explicitly raised this). Conductor adapts.                                   |
| `act(intent)` as NL string                    | Yes  | Structured intent type (`AttackIntent \| PersuadeIntent`)            | NL keeps the surface small; arbiter does the parsing it already does for player input.                                                                          |
| Beliefs as events                             | Yes  | Separate `Belief` atom on Character                                  | Events of communication / inference cover false beliefs without a parallel state channel. Add Belief if collective rumors / personality stances become awkward. |
| Knowledge derived from `History.participants` | Yes  | Explicit `Character.knowledge: list[FactRef]`                        | Derivation is free; explicit storage is more bookkeeping the LLM may forget.                                                                                    |
| `Character.description` public-only           | Yes  | Two fields: `voice_surface` + `private_identity`                     | One field with content discipline beats two fields with sync risk. Revisit if real play shows authors slipping secrets into descriptions.                       |
| Public render of other characters in scene    | Yes  | Auto-derived one-liner (first sentence)                              | Full description is safe given (b) above; one-liner risks losing voice cues.                                                                                    |
| One agent per role, dynamic system prompt     | Yes  | One agent per character (cached)                                     | Agent objects are cheap; dynamic system prompts via `@agent.system_prompt` give us per-character views without proliferation.                                   |
| `id` and `name` on every entity               | Yes  | id-only (recover name from titlecase) or name-only (rename cascades) | id is for code, name is for prose; both load-bearing.                                                                                                           |
| Single LLM provider                           | Yes  | Per-agent model tier (e.g., Haiku for sidebar, Sonnet for arbiter)   | All agents share `model_from_env` for v1; tier-mixing is a one-line change in the build functions when we want it.                                              |
| `narrator` has no tools                       | Yes  | `narrator` can `say()` like a character                              | Narrator describes environment; no need for speech events. Auto-minting `player_perceived` is enough.                                                           |
| `request_dice` split into 3 tools             | Yes  | One discriminated `request_dice` tool                                | Three tools have clearer per-tool schemas; LLM gets typed args.                                                                                                 |
| Trace as plain text                           | Yes  | OpenTelemetry / pydantic-ai instrumentation                          | Plain text traces are human-readable and easy to grep. OpenTelemetry is more powerful but heavier to set up.                                                    |
| WorldDB as canonical, prose log as archive    | Yes  | Single combined save file                                            | Separation lets you regenerate prose from event history in principle (not implemented), and avoids re-loading prose for tools that only need state.             |

## Things explicitly deferred (tracked in plan)

- Autonomous ticks (simulator runs without player input).
- Parallel `invoke_actor` (DAG with `depends_on`).
- Few-shot voice examples per character.
- `History.scheduled_at` for engine-fired offstage events.
- `History.tags` for plot organization at scale.
- `Character.current_disposition` cache for large-event-count characters.
- Streaming output.
- Combat-mode initiative / round structure beyond what arbiter improvises.
