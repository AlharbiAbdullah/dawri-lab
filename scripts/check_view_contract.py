"""Check real recorded FastAPI responses with the frontend's actual validators."""

import os
import shutil
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    """Generate responses in a temporary directory, then validate both seasons."""
    uv = shutil.which("uv")
    npm = shutil.which("npm")
    if uv is None or npm is None:
        raise RuntimeError("uv and npm are required for the view contract check")
    with tempfile.TemporaryDirectory(prefix="dawri-view-contract-") as folder:
        payload = Path(folder) / "views.json"
        exported = subprocess.run(  # noqa: S603
            [
                uv,
                "run",
                "pytest",
                "tests/test_view.py",
                "-k",
                "view_facts",
                "--view-contract",
                str(payload),
                "-q",
            ],
            cwd=ROOT,
            check=False,
        )
        if exported.returncode:
            return exported.returncode
        return subprocess.run(  # noqa: S603
            [
                npm,
                "exec",
                "--",
                "vitest",
                "run",
                "--config",
                "vitest.contract.config.ts",
            ],
            cwd=ROOT / "web",
            env={**os.environ, "DAWRI_VIEW_CONTRACT": str(payload)},
            check=False,
        ).returncode


if __name__ == "__main__":
    raise SystemExit(main())
