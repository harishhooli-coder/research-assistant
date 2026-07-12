"""Export the FastAPI OpenAPI schema to docs/api/openapi.json.

No running server, Redis, or Postgres required — only imports the app factory.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
OUTPUT = REPO_ROOT / "docs" / "api" / "openapi.json"


def export_openapi(*, pretty: bool = True) -> Path:
    sys.path.insert(0, str(REPO_ROOT))

    from api.main import create_app

    app = create_app()
    schema = app.openapi()

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT.open("w", encoding="utf-8") as fh:
        if pretty:
            json.dump(schema, fh, indent=2, ensure_ascii=False)
            fh.write("\n")
        else:
            json.dump(schema, fh, ensure_ascii=False)

    return OUTPUT


if __name__ == "__main__":
    path = export_openapi()
    print(f"Wrote {path.relative_to(REPO_ROOT)}")
