"""Prova que gitleaks.toml pega o que tem que pegar e ignora o que tem que ignorar.

Roda igual em CI e na maquina: python testdata/assert.py <caminho-do-gitleaks>
"""

import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GITLEAKS = sys.argv[1] if len(sys.argv) > 1 else "gitleaks"

# Toda regra custom precisa disparar no corpus vazado. Se voce adicionar uma
# regra nova, adicione o caso em testdata/leaky/ e o id aqui.
EXPECTED = {
    "juninmd-hardcoded-password",
    "juninmd-oracle-connect-string",
    "juninmd-db-uri-credentials",
    "juninmd-internal-hostname",
    "juninmd-aws-rds-endpoint",
    "juninmd-authorization-header",
}


def scan(source: Path) -> list[dict]:
    with tempfile.TemporaryDirectory() as tmp:
        report = Path(tmp) / "report.json"
        subprocess.run(
            [GITLEAKS, "detect", "--no-git", "--source", str(source),
             "--config", str(ROOT / "gitleaks.toml"), "--report-format", "json",
             "--report-path", str(report), "--no-banner", "--exit-code", "0"],
            check=True, capture_output=True,
        )
        return json.loads(report.read_text(encoding="utf-8") or "[]")


failures = []

found = {f["RuleID"] for f in scan(ROOT / "testdata" / "leaky")}
missing = EXPECTED - found
if missing:
    failures.append(f"regras que NAO dispararam no corpus vazado: {sorted(missing)}")
print(f"leaky/: {len(found & EXPECTED)}/{len(EXPECTED)} regras custom dispararam")

clean = [f for f in scan(ROOT / "testdata" / "clean") if f["RuleID"].startswith("juninmd-")]
if clean:
    for f in clean:
        failures.append(f"falso positivo em clean/: {f['RuleID']} -> {f['Secret']!r}")
print(f"clean/: {len(clean)} falsos positivos")

if failures:
    print("\nFALHOU:")
    for f in failures:
        print(f"  - {f}")
    sys.exit(1)

print("\nOK: ruleset pega todos os vazamentos e nao acusa nenhum placeholder.")
