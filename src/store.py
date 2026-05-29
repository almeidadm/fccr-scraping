"""Persistência do índice de publicações já vistas."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

INDEX_PATH = Path("data/index.json")


def load_index(path: Path = INDEX_PATH) -> dict[str, dict]:
    if not path.exists():
        return {}
    with path.open(encoding="utf-8") as f:
        data = json.load(f)
    return data.get("items", {})


def save_index(items: dict[str, dict], path: Path = INDEX_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "count": len(items),
        "items": items,
    }
    with path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2, sort_keys=True)
        f.write("\n")


def merge_new(
    existing: dict[str, dict], incoming: list[dict], now_iso: str
) -> tuple[dict[str, dict], list[dict]]:
    """Insere itens novos em `existing`, marcando `first_seen`. Retorna (índice atualizado, itens novos)."""
    new_items: list[dict] = []
    merged = dict(existing)
    for item in incoming:
        item_id = item["id"]
        if item_id in merged:
            continue
        record = dict(item)
        record["first_seen"] = now_iso
        merged[item_id] = record
        new_items.append(record)
    return merged, new_items
