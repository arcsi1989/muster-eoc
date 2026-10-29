"""The prompt files and their loader: a prompt's version is its file name (sitrep_v2.md is
sitrep-v2). The tasks that own a prompt load it here; providers only send it."""

from pathlib import Path

from app.llm.schemas import Prompt

PROMPTS = Path(__file__).resolve().parent


def load_prompt(
    name: str, max_tokens: int, max_tool_rounds: int = 0, deadline_s: float | None = None
) -> Prompt:
    path = PROMPTS / f"{name}.md"
    version = path.stem.replace("_", "-")
    return Prompt(version, path.read_text(), max_tokens, max_tool_rounds, deadline_s)
