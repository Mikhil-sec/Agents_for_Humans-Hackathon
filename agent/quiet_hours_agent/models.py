"""Model selection.

`live` gets Claude Sonnet 4.5 on Bedrock. `mock` gets a scripted stub, because
**mock mode must work with zero credentials** — that is how a hackathon judge
runs us, and it is a hard rule in the root `AGENTS.md`.

The scripted model is the mock-mode *reasoning*, not a test double: `make demo`
runs on it, and it drives every node of the A5 graph. The per-node scripts live
in `mock_reasoning.py`; this module only knows how to walk one.
"""

from __future__ import annotations

import json
import os
import uuid
from collections.abc import AsyncIterable
from dataclasses import dataclass, field
from typing import Any

from strands.models.model import Model
from strands.types.content import Messages
from strands.types.streaming import StreamEvent
from strands.types.tools import ToolSpec

DEFAULT_BEDROCK_MODEL_ID = "us.anthropic.claude-sonnet-4-5-20250929-v1:0"


@dataclass
class ScriptedStep:
    """One tool call the scripted model should make."""

    tool_name: str
    tool_input: dict[str, Any]
    tool_use_id: str = ""

    def resolved_id(self, index: int, nonce: str = "") -> str:
        """The `toolUseId` for this step.

        **Tool use ids must be unique across the whole run, not just within one
        agent.** In a graph the specialists execute in parallel and share a single
        `PolicyHook`, which keys its pending-call table — and every derived
        `decision_id` — on this id. Numbering by script position alone gave every
        node's first step the same id, so one node's audit entry silently
        overwrote another's and two unrelated actions could collide on one
        decision card.

        Hence the per-model `nonce`. A real provider guarantees uniqueness
        itself; the scripted model has to do it deliberately.
        """
        if self.tool_use_id:
            return self.tool_use_id
        return f"tooluse_qh_{nonce}_{index}" if nonce else f"tooluse_qh_{index}"


def _tool_result_count(messages: Messages) -> int:
    """How many tool results are already in the conversation.

    Used as the script cursor instead of instance state, so the model resumes at
    the right step after a process restart — the conversation is rehydrated from
    the session, but a fresh `ScriptedModel` object is not.
    """
    return sum(
        1
        for message in messages
        for block in message.get("content", [])
        if isinstance(block, dict) and "toolResult" in block
    )


@dataclass
class ScriptedModel(Model):
    """Walks a fixed list of tool calls, then closes with a sentence.

    Deterministic and credential-free. Not a mock in the test-double sense — it
    is the mock-mode *model provider*, and `make demo` runs on it.
    """

    script: list[ScriptedStep] = field(default_factory=list)
    final_text: str = "Nothing else needs doing."
    config: dict[str, Any] = field(default_factory=lambda: {"model_id": "quiet-hours-scripted"})

    nonce: str = field(default_factory=lambda: uuid.uuid4().hex[:8])
    """Distinguishes this model's generated tool use ids from every other node's.

    One `ScriptedModel` is built per agent, so this is effectively a node id — see
    `ScriptedStep.resolved_id` for why sharing ids across parallel nodes corrupts
    the audit trail.
    """

    def update_config(self, **model_config: Any) -> None:
        self.config.update(model_config)

    def get_config(self) -> dict[str, Any]:
        return self.config

    def structured_output(
        self, output_model: Any, prompt: Any, system_prompt: Any = None, **kwargs: Any
    ) -> Any:
        # The `structured_output_model=` path used by the graph does *not* come
        # through here — Strands injects a tool named after the schema class and
        # the script calls it by name (see `mock_reasoning`). This is only the
        # direct `agent.structured_output(...)` entry point.
        raise NotImplementedError(
            "Direct structured_output() needs a real model. Run with "
            "QH_PROVIDER_MODE=live, or drive it through structured_output_model."
        )

    async def stream(
        self,
        messages: Messages,
        tool_specs: list[ToolSpec] | None = None,
        system_prompt: str | None = None,
        **kwargs: Any,
    ) -> AsyncIterable[StreamEvent]:
        index = _tool_result_count(messages)

        yield {"messageStart": {"role": "assistant"}}

        if index < len(self.script):
            step = self.script[index]
            yield {
                "contentBlockStart": {
                    "start": {
                        "toolUse": {
                            "toolUseId": step.resolved_id(index, self.nonce),
                            "name": step.tool_name,
                        }
                    }
                }
            }
            yield {
                "contentBlockDelta": {"delta": {"toolUse": {"input": json.dumps(step.tool_input)}}}
            }
            yield {"contentBlockStop": {}}
            stop_reason = "tool_use"
        else:
            yield {"contentBlockStart": {"start": {}}}
            yield {"contentBlockDelta": {"delta": {"text": self.final_text}}}
            yield {"contentBlockStop": {}}
            stop_reason = "end_turn"

        yield {"messageStop": {"stopReason": stop_reason}}
        yield {
            "metadata": {
                "usage": {"inputTokens": 0, "outputTokens": 0, "totalTokens": 0},
                "metrics": {"latencyMs": 0},
            }
        }


def build_model(
    mode: str | None = None,
    *,
    script: list[ScriptedStep] | None = None,
    final_text: str | None = None,
) -> Model:
    """Bedrock in live mode, the scripted stub in mock mode.

    Args:
        mode: `live` or `mock`. Defaults to `QH_PROVIDER_MODE`, then `mock`.
        script: The tool calls the scripted model should walk. Ignored in live mode.
        final_text: What the scripted model says once the script is spent. This is
            the node's output text, so in a graph it is what the next node reads.
    """
    resolved = (mode or os.environ.get("QH_PROVIDER_MODE") or "mock").strip().casefold()

    if resolved == "live":
        from strands.models import BedrockModel

        # `QH_MODEL_ID` is the name the root `.env.example` documents and the one
        # a deployed runtime will actually have set; `QH_BEDROCK_MODEL_ID` is the
        # name this file used first. Reading both means a live deploy picks up the
        # configured model instead of silently falling back to the default —
        # which would look like it worked, on the wrong model, at the wrong price.
        return BedrockModel(
            model_id=(
                os.environ.get("QH_MODEL_ID")
                or os.environ.get("QH_BEDROCK_MODEL_ID")
                or DEFAULT_BEDROCK_MODEL_ID
            ),
            region_name=os.environ.get("AWS_REGION", "us-east-1"),
        )

    model = ScriptedModel(script=list(script or []))
    if final_text is not None:
        model.final_text = final_text
    return model
