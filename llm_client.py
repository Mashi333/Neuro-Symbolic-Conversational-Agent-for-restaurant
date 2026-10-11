"""Pluggable, minimal LLM client used by the intent extractor.

The extractor only talks to a chat-completions-style endpoint. Right now the
only real provider is Ollama (https://ollama.com), which exposes an
OpenAI-compatible endpoint at http://localhost:11434/v1/chat/completions.

Configure via environment variables (or defaults):
    OLLAMA_BASE_URL   default http://localhost:11434
    LLM_MODEL         default llama3.1
    NLU_FORCE_FALLBACK=1   disable the LLM and always use the rule fallback

Tests use MockLLM so no network call is ever made.
"""

from __future__ import annotations

import logging
import os
from typing import Callable

import requests

logger = logging.getLogger(__name__)

DEFAULT_OLLAMA_BASE_URL = "http://localhost:11434"
DEFAULT_OLLAMA_MODEL = "llama3.1"


class LLMError(Exception):
    """The model answered something unusable."""


class LLMUnavailableError(LLMError):
    """The model server could not be reached at all."""


class BaseLLM:
    """A chat model that returns plain text for a list of messages.

    messages: [{"role": "system"|"user"|"assistant", "content": str}, ...]
    """

    model: str

    def complete(
        self,
        messages: list[dict],
        *,
        temperature: float = 0.0,
        json_mode: bool = True,
    ) -> str:
        raise NotImplementedError


class OllamaClient(BaseLLM):
    """Local Ollama server through its OpenAI-compatible endpoint."""

    def __init__(
        self,
        base_url: str | None = None,
        model: str | None = None,
        timeout: float = 120.0,
    ) -> None:
        self.base_url = (
            base_url or os.environ.get("OLLAMA_BASE_URL") or DEFAULT_OLLAMA_BASE_URL
        ).rstrip("/")
        self.model = model or os.environ.get("LLM_MODEL") or DEFAULT_OLLAMA_MODEL
        self.timeout = timeout
        self.endpoint = f"{self.base_url}/v1/chat/completions"

    def complete(
        self,
        messages: list[dict],
        *,
        temperature: float = 0.0,
        json_mode: bool = True,
    ) -> str:
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "stream": False,
        }
        if json_mode:
            # Asks Ollama to constrain the answer to a JSON object.
            payload["response_format"] = {"type": "json_object"}
        try:
            response = requests.post(
                self.endpoint, json=payload, timeout=self.timeout
            )
            response.raise_for_status()
            content = response.json()["choices"][0]["message"]["content"]
        except requests.exceptions.RequestException as error:
            raise LLMUnavailableError(
                f"Ollama not reachable at {self.endpoint} ({error}). "
                "Install Ollama and run `ollama pull llama3.1`, or set "
                "NLU_FORCE_FALLBACK=1 to use the rule-based extractor."
            ) from error
        if not content or not content.strip():
            raise LLMError("empty completion from model")
        return content.strip()


class MockLLM(BaseLLM):
    """Deterministic stand-in for tests.

    responder is called as responder(messages, call_number) and must return
    the raw text the fake model would produce.
    """

    def __init__(self, responder: Callable[[list[dict], int], str], model: str = "mock") -> None:
        self._responder = responder
        self.model = model
        self.calls = 0
        self.last_messages: list[dict] = []
        self.last_kwargs: dict = {}

    def complete(
        self,
        messages: list[dict],
        *,
        temperature: float = 0.0,
        json_mode: bool = True,
    ) -> str:
        self.calls += 1
        self.last_messages = messages
        self.last_kwargs = {"temperature": temperature, "json_mode": json_mode}
        return self._responder(messages, self.calls)


def get_llm_client() -> BaseLLM | None:
    """Return the configured client, or None when the LLM is disabled."""
    if os.environ.get("NLU_FORCE_FALLBACK") == "1":
        return None
    return OllamaClient()