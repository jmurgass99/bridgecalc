"""Cada script de examples/ se ejecuta como proceso independiente y debe terminar con código 0."""
import os
import subprocess
import sys
from pathlib import Path

import pytest

EXAMPLES = sorted((Path(__file__).resolve().parents[1] / "examples").glob("*.py"))


@pytest.mark.parametrize("script", EXAMPLES, ids=[p.stem for p in EXAMPLES])
def test_example_runs(script: Path, tmp_path: Path) -> None:
    env = dict(os.environ, JM_EXAMPLES_OUT_DIR=str(tmp_path), PYTHONUTF8="1")
    r = subprocess.run(
        [sys.executable, "-X", "utf8", str(script)],
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=100, env=env,
        cwd=str(script.parent.parent),
    )
    assert r.returncode == 0, r.stderr[-2000:]
    assert r.stdout.strip(), "el ejemplo no imprimió nada"
