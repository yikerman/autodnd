# AutoDND Agent Notes

AutoDND is a solo tabletop roleplaying experiment: a creative Dungeon Master
held inside a small deterministic frame.

The goal is not full D&D rules fidelity. The goal is a session that feels
alive, fair, and surprising. The story should move with the player's choices
while the world, dice, resources, danger, and NPC motives provide resistance.

## Project Taste

- **Story first, state-backed.** Prose carries the experience; mechanics keep
  the fiction honest.
- **Consequences are real.** Meaningful changes in money, health, items,
  knowledge, position, relationships, and danger should persist in game state.
- **Uncertainty gets resolved.** When success and failure are both plausible
  and interesting, dice should decide the outcome.
- **Perspective matters.** The player-facing story should stay grounded in what
  the character can perceive, infer, and misread.
- **Memory is useful, not exhaustive.** Preserve facts that matter for play:
  what happened, what changed, what the player knows, and what remains open.
- **Rules serve momentum.** Suggest lightweight, legible mechanics that prevent
  nonsense while leaving room for the story to breathe.
- **Bookkeeping stays separate from drama.** Status questions should give clear
  answers without bending the narrative thread.

AutoDND should feel like a careful human DM: atmospheric, consequential,
surprising, and strict about impossible accounting.

## Coding Direction

Shape changes around the product behavior, not around framework ceremony. The
best implementation is the smallest one that makes the fiction more coherent,
the state more reliable, or the agent behavior easier to steer.

Use explicit state and validated transitions for money, inventory, HP,
movement, rolls, clocks, and learned facts. Let prose stay flexible where exact
mechanics would only add friction.

When improving prompts or agent behavior, favor structural support over longer
instructions. A validator, typed tool, narrower state model, or clearer boundary
usually beats another paragraph of prompt text.

Use `uv` for Python environment, dependency, and test commands.

## Prompt Writing

Prompts should be short, dense, and opinionated. They should describe the
desired outcome, the agent's authority, the important boundaries, and the design
logic behind choices that affect behavior.

Write prompts as guidance for judgment, not as a transcript of the reasoning
process. The model can work out steps on its own; the prompt should make clear
what good output looks like and which tradeoffs matter.

Good prompts:

- State the agent's responsibility.
- Define the information and decisions the agent owns.
- Suggest durable principles over exhaustive examples.
- Explain design logic when it changes behavior.
- Use structure to prevent known failure modes.
- Keep only instructions that change the result.

Shorter prompts are usually better when they preserve the boundary. Extra text
should earn its place by preventing a real failure mode.
