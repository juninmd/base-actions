"""Prova que gitleaks.toml pega o que tem que pegar e ignora o que tem que ignorar.

Roda igual em CI e na maquina: python testdata/assert.py <caminho-do-gitleaks>
"""

import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GITLEAKS = sys.argv[1] if len(sys.argv) > 1 else "gitleaks"


def fixture(seed: str, length: int) -> str:
    """Valor deterministico e sem sequencia de stopword, gerado sob demanda."""
    out = ""
    counter = 0
    while len(out) < length:
        out += hashlib.sha256(f"{seed}:{counter}".encode()).hexdigest()
        counter += 1
    return out[:length]


# OpenRouter e xAI usam prefixos que o push protection do GitHub reconhece.
# Se o literal ficasse no repositorio, o push seria bloqueado mesmo sendo um
# valor inventado. Por isso estes dois casos sao materializados em um diretorio
# temporario na hora do teste; o corpus versionado nao contem a chave.
RUNTIME_LEAKS = {
    "juninmd-openrouter-api-key": "sk-or-v1-" + fixture("openrouter", 64),
    "juninmd-xai-api-key": "xai-" + fixture("xai", 80),
}


def leaky_corpus(destination: Path) -> Path:
    shutil.copytree(ROOT / "testdata" / "leaky", destination)
    lines = [
        "// Casos gerados em runtime: formatos bloqueados pelo push protection.",
        "module.exports = {",
    ]
    for rule, secret in RUNTIME_LEAKS.items():
        lines.append(f"  // LEAK: {rule}")
        lines.append(f"  {rule.replace('-', '_')}: {secret!r},")
    lines.append("};")
    (destination / "providers.js").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return destination

# Toda regra custom precisa disparar no corpus vazado. Se voce adicionar uma
# regra nova, adicione o caso em testdata/leaky/ e o id aqui.
EXPECTED = {
    "juninmd-hardcoded-password",
    "juninmd-oracle-connect-string",
    "juninmd-db-uri-credentials",
    "juninmd-internal-hostname",
    "juninmd-aws-rds-endpoint",
    "juninmd-authorization-header",
    "juninmd-google-gemini-auth-key",
    "juninmd-openrouter-api-key",
    "juninmd-groq-api-key",
    "juninmd-xai-api-key",
    "juninmd-google-oauth-client-secret",
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

with tempfile.TemporaryDirectory() as corpus_tmp:
    found = {f["RuleID"] for f in scan(leaky_corpus(Path(corpus_tmp) / "leaky"))}
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
