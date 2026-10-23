"""
src/ai_extractor.py
===================
Phase 2: Local AI extraction engine using Ollama.

This module handles all communication with the locally running Ollama
service.  It does NOT perform rule-based extraction — that lives in
src/resume_parser.py.

Design decisions:
- Configuration is kept separate from extraction logic (AIConfig dataclass).
- The AIExtractor class is deliberately thin: send prompt → parse JSON →
  return AIExtractionResult.  Validation against the Pydantic schema is the
  orchestrator's responsibility.
- Mocking this class in tests requires only patching AIExtractor.extract().
- Ollama connectivity is checked lazily — only on the first real call.
"""

from __future__ import annotations

import json
import logging
import os
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

try:
    import dotenv
    _env_path = Path(__file__).resolve().parent.parent / ".env"
    if _env_path.exists():
        dotenv.load_dotenv(dotenv_path=_env_path, override=True)
    else:
        dotenv.load_dotenv(override=True)
except ImportError:
    pass

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# Path to the prompt template, relative to the project root.
_DEFAULT_PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "extract_candidate.txt"

# Default models
DEFAULT_GROQ_MODEL = "openai/gpt-oss-120b"
DEFAULT_OLLAMA_MODEL = "qwen3:4b"
DEFAULT_MODEL = DEFAULT_GROQ_MODEL

FALLBACK_GROQ_MODELS = [
    "openai/gpt-oss-120b",
    "openai/gpt-oss-20b",
    "qwen/qwen3.8-27b",
]

# Default Ollama base URL
DEFAULT_OLLAMA_HOST = "http://localhost:11434"


def list_groq_models(api_key: Optional[str] = None) -> list[str]:
    """Fetch active chat models available to the Groq API key."""
    key = (api_key or os.getenv("GROQ_API_KEY", "")).strip()
    if not key:
        return list(FALLBACK_GROQ_MODELS)
    try:
        import groq

        client = groq.Groq(api_key=key, timeout=10)
        models_resp = client.models.list()
        chat_models: list[str] = []
        for m in models_resp.data:
            mid = m.id.lower()
            if any(w in mid for w in ("whisper", "tts", "embed", "guard", "safeguard", "bge")):
                continue
            chat_models.append(m.id)

        if chat_models:
            preferred = ["openai/gpt-oss-120b", "openai/gpt-oss-20b", "qwen/qwen3.8-27b"]
            ordered: list[str] = [p for p in preferred if p in chat_models]
            for m in chat_models:
                if m not in ordered:
                    ordered.append(m)
            return ordered
    except Exception as exc:  # noqa: BLE001
        logger.warning("Could not list Groq models: %s", exc)
    return list(FALLBACK_GROQ_MODELS)


@dataclass
class AIConfig:
    """Configuration for the AI extraction engine.

    Supports both Groq Cloud API (fast inference) and local Ollama (offline).

    Attributes:
        provider:       "groq", "ollama", or "auto" (auto prefers Groq if key is set).
        model:          Model tag, e.g. ``'openai/gpt-oss-120b'`` or ``'qwen3:4b'``.
        api_key:        Groq API key (optional; defaults to GROQ_API_KEY environment variable).
        host:           Ollama API base URL (used when provider is ollama).
        timeout:        Per-request timeout in seconds.
        max_retries:    Maximum number of retries for transient failures.
        retry_delay:    Seconds to wait between retries.
        temperature:    Sampling temperature (0 = deterministic).
        prompt_path:    Path to the extraction prompt template file.
        think:          Whether to enable chain-of-thought (Ollama Qwen3). Set False to suppress.
        num_predict:    Maximum tokens to generate.
    """

    provider: str = "auto"
    model: str = ""
    api_key: Optional[str] = None
    host: str = DEFAULT_OLLAMA_HOST
    timeout: int = 60
    max_retries: int = 2
    retry_delay: float = 1.0
    temperature: float = 0.0    # deterministic — important for structured output
    prompt_path: Path = field(default_factory=lambda: _DEFAULT_PROMPT_PATH)
    think: bool = False         # Suppress CoT thinking blocks
    num_predict: int = 4096     # Bounded token generation limit (increased for comprehensive extraction)

    def __post_init__(self) -> None:
        if not self.model:
            prov = self.provider
            if prov == "auto":
                prov = "groq" if (self.api_key or os.getenv("GROQ_API_KEY")) else "ollama"
            self.model = DEFAULT_GROQ_MODEL if prov == "groq" else DEFAULT_OLLAMA_MODEL


# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------


@dataclass
class AIExtractionResult:
    """Result of a single AI extraction attempt.

    Attributes:
        success:    True when the model returned parseable JSON.
        data:       Parsed JSON dict (may be partial).  Empty on failure.
        error:      Human-readable failure description.  Empty on success.
        raw:        Raw model response string for debugging.
        model_used: The model tag that produced this result.
        duration_s: Wall-clock time for the Ollama call in seconds.
    """

    success: bool
    data: dict = field(default_factory=dict)
    error: str = ""
    raw: str = ""
    model_used: str = ""
    duration_s: float = 0.0


# ---------------------------------------------------------------------------
# Provider connection helpers
# ---------------------------------------------------------------------------


def check_groq_available(
    api_key: Optional[str] = None, model: str = DEFAULT_GROQ_MODEL
) -> tuple[bool, str]:
    """Return (is_available, message).

    Validates that a Groq API key is present and can reach the Groq API.
    """
    key = (api_key or os.getenv("GROQ_API_KEY", "")).strip()
    if not key:
        return (
            False,
            "Groq API key not provided. Set GROQ_API_KEY or enter your key in the sidebar.",
        )
    try:
        import groq

        client = groq.Groq(api_key=key, timeout=10)
        models_resp = client.models.list()
        active_ids = [m.id for m in models_resp.data]
        if model in active_ids:
            return True, f"Groq API connected; model '{model}' ready."
        chat_models = [
            m for m in active_ids
            if not any(w in m.lower() for w in ("whisper", "tts", "embed", "guard", "safeguard"))
        ]
        best_model = chat_models[0] if chat_models else DEFAULT_GROQ_MODEL
        return True, f"Groq API connected; active model '{best_model}' ready."
    except Exception as exc:  # noqa: BLE001
        err_name = type(exc).__name__
        err_str = str(exc)
        if "AuthenticationError" in err_name or "401" in err_str:
            return (
                False,
                "Invalid Groq API key. Please check your key at https://console.groq.com/keys",
            )
        return False, f"Could not connect to Groq API: {exc}"


def check_ollama_running(host: str = DEFAULT_OLLAMA_HOST) -> tuple[bool, str]:
    """Return (is_running, error_message).

    Does a lightweight HTTP GET to the Ollama root endpoint.
    """
    try:
        import httpx  # bundled with the ollama Python package

        resp = httpx.get(host, timeout=5)
        if resp.status_code == 200:
            return True, ""
        return False, f"Ollama returned HTTP {resp.status_code}"
    except Exception as exc:  # noqa: BLE001
        return False, f"Cannot reach Ollama at {host}: {exc}"


def check_model_available(model: str, host: str = DEFAULT_OLLAMA_HOST) -> tuple[bool, str]:
    """Return (is_available, error_message).

    Lists local models via the Ollama API and checks whether *model* is
    present.
    """
    try:
        import ollama  # type: ignore[import-untyped]

        client = ollama.Client(host=host)
        response = client.list()
        # response.models is a list of ModelInfo objects with a 'model' attribute
        available = [m.model for m in response.models]
        # Strip tags for flexible matching: "qwen3:4b" matches "qwen3:4b"
        if model in available:
            return True, ""
        # Partial match (e.g. "qwen3" matches "qwen3:4b")
        base = model.split(":")[0]
        matches = [m for m in available if m.startswith(base)]
        if matches:
            return True, ""
        return (
            False,
            f"Model '{model}' not found. Available: {available}. "
            f"Run: ollama pull {model}",
        )
    except Exception as exc:  # noqa: BLE001
        return False, f"Could not list Ollama models: {exc}"


# ---------------------------------------------------------------------------
# Prompt loading
# ---------------------------------------------------------------------------


def load_prompt_template(path: Path) -> str:
    """Load the extraction prompt from *path*.

    Raises:
        FileNotFoundError: If the prompt file does not exist.
    """
    if not path.exists():
        raise FileNotFoundError(
            f"Extraction prompt not found at {path}. "
            "Ensure prompts/extract_candidate.txt exists in the project root."
        )
    return path.read_text(encoding="utf-8")


def build_prompt(template: str, resume_text: str) -> str:
    """Substitute {resume_text} into the prompt template."""
    return template.replace("{resume_text}", resume_text)


# ---------------------------------------------------------------------------
# JSON extraction from model response
# ---------------------------------------------------------------------------


def _extract_json_from_response(raw: str) -> tuple[dict, str]:
    """Parse JSON from the model's raw response string.

    Handles:
    - Clean JSON responses.
    - Responses wrapped in ```json ... ``` markdown fences.
    - Responses with leading <think>...</think> blocks (Qwen3 CoT).
    - Trailing text after the JSON object.

    Returns:
        (parsed_dict, error_message)  — error is empty on success.
    """
    text = raw.strip()

    # Strip Qwen3 <think> ... </think> blocks
    import re
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()

    # Strip ```json ... ``` markdown fences
    fence_match = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if fence_match:
        text = fence_match.group(1).strip()

    # Find the outermost { ... } block
    start = text.find("{")
    if start == -1:
        return {}, f"No JSON object found in response: {raw[:200]!r}"

    # Walk to find the matching closing brace
    depth = 0
    end = -1
    for i, ch in enumerate(text[start:], start=start):
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                end = i
                break

    if end == -1:
        return {}, f"Unterminated JSON object in response: {raw[:200]!r}"

    json_str = text[start : end + 1]

    try:
        return json.loads(json_str), ""
    except json.JSONDecodeError:
        # Fallback: clean trailing commas before closing braces/brackets
        cleaned_json = re.sub(r",\s*([}\]])", r"\1", json_str)
        try:
            return json.loads(cleaned_json), ""
        except json.JSONDecodeError as exc:
            return {}, f"JSON parse error: {exc} — fragment: {json_str[:200]!r}"


# ---------------------------------------------------------------------------
# Main extractor class
# ---------------------------------------------------------------------------


class AIExtractor:
    """Sends resume text to Ollama and returns a parsed extraction dict.

    This class is deliberately stateless between calls so it is safe to share
    across a batch.

    Args:
        config: An :class:`AIConfig` instance.  Defaults to ``AIConfig()``.
    """

    def __init__(self, config: Optional[AIConfig] = None) -> None:
        self._config = config or AIConfig()
        self._prompt_template: Optional[str] = None  # loaded lazily

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def extract(self, resume_text: str, filename: str = "") -> AIExtractionResult:
        """Extract candidate data from *resume_text*.

        Args:
            resume_text: Cleaned text from Phase 1.
            filename:    Used only for log messages.

        Returns:
            An :class:`AIExtractionResult`.
        """
        if not resume_text or not resume_text.strip():
            return AIExtractionResult(
                success=False,
                error="Empty resume text — skipping AI extraction.",
                model_used=self._config.model,
            )

        # Load prompt template once
        if self._prompt_template is None:
            try:
                self._prompt_template = load_prompt_template(self._config.prompt_path)
            except FileNotFoundError as exc:
                return AIExtractionResult(
                    success=False,
                    error=str(exc),
                    model_used=self._config.model,
                )

        prompt = build_prompt(self._prompt_template, resume_text)

        last_error = ""
        for attempt in range(1, self._config.max_retries + 2):
            result = self._call_model(prompt, filename, attempt)
            if result.success:
                return result
            last_error = result.error
            if attempt <= self._config.max_retries:
                logger.warning(
                    "[%s] Attempt %d/%d failed: %s — retrying in %.1fs",
                    filename,
                    attempt,
                    self._config.max_retries + 1,
                    last_error,
                    self._config.retry_delay,
                )
                time.sleep(self._config.retry_delay)

        return AIExtractionResult(
            success=False,
            error=f"All {self._config.max_retries + 1} attempts failed. Last: {last_error}",
            model_used=self._config.model,
        )

    def _resolve_provider(self) -> str:
        """Resolve effective provider ('groq' or 'ollama')."""
        if self._config.provider in ("groq", "ollama"):
            return self._config.provider
        # auto: prefer groq if API key is present, else fall back to ollama
        if self._config.api_key or os.getenv("GROQ_API_KEY"):
            return "groq"
        return "ollama"

    def check_availability(self) -> tuple[bool, str]:
        """Check whether the configured AI service is available.

        Returns:
            (ok, message)  — ok is True when everything is ready.
        """
        prov = self._resolve_provider()
        if prov == "groq":
            return check_groq_available(self._config.api_key, self._config.model)
        else:
            running, err = check_ollama_running(self._config.host)
            if not running:
                return False, err

            available, err = check_model_available(self._config.model, self._config.host)
            if not available:
                return False, err

            return True, f"Ollama is running; model '{self._config.model}' is available."

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _call_model(
        self, prompt: str, filename: str, attempt: int
    ) -> AIExtractionResult:
        """Route call to configured provider or test mock."""
        # Support monkey-patched _call_ollama in unit test mocks
        if "_call_ollama" in self.__dict__:
            return self._call_ollama(prompt, filename, attempt)

        prov = self._resolve_provider()
        if prov == "groq":
            return self._call_groq(prompt, filename, attempt)
        return self._call_ollama(prompt, filename, attempt)

    def _call_groq(
        self, prompt: str, filename: str, attempt: int
    ) -> AIExtractionResult:
        """Make one Groq API call and return the result."""
        start = time.monotonic()
        try:
            import groq

            api_key = (self._config.api_key or os.getenv("GROQ_API_KEY", "")).strip()
            if not api_key:
                return AIExtractionResult(
                    success=False,
                    error="Groq API key not provided. Set GROQ_API_KEY or configure in settings.",
                    model_used=self._config.model,
                    duration_s=time.monotonic() - start,
                )

            client = groq.Groq(api_key=api_key, timeout=self._config.timeout)

            system_msg = (
                "You are a meticulous talent intelligence extraction AI. "
                "Your objective is 100% extraction precision: never omit, truncate, or summarize "
                "candidate contact details, work experience, responsibilities, education records, "
                "projects, skills, or links. "
                "Output must strictly adhere to the requested JSON schema without any markdown fences or commentary."
            )

            completion = client.chat.completions.create(
                model=self._config.model,
                messages=[
                    {"role": "system", "content": system_msg},
                    {"role": "user", "content": prompt},
                ],
                response_format={"type": "json_object"},
                temperature=self._config.temperature,
                max_completion_tokens=self._config.num_predict,
            )

            raw = completion.choices[0].message.content or ""
            duration = time.monotonic() - start

            logger.debug(
                "[%s] Groq attempt %d: %.2fs, %d response chars",
                filename, attempt, duration, len(raw)
            )

            parsed, parse_error = _extract_json_from_response(raw)
            if parse_error:
                return AIExtractionResult(
                    success=False,
                    error=parse_error,
                    raw=raw,
                    model_used=self._config.model,
                    duration_s=duration,
                )

            return AIExtractionResult(
                success=True,
                data=parsed,
                raw=raw,
                model_used=self._config.model,
                duration_s=duration,
            )

        except Exception as exc:  # noqa: BLE001
            duration = time.monotonic() - start
            err_name = type(exc).__name__
            err_str = str(exc)

            # Auto-recovery for decommissioned or inaccessible models (e.g. 404 model_not_found)
            if ("NotFoundError" in err_name or "404" in err_str or "model_not_found" in err_str or "model_decommissioned" in err_str) and attempt <= 2:
                try:
                    active_models = list_groq_models(api_key)
                    for candidate in active_models:
                        if candidate != self._config.model:
                            logger.warning(
                                "[%s] Model '%s' unavailable (%s). Auto-migrating to active model '%s'.",
                                filename, self._config.model, err_str, candidate
                            )
                            self._config.model = candidate
                            return self._call_groq(prompt, filename, attempt + 1)
                except Exception as list_exc:
                    logger.debug("Failed auto-model recovery: %s", list_exc)

            if "AuthenticationError" in err_name or "401" in err_str:
                msg = "Invalid Groq API key. Please check your key at https://console.groq.com/keys"
            elif "RateLimitError" in err_name or "429" in err_str:
                msg = "Groq rate limit reached. Please wait a moment before trying again."
            else:
                msg = f"Groq API error: {exc}"

            return AIExtractionResult(
                success=False,
                error=msg,
                model_used=self._config.model,
                duration_s=duration,
            )

    def _call_ollama(
        self, prompt: str, filename: str, attempt: int
    ) -> AIExtractionResult:
        """Make one Ollama API call and return the result."""
        start = time.monotonic()
        try:
            import ollama  # type: ignore[import-untyped]

            client = ollama.Client(host=self._config.host)

            # Use Ollama's chat API with format="json" and think=False.
            # Unlike generate(), chat() with format="json" enforces strict grammar constraints
            # so the model outputs pure JSON directly without wasting time generating hundreds
            # of tokens of reasoning monologue ("Okay, let's see...").
            system_msg = (
                "You are a structured resume data extraction assistant. "
                "Extract candidate information accurately and return ONLY a valid JSON object matching the requested schema. "
                "Never output reasoning, explanation, or markdown fences."
            )
            response = client.chat(
                model=self._config.model,
                messages=[
                    {"role": "system", "content": system_msg},
                    {"role": "user", "content": prompt},
                ],
                format="json",
                think=self._config.think,
                options={
                    "temperature": self._config.temperature,
                    "num_predict": self._config.num_predict,
                },
            )

            raw = ""
            if hasattr(response, "message") and hasattr(response.message, "content"):
                raw = response.message.content or ""
            elif hasattr(response, "response"):
                raw = response.response or ""
            else:
                raw = str(response)

            duration = time.monotonic() - start

            # Fall back to thinking text if response is empty
            thinking_text = ""
            if hasattr(response, "message") and hasattr(response.message, "thinking"):
                thinking_text = response.message.thinking or ""
            elif hasattr(response, "thinking"):
                thinking_text = response.thinking or ""

            if not raw.strip() and thinking_text.strip():
                logger.warning(
                    "[%s] Attempt %d: response was empty but thinking had "
                    "%d chars — falling back to thinking block.",
                    filename, attempt, len(thinking_text),
                )
                raw = thinking_text

            logger.debug(
                "[%s] Attempt %d: %.1fs, %d response chars",
                filename,
                attempt,
                duration,
                len(raw),
            )

            parsed, parse_error = _extract_json_from_response(raw)
            if parse_error:
                return AIExtractionResult(
                    success=False,
                    error=parse_error,
                    raw=raw,
                    model_used=self._config.model,
                    duration_s=duration,
                )

            return AIExtractionResult(
                success=True,
                data=parsed,
                raw=raw,
                model_used=self._config.model,
                duration_s=duration,
            )

        except Exception as exc:  # noqa: BLE001
            duration = time.monotonic() - start
            error_str = str(exc)

            # Classify common Ollama errors
            if "connection refused" in error_str.lower() or "connect" in error_str.lower():
                msg = (
                    f"Cannot connect to Ollama at {self._config.host}. "
                    "Ensure Ollama is running: ollama serve"
                )
            elif "not found" in error_str.lower() or "404" in error_str:
                msg = (
                    f"Model '{self._config.model}' not found. "
                    f"Pull it with: ollama pull {self._config.model}"
                )
            elif "timeout" in error_str.lower():
                msg = f"Ollama request timed out after {self._config.timeout}s."
            else:
                msg = f"Ollama error: {exc}"

            return AIExtractionResult(
                success=False,
                error=msg,
                model_used=self._config.model,
                duration_s=duration,
            )
