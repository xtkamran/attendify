"""Regenerate openapi.yaml from the live FastAPI app (the source of truth).

Run from the project root with dependencies installed:

    python scripts/dump_openapi.py

FastAPI also serves the same document live at http://localhost:8000/openapi.json
"""
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.main import app  # noqa: E402


def main() -> None:
    spec = app.openapi()
    out = Path(__file__).resolve().parent.parent / "openapi.yaml"
    out.write_text(yaml.safe_dump(spec, sort_keys=False, allow_unicode=True))
    print(f"Wrote {out} ({len(spec.get('paths', {}))} paths)")


if __name__ == "__main__":
    main()
