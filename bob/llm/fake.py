"""A scripted LLM for tests and offline demos."""

from typing import Any

from bob.llm.base import LLMError, T


class FakeLLM:
    """Answers by schema type.

    responses[Schema] may be: a dict/model (returned every time), a list (consumed in order),
    or a callable (system, user) -> dict/model.
    """

    def __init__(self, responses: dict[type, Any] | None = None):
        self.responses: dict[type, Any] = dict(responses or {})
        self.calls: list[tuple[str, str, type]] = []

    def complete_json(self, system: str, user: str, schema: type[T]) -> T:
        self.calls.append((system, user, schema))
        if schema not in self.responses:
            raise LLMError(f"FakeLLM has no response for {schema.__name__}")
        r = self.responses[schema]
        if isinstance(r, list):
            if not r:
                raise LLMError(f"FakeLLM ran out of responses for {schema.__name__}")
            r = r.pop(0)
        if callable(r):
            r = r(system, user)
        return r if isinstance(r, schema) else schema.model_validate(r)
