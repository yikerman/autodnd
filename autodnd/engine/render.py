"""Markdown projection of :class:`WorldModel` for the Director's prompt.

Only the Director reads the world. Output is deterministic (sorted by id
within each section) so prompt caching and snapshot tests stay stable.

Shape::

    # World (turn N)

    ## Threads
    ### root_thread — Display Name
    ...
    Events in this thread:
    - `id` t=N (narrative_time) at LOCATION_NAME (id=`loc`); participants: NAMES — description
    #### child_thread ...

    ## Characters (NPCs)
    ## Locations
    ## Items
    ## Player
"""

from autodnd.engine.rules import effective_mods
from autodnd.engine.world import CharacterStats, Event, Thread, WorldModel


def render_omniscient(world: WorldModel) -> str:
    name_of_loc = {loc.id: loc.name for loc in world.locations.values()}
    name_of_char = {char.id: char.name for char in world.characters.values()}

    children_of: dict[str | None, list[Thread]] = {}
    for thr in world.threads.values():
        children_of.setdefault(thr.parent_id, []).append(thr)
    for parent_id in children_of:
        children_of[parent_id].sort(key=lambda t: t.id)

    events_of_thread: dict[str, list[Event]] = {}
    for ev in world.events.values():
        events_of_thread.setdefault(ev.thread_id, []).append(ev)
    for tid in events_of_thread:
        events_of_thread[tid].sort(key=lambda e: e.t)

    lines: list[str] = [
        f"# World (turn {world.turn})",
        "",
        "## Threads",
        "",
    ]

    def render_thread(thread: Thread, depth: int) -> None:
        heading = "#" * min(depth + 3, 6)
        lines.append(f"{heading} `{thread.id}` — {thread.name}")
        lines.append(thread.description)
        lines.append("")
        events = events_of_thread.get(thread.id, [])
        if events:
            lines.append("Events:")
            for ev in events:
                loc_name = name_of_loc.get(ev.location_id, ev.location_id)
                if ev.participants:
                    parts = ", ".join(name_of_char.get(p, p) for p in ev.participants)
                    parts_segment = f" (with {parts})"
                else:
                    parts_segment = ""
                lines.append(
                    f"- `{ev.id}` t={ev.t} ({ev.narrative_time}) "
                    f"at {loc_name} (id=`{ev.location_id}`){parts_segment} — {ev.description}"
                )
            lines.append("")
        for child in children_of.get(thread.id, []):
            render_thread(child, depth + 1)

    roots = children_of.get(None, [])
    if not roots:
        lines.append("(no threads)")
        lines.append("")
    for root in roots:
        render_thread(root, 0)

    rendered_threads = set(world.threads)
    orphan_events = [
        ev for ev in world.events.values() if ev.thread_id not in rendered_threads
    ]
    if orphan_events:
        lines.append("## Events with missing thread (data error)")
        lines.append("")
        for ev in sorted(orphan_events, key=lambda e: e.t):
            lines.append(
                f"- `{ev.id}` t={ev.t} thread_id=`{ev.thread_id}` — {ev.description}"
            )
        lines.append("")

    lines.append("## Characters (NPCs)")
    lines.append("")
    if not world.characters:
        lines.append("(none)")
    for char in sorted(world.characters.values(), key=lambda c: c.id):
        loc_name = name_of_loc.get(char.location_id, char.location_id)
        lines.append(
            f"- **{char.name}** (id=`{char.id}`) @ {loc_name} (id=`{char.location_id}`) "
            f"— {_format_stats(char.stats)}"
        )
        lines.append(f"  {char.description}")
    lines.append("")

    lines.append("## Locations")
    lines.append("")
    if not world.locations:
        lines.append("(none)")
    for loc in sorted(world.locations.values(), key=lambda x: x.id):
        lines.append(f"- **{loc.name}** (id=`{loc.id}`) — {loc.description}")
    lines.append("")

    lines.append("## Items")
    lines.append("")
    if not world.items:
        lines.append("(none)")
    for item in sorted(world.items.values(), key=lambda x: x.id):
        effects_str = (
            f" [effects: {_format_mods(item.effects)}]" if item.effects else ""
        )
        lines.append(
            f"- **{item.name}** (id=`{item.id}`){effects_str} — {item.description}"
        )
    lines.append("")

    lines.append("## Player")
    lines.append("")
    p = world.player
    p_loc_name = name_of_loc.get(p.location_id, p.location_id)
    eff = effective_mods(p.stats, p.items, world.items)
    lines.append(f"Location: {p_loc_name} (id=`{p.location_id}`)")
    lines.append(f"Stats: {_format_stats(p.stats)}")
    lines.append(f"Effective mods (stats + carried items): {_format_mods(eff)}")
    items_str = ", ".join(f"`{i}`" for i in p.items) if p.items else "—"
    lines.append(f"Items: {items_str}")
    lines.append("")
    lines.append("Player log (chronological, oldest first):")
    if not p.log:
        lines.append("- (none)")
    for entry in p.log:
        lines.append(f"- {entry}")
    lines.append("")

    return "\n".join(lines)


def _format_mods(mods: dict[str, int]) -> str:
    if not mods:
        return "—"
    return ", ".join(f"{k}{v:+d}" for k, v in sorted(mods.items()))


def _format_stats(s: CharacterStats) -> str:
    hp_part = f"HP {s.hp}/{s.hp_max}" if s.hp_max > 0 else f"HP {s.hp}"
    abilities = (
        f"STR {s.strength}, DEX {s.dexterity}, CON {s.constitution}, "
        f"INT {s.intelligence}, WIS {s.wisdom}, CHA {s.charisma}"
    )
    return f"{hp_part}, AC {s.ac}, {abilities}, mods: {_format_mods(s.mods)}"
