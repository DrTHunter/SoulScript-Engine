"""Append-only JSONL journal store.

Every significant runtime event is written as one JSON line.

Event types:
    user_input, agent_selected, llm_request_meta, llm_response,
    tool_call, tool_result, policy_stop, error
"""

import json
import os
import time
from typing import Any, Dict


class JournalStore:
    def __init__(self, path: str):
        self.path = path
        dir_name = os.path.dirname(path)
        if dir_name:
            os.makedirs(dir_name, exist_ok=True)

    def append(self, event: str, data: Dict[str, Any]) -> None:
        """Append a single event line to the journal."""
        entry = {
            "ts": time.time(),
            "iso": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "event": event,
            "data": data,
        }
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False, default=str) + "\n")
