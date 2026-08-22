"""Multi-agent graph: triage, then specialists, then the digest.

    Ingest -> Triage -+-> BillAnalyst -+
                      +-> Negotiator  -+-> Brief
                      +-> Scheduler   -+

LANE A: verify `GraphBuilder` against the current SDK before writing this - use
the `context7` MCP server, `/websites/strandsagents`,
`docs/user-guide/concepts/multi-agent/graph`.

Notes that matter:

* Pass `household_id`, `run_id` and the provider bundle via `invocation_state`,
  not in the prompt. It reaches tools through `ToolContext` and hooks without
  ever entering the model's context - cheaper, and it cannot be prompt-injected.
* `PolicyHook` must be registered on every agent that can call a governed tool.
  A specialist without the hook is an ungoverned path to someone's bank account.
* Prefer `structured_output_model=Finding` / `ProposedAction` over parsing JSON
  out of prose.
* System prompts live in `prompts/*.md`. Load them; do not inline them.
"""

from __future__ import annotations

from typing import Any


def build_graph(household_id: str, providers: Any, policies: list[Any], store: Any) -> Any:
    """Assemble the run graph.

    TODO(Lane A):
        from strands.multiagent import GraphBuilder
        builder = GraphBuilder()
        builder.add_node(ingest_agent, "ingest")
        builder.add_node(triage_agent, "triage")
        ...
        builder.add_edge("ingest", "triage")
        return builder.build()
    """
    raise NotImplementedError("Lane A: build order step A5")
