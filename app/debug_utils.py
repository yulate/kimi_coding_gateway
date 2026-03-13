from __future__ import annotations

import asyncio
import json
import os


def parse_json_payload(body: bytes):
    if not body:
        return None
    try:
        return json.loads(body)
    except json.JSONDecodeError as exc:
        return {
            "_parse_error": str(exc),
            "_raw": body.decode("utf-8", errors="replace"),
        }


def parse_stream_json_events(raw_stream: bytes):
    text = raw_stream.decode("utf-8", errors="replace")
    events = []
    for line in text.splitlines():
        if not line.startswith("data:"):
            continue
        payload = line[5:].strip()
        if not payload or payload == "[DONE]":
            continue
        try:
            events.append(json.loads(payload))
        except json.JSONDecodeError as exc:
            events.append({"_parse_error": str(exc), "_raw": payload})
    return events


def append_debug_record_sync(path: str, record: dict):
    directory = os.path.dirname(path)
    if directory:
        os.makedirs(directory, exist_ok=True)
    line = json.dumps(record, ensure_ascii=False)
    with open(path, "a", encoding="utf-8") as file_obj:
        file_obj.write(line)
        file_obj.write("\n")


class DebugWriter:
    def __init__(self, enabled: bool, path: str):
        self._enabled = enabled
        self._path = path
        self._lock = asyncio.Lock()

    @property
    def enabled(self) -> bool:
        return self._enabled

    async def append(self, record: dict):
        if not self._enabled:
            return
        async with self._lock:
            await asyncio.to_thread(append_debug_record_sync, self._path, record)

