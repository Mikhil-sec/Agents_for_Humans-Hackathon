"""Loader for the node system prompts.

Prompts are `.md` files in this package, never inline Python strings
(`agent/AGENTS.md`, rule 4). They are iterated on constantly, they review far
better as a diff than as an escaped triple-quoted string, and a non-engineer can
edit one without touching Python.

Loaded once and cached: a graph builds five agents per run and the files never
change mid-process.
"""

from __future__ import annotations

from functools import cache
from pathlib import Path

PROMPT_DIR = Path(__file__).parent


class PromptNotFoundError(FileNotFoundError):
    """A node asked for a prompt file that does not exist.

    Raised eagerly at graph construction rather than left to surface as an empty
    system prompt, which would look like a subtly badly behaved agent instead of
    a missing file.
    """


@cache
def load_prompt(name: str) -> str:
    """Return the system prompt for one node, by file stem.

    Args:
        name: The file stem, e.g. `"triage"` for `prompts/triage.md`.
    """
    path = PROMPT_DIR / f"{name}.md"
    if not path.is_file():
        available = sorted(p.stem for p in PROMPT_DIR.glob("*.md") if p.stem != "README")
        raise PromptNotFoundError(f"no prompt {name!r} in {PROMPT_DIR} (have: {available})")
    return path.read_text(encoding="utf-8").strip()


__all__ = ["PROMPT_DIR", "PromptNotFoundError", "load_prompt"]
