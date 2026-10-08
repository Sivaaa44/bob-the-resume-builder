"""The one interface the rest of Bob uses to talk to a language model."""

import json
import re
from typing import Protocol, TypeVar

from pydantic import BaseModel, ValidationError

T = TypeVar("T", bound=BaseModel)


class LLMError(RuntimeError):
    pass


class LLM(Protocol):
    def complete_json(self, system: str, user: str, schema: type[T]) -> T:
        """Ask for a JSON object matching `schema`; return it validated."""
        ...


def parse_json_response(text: str, schema: type[T]) -> T:
    """Extract the JSON object from a model reply (tolerating ``` fences / chatter) and validate it.

    Raises ValueError with a message that can be shown back to the model for a repair attempt.
    """
    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip())
    start, end = cleaned.find("{"), cleaned.rfind("}")
    if start < 0 or end < start:
        raise ValueError("no JSON object found in the reply")
    try:
        data = json.loads(cleaned[start : end + 1])
    except json.JSONDecodeError as e:
        raise ValueError(f"invalid JSON: {e}") from e
    try:
        return schema.model_validate(data)
    except ValidationError as e:
        raise ValueError(f"JSON does not match the schema: {e}") from e


def schema_instructions(schema: type[BaseModel]) -> str:
    return (
        "Reply with a single JSON object and nothing else. It must validate against this JSON Schema:\n"
        + json.dumps(schema.model_json_schema(), separators=(",", ":"))
    )
