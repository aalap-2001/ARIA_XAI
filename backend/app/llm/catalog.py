"""The provider catalog shown in Settings → AI models, grouped as the product requires."""
from ..config import ENABLE_MOCK_LLM
from .providers import (AnthropicProvider, AzureOpenAIProvider, BedrockProvider, MockProvider, VertexProvider, compat)

KEY = {"name": "api_key", "label": "API key", "secret": True, "required": True}
KEY_OPT = {"name": "api_key", "label": "API key (optional)", "secret": True, "required": False}


def url(default, required=False):
    return {"name": "base_url", "label": "Base URL", "secret": False, "required": required, "placeholder": default, "default": default}


CATALOG = [
    # ------------------------------------------------------------- Open / SaaS
    {"id": "anthropic", "group": "saas", "name": "Anthropic", "blurb": "Claude models", "fields": [KEY],
     "recommended_model": "claude-opus-5-5", "cls": AnthropicProvider, "key_url": "https://console.anthropic.com/settings/keys"},
    {"id": "openai", "group": "saas", "name": "OpenAI", "blurb": "GPT models", "fields": [KEY], "cls": compat(None),
     "key_url": "https://platform.openai.com/api-keys"},
    {"id": "gemini", "group": "saas", "name": "Google Gemini", "blurb": "Gemini via Google AI Studio", "fields": [KEY],
     "cls": compat("https://generativelanguage.googleapis.com/v1beta/openai/"), "key_url": "https://aistudio.google.com/apikey"},
    {"id": "mistral", "group": "saas", "name": "Mistral AI", "blurb": "Mistral & Codestral", "fields": [KEY],
     "cls": compat("https://api.mistral.ai/v1"), "key_url": "https://console.mistral.ai/api-keys"},
    {"id": "groq", "group": "saas", "name": "Groq", "blurb": "Fast open-weight models", "fields": [KEY],
     "cls": compat("https://api.groq.com/openai/v1"), "key_url": "https://console.groq.com/keys"},
    {"id": "deepseek", "group": "saas", "name": "DeepSeek", "blurb": "DeepSeek chat & reasoner", "fields": [KEY],
     "cls": compat("https://api.deepseek.com/v1"), "key_url": "https://platform.deepseek.com/api_keys"},
    {"id": "xai", "group": "saas", "name": "xAI", "blurb": "Grok models", "fields": [KEY],
     "cls": compat("https://api.x.ai/v1"), "key_url": "https://console.x.ai"},
    {"id": "openrouter", "group": "saas", "name": "OpenRouter", "blurb": "Many providers, one key", "fields": [KEY],
     "cls": compat("https://openrouter.ai/api/v1"), "key_url": "https://openrouter.ai/keys"},
    # ------------------------------------------------------------- Enterprise
    {"id": "azure_openai", "group": "enterprise", "name": "Azure OpenAI", "blurb": "Your Azure OpenAI resource",
     "fields": [{"name": "endpoint", "label": "Endpoint", "secret": False, "required": True, "placeholder": "https://my-resource.openai.azure.com"},
                KEY,
                {"name": "deployment", "label": "Deployment name(s)", "secret": False, "required": True, "placeholder": "gpt-prod, gpt-mini"},
                {"name": "api_version", "label": "API version", "secret": False, "required": False, "placeholder": "2024-10-21", "default": "2024-10-21"}],
     "cls": AzureOpenAIProvider},
    {"id": "bedrock", "group": "enterprise", "name": "AWS Bedrock", "blurb": "Claude, Llama, Mistral, Nova on AWS",
     "fields": [{"name": "access_key_id", "label": "Access key ID", "secret": True, "required": True},
                {"name": "secret_access_key", "label": "Secret access key", "secret": True, "required": True},
                {"name": "session_token", "label": "Session token (optional)", "secret": True, "required": False},
                {"name": "region", "label": "Region", "secret": False, "required": True, "placeholder": "us-east-1", "default": "us-east-1"}],
     "cls": BedrockProvider},
    {"id": "vertex", "group": "enterprise", "name": "Google Vertex AI", "blurb": "Claude on Google Cloud",
     "fields": [{"name": "service_account_json", "label": "Service-account JSON", "secret": True, "required": True, "multiline": True},
                {"name": "project_id", "label": "Project ID", "secret": False, "required": False, "placeholder": "taken from the JSON if blank"},
                {"name": "region", "label": "Region", "secret": False, "required": False, "placeholder": "global", "default": "global"}],
     "cls": VertexProvider},
    # ------------------------------------------------------------- Local / self-hosted
    {"id": "ollama", "group": "local", "name": "Ollama", "blurb": "Models running on your machine or server",
     "fields": [url("http://localhost:11434/v1", True), KEY_OPT], "cls": compat("http://localhost:11434/v1", needs_key=False)},
    {"id": "lmstudio", "group": "local", "name": "LM Studio", "blurb": "Local server from LM Studio",
     "fields": [url("http://localhost:1234/v1", True), KEY_OPT], "cls": compat("http://localhost:1234/v1", needs_key=False)},
    {"id": "vllm", "group": "local", "name": "vLLM", "blurb": "Self-hosted vLLM / TGI server",
     "fields": [url("http://localhost:8000/v1", True), KEY_OPT], "cls": compat("http://localhost:8000/v1", needs_key=False)},
    {"id": "openai_compatible", "group": "local", "name": "Any OpenAI-compatible", "blurb": "Gateways, LiteLLM, private endpoints",
     "fields": [url("https://llm.mycompany.internal/v1", True), KEY_OPT], "cls": compat(None, needs_key=False)},
]

if ENABLE_MOCK_LLM:
    CATALOG.append({"id": "mock", "group": "local", "name": "Mock (testing)", "blurb": "Deterministic test provider",
                    "fields": [KEY_OPT], "cls": MockProvider})

BY_ID = {p["id"]: p for p in CATALOG}
GROUPS = [("saas", "Open / SaaS"), ("enterprise", "Enterprise"), ("local", "Local / self-hosted")]


def public_catalog():
    return {"groups": [{"id": g, "label": label, "providers": [{k: v for k, v in p.items() if k != "cls"} for p in CATALOG if p["group"] == g]}
                       for g, label in GROUPS]}


def split_fields(provider_id: str, values: dict) -> tuple[dict, dict]:
    """Split submitted values into non-secret config and secrets, per the catalog."""
    p = BY_ID[provider_id]
    config, secrets = {}, {}
    for f in p["fields"]:
        v = values.get(f["name"])
        if v in (None, ""):
            v = f.get("default") if not f["secret"] else None
        if v in (None, ""):
            continue
        (secrets if f["secret"] else config)[f["name"]] = v.strip() if isinstance(v, str) and f["name"] != "service_account_json" else v
    return config, secrets


def missing_required(provider_id: str, config: dict, secrets: dict) -> list[str]:
    return [f["label"] for f in BY_ID[provider_id]["fields"] if f["required"] and not (config.get(f["name"]) or secrets.get(f["name"]))]


def provider(provider_id: str, config: dict, secrets: dict):
    if provider_id not in BY_ID:
        raise KeyError(provider_id)
    return BY_ID[provider_id]["cls"](config, secrets)
