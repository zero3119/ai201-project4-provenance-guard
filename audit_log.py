import json
from pathlib import Path

LOG_PATH = Path("audit_log.json")


def _load_log_entries():
    if not LOG_PATH.exists():
        return []

    try:
        with LOG_PATH.open("r", encoding="utf-8") as file:
            data = json.load(file)
    except json.JSONDecodeError:
        return []

    if isinstance(data, list):
        return data

    return []


def _save_log_entries(entries):
    with LOG_PATH.open("w", encoding="utf-8") as file:
        json.dump(entries, file, indent=2)


def add_log_entry(entry):
    entries = _load_log_entries()
    entries.append(entry)
    _save_log_entries(entries)


def get_recent_log_entries(limit=10):
    entries = _load_log_entries()
    return entries[-limit:]


def find_submission(content_id):
    """Return the most recent submission entry with this content_id."""
    entries = _load_log_entries()
    for entry in reversed(entries):
        if entry.get("event_type") == "submission" and entry.get("content_id") == content_id:
            return entry
    return None


def mark_submission_under_review(content_id, creator_reasoning, appeal_timestamp):
    """
    Update the original submission log entry so the current content status is
    visible directly in GET /log.
    """
    entries = _load_log_entries()
    updated = None

    for entry in reversed(entries):
        if entry.get("event_type") == "submission" and entry.get("content_id") == content_id:
            entry["status"] = "under_review"
            entry["appeal_filed"] = True
            entry["appeal_reasoning"] = creator_reasoning
            entry["appeal_timestamp"] = appeal_timestamp
            updated = entry
            break

    if updated is not None:
        _save_log_entries(entries)

    return updated
