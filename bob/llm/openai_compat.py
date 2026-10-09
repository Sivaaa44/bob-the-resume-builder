"""Client for any OpenAI-compatible chat API: Groq, OpenAI, OpenRouter, Together, Ollama, vLLM..."""

import re
import time

import httpx

from bob.config import Settings
from bob.llm.base import LLMError, T, parse_json_response, schema_instructions


MAX_RATE_LIMIT_WAIT = 65.0  # seconds; free tiers reset per minute


def retry_after_seconds(resp: httpx.Response) -> float | None:
    """How long a 429 asks us to wait: Retry-After header, or "try again in 26.2s" in the body."""
    header = resp.headers.get("retry-after")
    if header:
        try:
            return float(header)
        except ValueError:
            pass
    m = re.search(r"try again in (?:(\d+)m)?([\d.]+)s", resp.text)
    if m:
        return int(m.group(1) or 0) * 60 + float(m.group(2))
    return None


class _JSONModeRejected(LLMError):
    """The provider's JSON mode refused the model's output (Groq: json_validate_failed)."""


class OpenAICompatLLM:
    def __init__(
        self,
        base_url: str,
        api_key: str,
        model: str,
        temperature: float = 0.2,
        timeout: float = 90.0,
        client: httpx.Client | None = None,
        sleep=time.sleep,
        rate_limit_retries: int = 2,
    ):
        self.sleep = sleep
        self.rate_limit_retries = rate_limit_retries
        self.url = base_url.rstrip("/") + "/chat/completions"
        self.model = model
        self.temperature = temperature
        self.client = client or httpx.Client(timeout=timeout)
        self.headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}

    def _chat(self, messages: list[dict], json_mode: bool = True) -> str:
        body = {"model": self.model, "messages": messages, "temperature": self.temperature}
        if json_mode:
            body["response_format"] = {"type": "json_object"}
        for attempt in range(self.rate_limit_retries + 1):
            try:
                resp = self.client.post(self.url, json=body, headers=self.headers)
            except httpx.HTTPError as e:
                raise LLMError(f"could not reach {self.url}: {e}") from e
            if resp.status_code != 429 or attempt == self.rate_limit_retries:
                break
            # free tiers limit tokens per minute; waiting the requested time usually clears it
            wait = retry_after_seconds(resp)
            if wait is None or wait > MAX_RATE_LIMIT_WAIT:
                break
            self.sleep(wait + 0.5)
        if resp.status_code == 400 and json_mode and "json_validate_failed" in resp.text:
            raise _JSONModeRejected(resp.text[:500])
        if resp.status_code != 200:
            raise LLMError(f"LLM API returned {resp.status_code}: {resp.text[:500]}")
        try:
            return resp.json()["choices"][0]["message"]["content"] or ""
        except (KeyError, IndexError, ValueError) as e:
            raise LLMError(f"unexpected LLM API response: {resp.text[:500]}") from e

    def complete_json(self, system: str, user: str, schema: type[T]) -> T:
        messages = [
            {"role": "system", "content": f"{system}\n\n{schema_instructions(schema)}"},
            {"role": "user", "content": user},
        ]
        try:
            reply = self._chat(messages)
        except _JSONModeRejected:
            # the provider refused malformed JSON; ask again without JSON mode and parse it ourselves
            reply = self._chat(messages, json_mode=False)
        try:
            return parse_json_response(reply, schema)
        except ValueError as first:
            # one repair attempt: show the model its own output and the error
            messages += [
                {"role": "assistant", "content": reply},
                {"role": "user", "content": f"That reply was invalid ({first}). Reply again with corrected JSON only."},
            ]
            reply = self._chat(messages, json_mode=False)
            try:
                return parse_json_response(reply, schema)
            except ValueError as second:
                raise LLMError(f"model did not return valid {schema.__name__} after a retry: {second}") from second


def get_llm(settings: Settings | None = None) -> OpenAICompatLLM:
    settings = settings or Settings()
    local = any(h in settings.llm_base_url for h in ("localhost", "127.0.0.1"))
    if not settings.llm_api_key and not local:
        raise LLMError(
            "No LLM API key. Set BOB_LLM_API_KEY (or GROQ_API_KEY) in .env — see .env.example."
        )
    return OpenAICompatLLM(settings.llm_base_url, settings.llm_api_key, settings.llm_model)
