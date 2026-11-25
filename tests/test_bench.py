"""El banco de rendimiento imprime métricas reales y termina con 0 en modo rápido."""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
BENCH = RAIZ / "scripts" / "bench.py"
METRICA_RE = re.compile(r"^metric \S+ .*median_ms=\d+(?:\.\d+)? .*p95_ms=\d+(?:\.\d+)?", re.M)


def test_quick_imprime_metricas_numericas_y_sale_con_cero():
    proc = subprocess.run(
        [sys.executable, str(BENCH), "--quick"],
        cwd=RAIZ, capture_output=True, text=True, timeout=180,
    )

    assert proc.returncode == 0, proc.stdout + proc.stderr
    metricas = METRICA_RE.findall(proc.stdout)
    assert len(metricas) >= 4, proc.stdout
    assert "exit_code=0" in proc.stdout
