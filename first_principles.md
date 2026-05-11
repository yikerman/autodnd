# First Principles

## LLMs are dual-purpose

Each LLM call is both: (1) a maximum-likelihood predictor — p(output | input), where anything in the prompt biases the output; and (2) an ill-defined NL problem solver. Design exploits (2) and structures around (1).

## Bounded → code; unbounded → LLM

Strictly bounded tasks go to deterministic code. Reasoning over natural language goes to LLMs + tool calls. Never blur the line.

## Hand each LLM a small problem

Minimum input for the scope; one well-defined task per call. Coordination is deterministic; reasoning is the LLM's only job.

## Perspective is the firewall

What an LLM can see is the only reliable bound on what it can leak. Restrict input structurally — soft instructions ("don't reveal X") cannot defeat what's in the prompt.

## Single source of truth, no redundancy

The WorldDB is the only canonical state. Don't store what can be queried; don't model what can be derived. Every field earns its place.

## Don't structure NL reasoning

If a fact is hard to represent deterministically, or its only consumer is an LLM doing NL reasoning, don't make it a field. Let it live in description text.

## Story first, state-backed

Prose carries the experience; state keeps the fiction honest. Mechanics resolve uncertainty when both outcomes are plausible and interesting — otherwise they stay out of the way. Bookkeeping stays separate from drama.

## Minimal first

The smallest implementation that makes the fiction more coherent or the state more reliable. Add structure only when its absence produces a real failure mode.

## Prompts shape judgment, not steps

Describe what good output looks like and which tradeoffs matter. Prevent failure modes via structure (typed inputs, restricted views, beat schemas), not longer instructions.
