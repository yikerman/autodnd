"""LLM client config — reads ``MODEL_ENDPOINT``, ``MODEL_KEY``, ``MODEL_NAME``.

One OpenAI-compatible endpoint serves every agent in the system (arbiter,
characters, narrator, sidebar, bootstrapper). The model name can be overridden
per-agent later if we want tier mixing; for now everyone shares.
"""

from __future__ import annotations

import os

from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider


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
