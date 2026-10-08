"""Client for any OpenAI-compatible chat API: Groq, OpenAI, OpenRouter, Together, Ollama, vLLM..."""

import httpx

from bob.config import Settings
from bob.llm.base import LLMError, T, parse_json_response, schema_instructions


class OpenAICompatLLM:
    def __init__(
        self,
        base_url: str,
        api_key: str,
        model: str,
        temperature: float = 0.2,
        timeout: float = 90.0,
        client: httpx.Client | None = None,
    ):
        self.url = base_url.rstrip("/") + "/chat/completions"
        self.model = model
        self.temperature = temperature
        self.client = client or httpx.Client(timeout=timeout)
        self.headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}

    def _chat(self, messages: list[dict]) -> str:
        body = {
            "model": self.model,
            "messages": messages,
            "temperature": self.temperature,
            "response_format": {"type": "json_object"},
        }
        try:
            resp = self.client.post(self.url, json=body, headers=self.headers)
        except httpx.HTTPError as e:
            raise LLMError(f"could not reach {self.url}: {e}") from e
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
        reply = self._chat(messages)
        try:
            return parse_json_response(reply, schema)
        except ValueError as first:
            # one repair attempt: show the model its own output and the error
            messages += [
                {"role": "assistant", "content": reply},
                {"role": "user", "content": f"That reply was invalid ({first}). Reply again with corrected JSON only."},
            ]
            reply = self._chat(messages)
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
