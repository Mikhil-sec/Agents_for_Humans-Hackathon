"""Emit JSON Schema for every contract model.

Run from the repo root:  python contracts/schemas/generate.py

Lane B can point a TypeScript codegen tool at the output if hand-maintaining
`contracts/typescript/index.ts` becomes tedious. The generated files are
committed so a reviewer can see a contract change as a diff.
"""

from __future__ import annotations

import json
from pathlib import Path

from quiet_hours_contracts import models

OUT = Path(__file__).parent


def main() -> None:
    exported = 0
    for name in dir(models):
        obj = getattr(models, name)
        if not isinstance(obj, type) or not hasattr(obj, "model_json_schema"):
            continue
        if name.startswith("_") or obj is models.BaseModel:
            continue
        schema = obj.model_json_schema()
        (OUT / f"{name}.schema.json").write_text(json.dumps(schema, indent=2) + "\n")
        exported += 1
    print(f"wrote {exported} schemas to {OUT}")


if __name__ == "__main__":
    main()
