"""
Async Ollama client wrapper.
-------------------------------
Exposes a clean generate() interface with:
  - Per-request timeout control (local LLMs are slow on CPU)
  - Exponential backoff retry
  - Model name sanitization (handles :tag variants)
  - Graceful degradation on timeout (returns empty string, never raises)
"""
from __future__ import annotations

import asyncio
from typing import Any

import httpx
import structlog

from src.core.config import get_config

logger = structlog.get_logger(__name__)


class OllamaClient:
    def __init__(self, model: str) -> None:
        self._model  = model
        self._config = get_config().ollama
        self._log    = logger.bind(model=model)

    def _sanitize_model(self, model: str) -> str:
        """
        Normalizes model names to the format Ollama expects.
        'mistral:7b-instruct-v0.3-q4_K_M' → 'mistral:latest'
        'mistral' → 'mistral:latest'
        'mistral:latest' → 'mistral:latest'
        """
        base = model.split(":")[0]
        tag  = model.split(":")[1] if ":" in model else "latest"

        # Only known safe tags; everything else falls back to :latest
        safe_tags = {"latest", "mini", "medium", "large"}
        final_tag = tag if tag in safe_tags else "latest"

        return f"{base}:{final_tag}"

    async def generate(
        self,
        prompt: str,
        system: str = "",
        temperature: float | None = None,
    ) -> str:
        """
        Send a prompt to Ollama and return the response text.

        Args:
            prompt: The user prompt
            system: Optional system message
            temperature: Override temperature (defaults to config value)

        Returns:
            Response string, or empty string on unrecoverable failure.
        """
        temp       = temperature if temperature is not None else get_config().agent.temperature
        model_name = self._sanitize_model(self._model)

        payload: dict[str, Any] = {
            "model":  model_name,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": temp,
                "seed":        get_config().agent.seed,
                "num_predict": 2048,   # Cap output to keep responses fast
            },
        }
        if system:
            payload["system"] = system

        # Separate timeouts for connect vs read
        # Read is long (300s) because CPU inference is slow
        timeout = httpx.Timeout(
            connect=10.0,
            read=300.0,
            write=30.0,
            pool=10.0,
        )

        last_error: str = ""
        for attempt in range(self._config.max_retries):
            try:
                async with httpx.AsyncClient(timeout=timeout) as client:
                    resp = await client.post(
                        f"{self._config.base_url}/api/generate",
                        json=payload,
                    )
                    resp.raise_for_status()
                    data = resp.json()
                    text = data.get("response", "")
                    self._log.debug(
                        "ollama.success",
                        model=model_name,
                        attempt=attempt,
                        response_chars=len(text),
                    )
                    return text

            except httpx.ReadTimeout:
                last_error = f"ReadTimeout after 300s (attempt {attempt + 1})"
                self._log.warning(
                    "ollama.timeout",
                    attempt=attempt,
                    model=model_name,
                    prompt_chars=len(prompt),
                )
                if attempt == self._config.max_retries - 1:
                    self._log.error(
                        "ollama.timeout.exhausted",
                        model=model_name,
                        error=last_error,
                    )
                    # Graceful degradation — return empty, let agent handle it
                    return ""
                await asyncio.sleep(2 ** attempt)

            except httpx.HTTPStatusError as exc:
                last_error = f"HTTP {exc.response.status_code}: {exc.response.text[:200]}"
                self._log.warning(
                    "ollama.http_error",
                    attempt=attempt,
                    error=last_error,
                    model=model_name,
                )
                if attempt == self._config.max_retries - 1:
                    raise RuntimeError(
                        f"Ollama HTTP error after {self._config.max_retries} attempts: {last_error}"
                    ) from exc
                await asyncio.sleep(2 ** attempt)

            except httpx.ConnectError as exc:
                last_error = f"Cannot connect to Ollama at {self._config.base_url}"
                self._log.error(
                    "ollama.connect_error",
                    error=last_error,
                    model=model_name,
                )
                raise RuntimeError(
                    f"Ollama not reachable at {self._config.base_url}. "
                    "Is 'ollama serve' running?"
                ) from exc

            except (httpx.HTTPError, httpx.TransportError) as exc:
                last_error = str(exc)
                self._log.warning(
                    "ollama.retry",
                    attempt=attempt,
                    error=last_error,
                    model=model_name,
                )
                if attempt == self._config.max_retries - 1:
                    raise
                await asyncio.sleep(2 ** attempt)

        return ""