"""Verify generated API documentation matches the FastAPI source of truth.

Regenerates docs/api/openapi.json and web/src/lib/api.generated.ts, then exits
non-zero when committed artifacts are out of date.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
OPENAPI = REPO_ROOT / "docs" / "api" / "openapi.json"
GENERATED_TS = REPO_ROOT / "web" / "src" / "lib" / "api.generated.ts"


def _run(cmd: list[str], *, cwd: Path | None = None) -> None:
    print("+", " ".join(cmd))
    subprocess.run(cmd, cwd=cwd or REPO_ROOT, check=True)


def _npm_run(script: str, *, cwd: Path) -> None:
    npm = shutil.which("npm")
    if npm is None:
        raise RuntimeError("npm not found on PATH")
    _run([npm, "run", script], cwd=cwd)


def main() -> int:
    _run([sys.executable, "scripts/export_openapi.py"])

    if not OPENAPI.is_file():
        print(f"Missing {OPENAPI.relative_to(REPO_ROOT)}", file=sys.stderr)
        return 1

    _npm_run("generate:api-types", cwd=REPO_ROOT / "web")

    if not GENERATED_TS.is_file():
        print(f"Missing {GENERATED_TS.relative_to(REPO_ROOT)}", file=sys.stderr)
        return 1

    diff = subprocess.run(
        ["git", "diff", "--exit-code", "--", "docs/api/openapi.json", "web/src/lib/api.generated.ts"],
        cwd=REPO_ROOT,
    )
    if diff.returncode != 0:
        print(
            "\nGenerated documentation is out of date.\n"
            "Run:  python scripts/update_docs.py\n"
            "Then commit the updated files.",
            file=sys.stderr,
        )
        return 1

    print("Documentation artifacts are up to date.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
