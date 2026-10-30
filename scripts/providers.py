"""Provider identity and cost boundaries; keys never cross provider endpoints."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load_providers():
    return json.loads((ROOT / "data/model-providers.json").read_text(encoding="utf-8"))["providers"]


PROVIDERS = load_providers()


def provider_settings(provider, environ):
    info = PROVIDERS.get(provider)
    if info is None:
        raise ValueError("Unknown or retired provider")
    # Generic settings belong to the existing Groq key only, not every fallback.
    base = info["base_url"]
    model = environ.get(f"OPENGSA_{provider.upper()}_MODEL", "") or info["model"]
    if provider == "groq":
        base = environ.get("OPENGSA_MODEL_BASE_URL", "") or base
        model = environ.get("OPENGSA_MODEL_NAME", "") or model
    if provider == "siliconflow":
        region = environ.get("OPENGSA_SILICONFLOW_REGION", "unknown")
        if region not in ("cn", "com"):
            raise ValueError("SiliconFlow region must be confirmed (cn or com)")
        base = f"https://api.siliconflow.{region}/v1"
    if base not in info.get("allowed_base_urls", [info["base_url"]]):
        raise ValueError("Provider endpoint is not allowlisted")
    key_env = "OPENGSA_SELECTED_API_KEY" if environ.get("OPENGSA_SELECTED_API_KEY", "").strip() else next((k for k in info["key_envs"] if environ.get(k, "").strip()), info["key_envs"][0])
    return base, model, key_env
