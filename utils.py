import json
import uuid
from datetime import datetime
from pathlib import Path


API_LOG_FILE = Path("api_requests.log")
SETTINGS_LOG_FILE = Path("settings_changes.log")
SENSITIVE_KEYS = {"api_key", "authorization", "token", "secret", "password"}


def generate_id():
    return str(uuid.uuid4())


def get_current_time():
    return datetime.now().isoformat(timespec="seconds")


def append_api_request_log(url, payload):
    entry = {
        "timestamp": get_current_time(),
        "url": url,
        "payload": payload,
    }
    with API_LOG_FILE.open("a", encoding="utf-8") as file:
        file.write(json.dumps(entry, ensure_ascii=False))
        file.write("\n")


def append_settings_change_log(category, before, after):
    entry = {
        "timestamp": get_current_time(),
        "category": category,
        "before": redact_sensitive_values(before),
        "after": redact_sensitive_values(after),
    }
    with SETTINGS_LOG_FILE.open("a", encoding="utf-8") as file:
        file.write(json.dumps(entry, ensure_ascii=False))
        file.write("\n")


def redact_sensitive_values(value):
    if isinstance(value, dict):
        return {
            key: "***REDACTED***" if str(key).lower() in SENSITIVE_KEYS else redact_sensitive_values(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [redact_sensitive_values(item) for item in value]
    return value


def format_time(iso_string):
    try:
        dt = datetime.fromisoformat(iso_string)
    except (TypeError, ValueError):
        return iso_string or ""
    return dt.strftime("%Y-%m-%d %H:%M")


def truncate_title(text, max_len=20):
    text = text.strip()
    return f"{text[:max_len]}..." if len(text) > max_len else text


def extract_first_line(text, max_len=20):
    first = text.strip().splitlines()[0].strip() if text.strip() else ""
    return truncate_title(first, max_len) if first else "新对话"
