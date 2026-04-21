import json
import os
from copy import deepcopy
from pathlib import Path


DEFAULT_API_URL = "https://api.deepseek.com/v1/chat/completions"
DEFAULT_MODEL = "deepseek-chat"
DEFAULT_PROXY_URL = os.getenv("DEEPSEEK_PROXY", "").strip()
SETTINGS_FILE = Path("settings.json")
DEFAULT_FEATURE_SETTINGS = {
    "max_tokens": 4096,
    "temperature": 1.0,
    "top_p": 1.0,
    "frequency_penalty": 0.0,
    "presence_penalty": 0.0,
    "stop": [],
    "response_format": {"type": "text"},
    "logprobs": False,
    "top_logprobs": None,
    "tools": [],
    "tool_choice": None,
    "prefix": False,
    "reasoning_content": False,
}


def merge_feature_settings(saved_settings=None):
    merged = deepcopy(DEFAULT_FEATURE_SETTINGS)
    if isinstance(saved_settings, dict):
        for key in merged:
            if key in saved_settings:
                merged[key] = saved_settings[key]
    return merged


def load_runtime_config():
    config = {
        "api_key": os.getenv("DEEPSEEK_API_KEY", ""),
        "api_url": os.getenv("DEEPSEEK_API_URL", DEFAULT_API_URL),
        "proxy_url": DEFAULT_PROXY_URL,
        "model": os.getenv("DEEPSEEK_MODEL", DEFAULT_MODEL),
        "feature_settings": merge_feature_settings(),
        "help_doc_path": "",
    }

    if SETTINGS_FILE.exists():
        try:
            with SETTINGS_FILE.open("r", encoding="utf-8") as file:
                saved = json.load(file)
        except (OSError, json.JSONDecodeError):
            saved = {}

        config["api_key"] = saved.get("api_key", config["api_key"])
        config["api_url"] = saved.get("api_url", config["api_url"])
        config["proxy_url"] = saved.get("proxy_url", config["proxy_url"])
        config["model"] = saved.get("model", config["model"])
        config["feature_settings"] = merge_feature_settings(saved.get("feature_settings"))
        config["help_doc_path"] = saved.get("help_doc_path", config["help_doc_path"])

    return config


def save_runtime_config(api_key, api_url, model=DEFAULT_MODEL, feature_settings=None, proxy_url="", help_doc_path=""):
    payload = {
        "api_key": api_key.strip(),
        "api_url": api_url.strip() or DEFAULT_API_URL,
        "proxy_url": (proxy_url or "").strip(),
        "model": model.strip() or DEFAULT_MODEL,
        "feature_settings": merge_feature_settings(feature_settings),
        "help_doc_path": (help_doc_path or "").strip(),
    }
    with SETTINGS_FILE.open("w", encoding="utf-8") as file:
        json.dump(payload, file, ensure_ascii=False, indent=2)
