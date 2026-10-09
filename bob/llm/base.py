"""The one interface the rest of Bob uses to talk to a language model."""

import json
import re
from typing import Protocol, TypeVar

from pydantic import BaseModel, ValidationError

T = TypeVar("T", bound=BaseModel)


class LLMError(RuntimeError):
    pass


class Usage(BaseModel):
    """Token counts as reported by the provider (summed over calls, retries included)."""

    prompt_tokens: int = 0
    completion_tokens: int = 0
    calls: int = 0

    @property
    def total(self) -> int:
        return self.prompt_tokens + self.completion_tokens

    def add(self, other: "Usage") -> "Usage":
        return Usage(prompt_tokens=self.prompt_tokens + other.prompt_tokens,
                     completion_tokens=self.completion_tokens + other.completion_tokens,
                     calls=self.calls + other.calls)

    def minus(self, other: "Usage") -> "Usage":
        return Usage(prompt_tokens=self.prompt_tokens - other.prompt_tokens,
                     completion_tokens=self.completion_tokens - other.completion_tokens,
                     calls=self.calls - other.calls)


class LLM(Protocol):
    usage: Usage  # running total for this client; the pipeline diffs it per step

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


def schema_sketch(schema: type[BaseModel]) -> str:
    """A compact example of the JSON shape, e.g. {"items": [{"kind": "rewrite|add", "ids": ["string"]}]}.

    Models follow a concrete shape far more reliably than a raw JSON Schema with $refs."""
    full = schema.model_json_schema()
    defs = full.get("$defs", {})

    def walk(node: dict):
        if "$ref" in node:
            return walk(defs[node["$ref"].split("/")[-1]])
        if "anyOf" in node:  # Optional[X] → X (null allowed)
            options = [o for o in node["anyOf"] if o.get("type") != "null"]
            return walk(options[0]) if options else None
        if "enum" in node:
            return "|".join(str(v) for v in node["enum"])
        kind = node.get("type")
        if kind == "object":
            return {k: walk(v) for k, v in node.get("properties", {}).items()}
        if kind == "array":
            return [walk(node.get("items", {}))]
        return {"integer": 0, "number": 0.0, "boolean": True}.get(kind, "string")

    return json.dumps(walk(full))


def schema_instructions(schema: type[BaseModel]) -> str:
    return (
        "Reply with one JSON object and nothing else (no markdown, no commentary). Use exactly this shape; "
        "\"a|b\" means one of those values, lists may have any number of items:\n" + schema_sketch(schema)
    )
