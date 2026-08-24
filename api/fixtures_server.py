import json
from typing import Any

from fastapi import HTTPException

from config import FIXTURES_DIR


def load_fixture(filename: str) -> dict[str, Any]:
    file_path = FIXTURES_DIR / filename
    if not file_path.exists():
        raise HTTPException(
            status_code=404, 
            detail=f"Fixture file '{filename}' not found at {file_path}."
        )
    
    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)

def get_paged_fixture(filename: str, status_filter: str | None = None) -> dict[str, Any]:
    data = load_fixture(filename)
    
    if status_filter and isinstance(data, list):
        data = [item for item in data if item.get("status") == status_filter]
        
    if isinstance(data, list):
        return {
            "items": data,
            "total": len(data),
            "page": 1,
            "size": len(data)
        }
    return data