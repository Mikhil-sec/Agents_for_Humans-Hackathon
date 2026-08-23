"""A deterministic, credential-free Model for the A1 spike.

The spike is testing the *interrupt mechanic*, not the model. A real
`BedrockModel` would add network flakiness, AWS credentials and non-determinism
to an experiment whose whole point is a clean yes/no answer — and mock mode has
to work with zero credentials anyway (root `AGENTS.md`, rule 3).

So this emits a hard-coded tool call on the first turn and a hard-coded sentence
once it sees a tool result. Nothing more.

Not production code. When A5 wires the real graph this is replaced by
`BedrockModel`; the hook and session behaviour it exercises stay the same.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterable
from typing import Any

from strands.models.model import Model
from strands.types.content import Messages
from strands.types.streaming import StreamEvent
from strands.types.tools import ToolSpec


def _has_tool_result(messages: Messages) -> bool:
    """True once the conversation contains a tool result block.

    That is our cue that the tool has run (or been cancelled) and the turn should
    be closed out with text rather than another tool call.
    """
    return any(
        "toolResult" in block
        for message in messages
        for block in message.get("content", [])
        if isinstance(block, dict)
    )


class ScriptedModel(Model):
    """Emits one fixed tool call, then one fixed sentence. No network, no creds."""

    def __init__(
        self,
        *,
        tool_name: str,
        tool_input: dict[str, Any],
        tool_use_id: str,
        final_text: str = "Done.",
    ) -> None:
        self.tool_name = tool_name
        self.tool_input = tool_input
        self.tool_use_id = tool_use_id
        self.final_text = final_text
        self._config: dict[str, Any] = {"model_id": "scripted-spike-model"}

    # -- Model ABC ---------------------------------------------------------

    def update_config(self, **model_config: Any) -> None:
        self._config.update(model_config)

    def get_config(self) -> dict[str, Any]:
        return self._config

    def structured_output(
        self, output_model: Any, prompt: Any, system_prompt: Any = None, **kwargs: Any
    ) -> Any:
        raise NotImplementedError("ScriptedModel is for the A1 interrupt spike only.")

    async def stream(
        self,
        messages: Messages,
        tool_specs: list[ToolSpec] | None = None,
        system_prompt: str | None = None,
        **kwargs: Any,
    ) -> AsyncIterable[StreamEvent]:
        """Turn 1: call the tool. Turn 2 (after a tool result): say the sentence."""
        yield {"messageStart": {"role": "assistant"}}

        if _has_tool_result(messages):
            yield {"contentBlockStart": {"start": {}}}
            yield {"contentBlockDelta": {"delta": {"text": self.final_text}}}
            yield {"contentBlockStop": {}}
            stop_reason = "end_turn"
        else:
            yield {
                "contentBlockStart": {
                    "start": {"toolUse": {"toolUseId": self.tool_use_id, "name": self.tool_name}}
                }
            }
            yield {
                "contentBlockDelta": {"delta": {"toolUse": {"input": json.dumps(self.tool_input)}}}
            }
            yield {"contentBlockStop": {}}
            stop_reason = "tool_use"

        yield {"messageStop": {"stopReason": stop_reason}}
        yield {
            "metadata": {
                "usage": {"inputTokens": 0, "outputTokens": 0, "totalTokens": 0},
                "metrics": {"latencyMs": 0},
            }
        }
