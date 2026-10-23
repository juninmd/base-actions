#!/usr/bin/env python3
"""Regression do gate de segredos versionados do validate-pr.

Executa o bloco `run:` real do passo "Check for committed secrets (Basic)"
dentro de um repo git temporario, com arquivos de mentira gerados em runtime
(nada de chave commitada neste repo). Pina:
  - .env, .pem e .key na raiz e em subpastas continuam reprovando;
  - fixtures de teste (tests/, fixtures/ na raiz ou aninhados) passam.
"""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
ACTION = ROOT / "validate-pr" / "action.yml"
STEP_NAME = "Check for committed secrets (Basic)"
PLACEHOLDER = "placeholder-not-a-secret\n"
# Windows: `bash` no PATH costuma ser o WSL; BASH_BIN aponta para o Git Bash local
BASH = os.environ.get("BASH_BIN", "bash")


def load_script() -> str:
    steps = yaml.safe_load(ACTION.read_text(encoding="utf-8"))["runs"]["steps"]
    step = next(s for s in steps if s.get("name") == STEP_NAME)
    return step["run"]


def run_gate(script: str, files: list[str]) -> int:
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp)
        subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
        for rel in files:
            target = repo / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(PLACEHOLDER, encoding="utf-8")
        subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
        result = subprocess.run(
            [BASH, "-e", "-c", script], cwd=repo, capture_output=True, text=True
        )
        # exit 127/126 = bash ausente: nao pode passar como "reprovou"
        if result.returncode in (126, 127) or "WSL" in result.stderr:
            raise SystemExit(f"bash indisponivel ({BASH}): {result.stderr.strip()}")
        return result.returncode


CASES = [
    # (descricao, arquivos, exit esperado)
    ("env na raiz reprova", [".env"], 1),
    ("pem em subpasta reprova", ["config/prod.pem"], 1),
    ("key em subpasta reprova", ["certs/server.key"], 1),
    ("fixture .key em tests/ na raiz passa", ["tests/servers/ca.key"], 0),
    ("fixture .key em fixtures/ na raiz passa", ["fixtures/x.key"], 0),
    ("fixture aninhada em tests/ passa", ["pkg/tests/unit/a.key"], 0),
    ("repo limpo passa", ["src/index.ts"], 0),
]


def main() -> int:
    script = load_script()
    failures = 0
    for desc, files, expected in CASES:
        got = run_gate(script, files)
        ok = got == expected
        failures += 0 if ok else 1
        print(f"{'ok  ' if ok else 'FAIL'} {desc} (exit {got}, esperado {expected})")
    if failures:
        print(f"{failures} caso(s) falharam", file=sys.stderr)
        return 1
    print(f"{len(CASES)} casos ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
