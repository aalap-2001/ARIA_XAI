"""Provider adapters. Each maps the normalised interface onto one vendor SDK."""
import json

from .base import ChatResult, LLMError, Provider, ToolCall, friendly_error

# Models that accept the server-side refusal fallback (opt-in for current Claude models).
_FALLBACK_MODELS = {"claude-fable-5-2", "claude-fable-5-1", "claude-opus-5-5", "claude-opus-5", "claude-sonnet-5-5"}
TIMEOUT = 120.0


# ====================================================================== Anthropic (+ Vertex)
class AnthropicProvider(Provider):
    def client(self):
        import anthropic
        kw = {"api_key": self.secrets.get("api_key"), "timeout": TIMEOUT, "max_retries": 1}
        if self.config.get("base_url"):
            kw["base_url"] = self.config["base_url"]
        return anthropic.Anthropic(**kw)

    def list_models(self):
        try:
            return [m.id for m in self.client().models.list(limit=100)]
        except Exception as ex:  # noqa: BLE001
            raise LLMError(friendly_error(ex)) from ex

    @staticmethod
    def to_native(messages):
        out = []
        for m in messages:
            if m["role"] == "user":
                out.append({"role": "user", "content": m["content"]})
            elif m["role"] == "assistant":
                if m.get("_native") is not None:
                    out.append({"role": "assistant", "content": m["_native"]})
                else:
                    blocks = ([{"type": "text", "text": m["content"]}] if m.get("content") else []) + [
                        {"type": "tool_use", "id": t.id, "name": t.name, "input": t.args} for t in m.get("tool_calls") or []]
                    out.append({"role": "assistant", "content": blocks or m.get("content", "")})
            elif m["role"] == "tool":
                block = {"type": "tool_result", "tool_use_id": m["tool_call_id"], "content": m["content"]}
                if m.get("is_error"):
                    block["is_error"] = True
                # all tool results answering one assistant turn go back in a single user message
                if out and out[-1]["role"] == "user" and isinstance(out[-1]["content"], list) and out[-1]["content"] and out[-1]["content"][0].get("type") == "tool_result":
                    out[-1]["content"].append(block)
                else:
                    out.append({"role": "user", "content": [block]})
        return out

    def chat(self, model, system, messages, tools=None, max_tokens=8000):
        c = self.client()
        kw = dict(model=model, max_tokens=max_tokens, system=system, messages=self.to_native(messages))
        if tools:
            kw["tools"] = [{"name": t["name"], "description": t["description"], "input_schema": t["parameters"]} for t in tools]
        try:
            if model in _FALLBACK_MODELS and not isinstance(self, VertexProvider):
                resp = c.beta.messages.create(betas=["server-side-fallback-2026-07-01"], fallbacks="default", **kw)
            else:
                resp = c.messages.create(**kw)
        except Exception as ex:  # noqa: BLE001
            raise LLMError(friendly_error(ex)) from ex
        if resp.stop_reason == "refusal":
            return ChatResult(text="The model declined this request.", stop="refusal", model=resp.model,
                              input_tokens=resp.usage.input_tokens, output_tokens=resp.usage.output_tokens)
        text = "".join(b.text for b in resp.content if b.type == "text").strip()
        calls = [ToolCall(b.id, b.name, dict(b.input or {})) for b in resp.content if b.type == "tool_use"]
        return ChatResult(text=text, tool_calls=calls, native=[b.model_dump(exclude_none=True) for b in resp.content],
                          stop="tool_use" if calls else ("max_tokens" if resp.stop_reason == "max_tokens" else "end"),
                          input_tokens=resp.usage.input_tokens, output_tokens=resp.usage.output_tokens, model=resp.model)


class VertexProvider(AnthropicProvider):
    VERTEX_MODELS = ["claude-opus-5-5", "claude-sonnet-5-5", "claude-haiku-5-5", "claude-opus-5", "claude-sonnet-5", "claude-opus-4-8"]

    def client(self):
        import anthropic
        from google.oauth2 import service_account
        try:
            info = json.loads(self.secrets.get("service_account_json") or "{}")
            creds = service_account.Credentials.from_service_account_info(info, scopes=["https://www.googleapis.com/auth/cloud-platform"])
        except Exception as ex:  # noqa: BLE001
            raise LLMError(f"Service-account JSON is not valid: {type(ex).__name__}") from ex
        return anthropic.AnthropicVertex(region=self.config.get("region") or "global",
                                         project_id=self.config.get("project_id") or info.get("project_id"),
                                         credentials=creds, timeout=TIMEOUT, max_retries=1)

    def list_models(self):
        self.client()  # validates the credentials parse
        return list(self.VERTEX_MODELS)


# ====================================================================== OpenAI-compatible family
class OpenAICompatProvider(Provider):
    default_base_url: str | None = None
    needs_key = True

    def client(self):
        import openai
        key = self.secrets.get("api_key") or ("not-needed" if not self.needs_key else None)
        if not key:
            raise LLMError("An API key is required")
        return openai.OpenAI(api_key=key, base_url=self.config.get("base_url") or self.default_base_url, timeout=TIMEOUT, max_retries=1)

    def list_models(self):
        try:
            return sorted(m.id for m in self.client().models.list())
        except LLMError:
            raise
        except Exception as ex:  # noqa: BLE001
            raise LLMError(friendly_error(ex)) from ex

    @staticmethod
    def to_native(system, messages):
        out = [{"role": "system", "content": system}] if system else []
        for m in messages:
            if m["role"] == "assistant":
                msg = {"role": "assistant", "content": m.get("content") or None}
                if m.get("tool_calls"):
                    msg["tool_calls"] = [{"id": t.id, "type": "function", "function": {"name": t.name, "arguments": json.dumps(t.args)}}
                                         for t in m["tool_calls"]]
                out.append(msg)
            elif m["role"] == "tool":
                out.append({"role": "tool", "tool_call_id": m["tool_call_id"], "content": m["content"]})
            else:
                out.append({"role": "user", "content": m["content"]})
        return out

    def _model_arg(self, model):
        return model

    def chat(self, model, system, messages, tools=None, max_tokens=8000):
        c = self.client()
        kw = dict(model=self._model_arg(model), messages=self.to_native(system, messages))
        if tools:
            kw["tools"] = [{"type": "function", "function": {"name": t["name"], "description": t["description"], "parameters": t["parameters"]}} for t in tools]
        try:
            resp = c.chat.completions.create(**kw)
        except Exception as ex:  # noqa: BLE001
            raise LLMError(friendly_error(ex)) from ex
        ch = resp.choices[0]
        msg = ch.message
        calls = []
        for tc in msg.tool_calls or []:
            try:
                args = json.loads(tc.function.arguments or "{}")
            except json.JSONDecodeError:
                args = {"_invalid_json": tc.function.arguments}
            calls.append(ToolCall(tc.id, tc.function.name, args))
        u = resp.usage
        return ChatResult(text=(msg.content or "").strip(), tool_calls=calls, stop="tool_use" if calls else ("max_tokens" if ch.finish_reason == "length" else "end"),
                          input_tokens=getattr(u, "prompt_tokens", 0) or 0, output_tokens=getattr(u, "completion_tokens", 0) or 0,
                          model=getattr(resp, "model", model))


def compat(base_url: str | None, needs_key=True):
    return type("Compat", (OpenAICompatProvider,), {"default_base_url": base_url, "needs_key": needs_key})


class AzureOpenAIProvider(OpenAICompatProvider):
    def client(self):
        import openai
        if not self.secrets.get("api_key") or not self.config.get("endpoint"):
            raise LLMError("Azure OpenAI needs an endpoint and an API key")
        return openai.AzureOpenAI(api_key=self.secrets["api_key"], azure_endpoint=self.config["endpoint"],
                                  api_version=self.config.get("api_version") or "2024-10-21", timeout=TIMEOUT, max_retries=1)

    def list_models(self):
        dep = (self.config.get("deployment") or "").strip()
        if not dep:
            raise LLMError("Enter the deployment name to use (Azure deployments are not listable with a data-plane key)")
        return [d.strip() for d in dep.split(",") if d.strip()]


# ====================================================================== AWS Bedrock (Converse API)
class BedrockProvider(Provider):
    def _session(self):
        import boto3
        if not (self.secrets.get("access_key_id") and self.secrets.get("secret_access_key")):
            raise LLMError("AWS Bedrock needs an access key ID and secret access key")
        return boto3.Session(aws_access_key_id=self.secrets["access_key_id"], aws_secret_access_key=self.secrets["secret_access_key"],
                             aws_session_token=self.secrets.get("session_token") or None, region_name=self.config.get("region") or "us-east-1")

    def list_models(self):
        try:
            b = self._session().client("bedrock")
            ids = [m["modelId"] for m in b.list_foundation_models(byOutputModality="TEXT")["modelSummaries"]
                   if "ON_DEMAND" in (m.get("inferenceTypesSupported") or [])]
            try:
                ids += [p["inferenceProfileId"] for p in b.list_inference_profiles(maxResults=100).get("inferenceProfileSummaries", [])]
            except Exception:  # noqa: BLE001
                pass
            return sorted(set(ids))
        except LLMError:
            raise
        except Exception as ex:  # noqa: BLE001
            raise LLMError(friendly_error(ex)) from ex

    @staticmethod
    def to_native(messages):
        out = []
        for m in messages:
            if m["role"] == "user":
                out.append({"role": "user", "content": [{"text": m["content"]}]})
            elif m["role"] == "assistant":
                blocks = ([{"text": m["content"]}] if m.get("content") else []) + [
                    {"toolUse": {"toolUseId": t.id, "name": t.name, "input": t.args}} for t in m.get("tool_calls") or []]
                out.append({"role": "assistant", "content": blocks or [{"text": "."}]})
            elif m["role"] == "tool":
                block = {"toolResult": {"toolUseId": m["tool_call_id"], "content": [{"text": m["content"]}], "status": "error" if m.get("is_error") else "success"}}
                if out and out[-1]["role"] == "user" and "toolResult" in out[-1]["content"][0]:
                    out[-1]["content"].append(block)
                else:
                    out.append({"role": "user", "content": [block]})
        return out

    def chat(self, model, system, messages, tools=None, max_tokens=8000):
        rt = self._session().client("bedrock-runtime")
        kw = dict(modelId=model, messages=self.to_native(messages), inferenceConfig={"maxTokens": max_tokens})
        if system:
            kw["system"] = [{"text": system}]
        if tools:
            kw["toolConfig"] = {"tools": [{"toolSpec": {"name": t["name"], "description": t["description"], "inputSchema": {"json": t["parameters"]}}} for t in tools]}
        try:
            r = rt.converse(**kw)
        except Exception as ex:  # noqa: BLE001
            raise LLMError(friendly_error(ex)) from ex
        content = r["output"]["message"]["content"]
        text = "".join(b.get("text", "") for b in content).strip()
        calls = [ToolCall(b["toolUse"]["toolUseId"], b["toolUse"]["name"], b["toolUse"].get("input") or {}) for b in content if "toolUse" in b]
        return ChatResult(text=text, tool_calls=calls, stop="tool_use" if calls else "end",
                          input_tokens=r.get("usage", {}).get("inputTokens", 0), output_tokens=r.get("usage", {}).get("outputTokens", 0), model=model)


# ====================================================================== Mock (tests / demos only)
class MockProvider(Provider):
    """Deterministic provider for automated tests. Enabled only with ARIAX_ENABLE_MOCK_LLM=1."""
    script = None  # tests may assign a callable(system, messages, tools) -> ChatResult

    def list_models(self):
        if self.secrets.get("api_key") == "bad-key":
            raise LLMError("401, the key was rejected (check it is correct and active): invalid x-api-key")
        return ["mock-large", "mock-small"]

    def chat(self, model, system, messages, tools=None, max_tokens=8000):
        if self.secrets.get("api_key") == "bad-key":
            raise LLMError("401, the key was rejected (check it is correct and active): invalid x-api-key")
        if MockProvider.script:
            return MockProvider.script(system, messages, tools)
        return ChatResult(text="Mock model is reachable.", model=model, input_tokens=10, output_tokens=5)
