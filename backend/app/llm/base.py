"""Provider-neutral chat interface.

Messages (normalised):
    {"role": "user", "content": str}
    {"role": "assistant", "content": str, "tool_calls": [ToolCall...], "_native": provider-specific replay data}
    {"role": "tool", "tool_call_id": str, "name": str, "content": str, "is_error": bool}
Tools: {"name", "description", "parameters": JSON schema}
"""
from dataclasses import dataclass, field


@dataclass
class ToolCall:
    id: str
    name: str
    args: dict


@dataclass
class ChatResult:
    text: str
    tool_calls: list[ToolCall] = field(default_factory=list)
    native: object = None          # provider-native assistant content, replayed unchanged next turn
    stop: str = "end"              # end | tool_use | refusal | max_tokens
    input_tokens: int = 0
    output_tokens: int = 0
    model: str = ""

    def as_message(self) -> dict:
        return {"role": "assistant", "content": self.text, "tool_calls": self.tool_calls, "_native": self.native}


class LLMError(Exception):
    """A provider call failed. message is safe to show to the user (never contains secrets)."""


class Provider:
    def __init__(self, config: dict, secrets: dict):
        self.config, self.secrets = config or {}, secrets or {}

    def list_models(self) -> list[str]:
        raise NotImplementedError

    def chat(self, model: str, system: str, messages: list[dict], tools: list[dict] | None = None, max_tokens: int = 8000) -> ChatResult:
        raise NotImplementedError


def friendly_error(ex: Exception) -> str:
    """Turn an SDK exception into a short, secret-free message."""
    name = type(ex).__name__
    status = getattr(ex, "status_code", None) or getattr(getattr(ex, "response", None), "status_code", None)
    msg = getattr(ex, "message", None) or str(ex)
    body = getattr(ex, "body", None)
    if isinstance(body, dict):
        err = body.get("error")
        if isinstance(err, dict) and err.get("message"):
            msg = err["message"]
    msg = str(msg).replace("\n", " ")[:400]
    hints = {401: "the key was rejected (check it is correct and active)", 403: "the key does not have access to this model or resource",
             404: "model or endpoint not found", 429: "rate limited or out of credit", 400: "the provider rejected the request"}
    pre = f"{status}, {hints.get(status, name)}: " if status else f"{name}: "
    return pre + msg
