"""LLM agent surface for AutoDND.

All three agents (Director, Narrator, Sidebar) target a single
OpenAI-compatible endpoint configured via env: ``MODEL_ENDPOINT``,
``MODEL_KEY``, ``MODEL_NAME``. See ``.env.example``.
"""

import os
from pathlib import Path

from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider

PROMPTS_DIR = Path(__file__).parent.parent / "prompts"


def model_from_env() -> OpenAIChatModel:
    endpoint = os.getenv("MODEL_ENDPOINT")
    key = os.getenv("MODEL_KEY")
    name = os.getenv("MODEL_NAME")
    if not (endpoint and key and name):
        raise RuntimeError(
            "MODEL_ENDPOINT, MODEL_KEY, MODEL_NAME must all be set (see .env.example)."
        )
    return OpenAIChatModel(
        name, provider=OpenAIProvider(base_url=endpoint, api_key=key)
    )


def load_prompt(name: str) -> str:
    """Load a prompt file from ``autodnd/prompts/``."""
    return (PROMPTS_DIR / name).read_text()
