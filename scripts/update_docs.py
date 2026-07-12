"""Regenerate all API documentation artifacts (OpenAPI + TypeScript types)."""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def _run(cmd: list[str], *, cwd: Path | None = None) -> None:
    print("+", " ".join(cmd))
    subprocess.run(cmd, cwd=cwd or REPO_ROOT, check=True)


def _npm_run(script: str, *, cwd: Path) -> None:
    npm = shutil.which("npm")
    if npm is None:
        raise RuntimeError("npm not found on PATH")
    _run([npm, "run", script], cwd=cwd)


def main() -> None:
    _run([sys.executable, "scripts/export_openapi.py"])
    _npm_run("generate:api-types", cwd=REPO_ROOT / "web")
    print("\nDone. Commit docs/api/openapi.json and web/src/lib/api.generated.ts if changed.")


if __name__ == "__main__":
    main()
