"""Prova que gitleaks.toml pega o que tem que pegar e ignora o que tem que ignorar.

Roda igual em CI e na maquina: python testdata/assert.py <caminho-do-gitleaks>
"""

import base64
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GITLEAKS = sys.argv[1] if len(sys.argv) > 1 else "gitleaks"

RESEND_ALPHABET = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"


def fixture(seed: str, length: int) -> str:
    """Valor deterministico em hex, sem sequencia de stopword."""
    out = ""
    counter = 0
    while len(out) < length:
        out += hashlib.sha256(f"{seed}:{counter}".encode()).hexdigest()
        counter += 1
    return out[:length]


def b64(seed: str, length: int) -> str:
    """Valor deterministico no alfabeto base64, sem padding e sem '='."""
    out = ""
    counter = 0
    while len(out) < length:
        digest = hashlib.sha256(f"{seed}:{counter}".encode()).digest()
        out += base64.b64encode(digest).decode().rstrip("=")
        counter += 1
    return out[:length]


def from_alphabet(seed: str, length: int, alphabet: str) -> str:
    """Valor deterministico restrito a um alfabeto (ex.: Resend)."""
    out = ""
    counter = 0
    while len(out) < length:
        digest = hashlib.sha256(f"{seed}:{counter}".encode()).digest()
        for byte in digest:
            out += alphabet[byte % len(alphabet)]
            if len(out) == length:
                break
        counter += 1
    return out


def uuid_hex(seed: str) -> str:
    value = fixture(seed, 32)
    return f"{value[:8]}-{value[8:12]}-{value[12:16]}-{value[16:20]}-{value[20:32]}"


# Alguns formatos sao reconhecidos pelo push protection do GitHub mesmo sendo
# valores inventados. Por isso todo caso novo e materializado em um diretorio
# temporario na hora do teste; o corpus versionado nao contem a chave.
RUNTIME_LEAKS = {
    # formato novo do Gemini + provedores de IA
    "juninmd-openrouter-api-key": "sk-or-v1-" + fixture("openrouter", 64),
    "juninmd-xai-api-key": "xai-" + fixture("xai", 80),
    "juninmd-nvidia-nim-api-key": "nvapi-" + fixture("nvidia", 64),
    "juninmd-langsmith-api-key": (
        "lsv2_pt_" + fixture("langsmith-id", 32) + "_" + fixture("langsmith-secret", 10)
    ),
    "juninmd-fireworks-api-key": "fw_" + fixture("fireworks", 32),
    "juninmd-replicate-api-token": "r8_" + fixture("replicate", 37),
    "juninmd-elevenlabs-api-key": "sk_" + fixture("elevenlabs", 48),
    "juninmd-pinecone-api-key": "pcsk_abcde_" + fixture("pinecone", 63),
    "juninmd-wandb-api-key": (
        "wandb_v1_" + fixture("wandb-id", 27) + "_" + fixture("wandb-secret", 49)
    ),
    # cloud / infra
    "juninmd-aws-access-key-id-extra": "AGPA" + fixture("aws-extra", 16).upper(),
    "juninmd-aws-secret-access-key": (
        "aws_secret_access_key = '" + b64("aws-secret", 40) + "'"
    ),
    "juninmd-azure-storage-account-key": (
        "AccountKey=" + b64("azure-storage", 86) + "=="
    ),
    "juninmd-digitalocean-token-v1": "dot_v1_" + fixture("digitalocean", 64),
    "juninmd-vault-token": "hvs." + fixture("vault", 30),
    "juninmd-cloudflare-api-token": (
        "cfut_" + fixture("cloudflare", 40) + fixture("cloudflare-suffix", 8)
    ),
    # pagamentos
    "juninmd-stripe-webhook-secret": "whsec_" + fixture("stripe-webhook", 48),
    "juninmd-paypal-braintree-token": (
        "access_token$production$"
        + fixture("braintree-id", 16)
        + "$"
        + fixture("braintree-secret", 32)
    ),
    "juninmd-razorpay-key": "rzp_live_" + fixture("razorpay", 14),
    "juninmd-paystack-key": "sk_live_" + fixture("paystack", 40),
    "juninmd-pagarme-key": "ak_live_" + fixture("pagarme", 30),
    # comunicacao
    "juninmd-discord-bot-token": (
        "M"
        + fixture("discord-bot", 23)
        + "."
        + fixture("discord-bot-mid", 6)
        + "."
        + fixture("discord-bot-sig", 27)
    ),
    "juninmd-discord-webhook": (
        "https://discord.com/api/webhooks/123456789012345678/"
        + fixture("discord-webhook-token", 32)
    ),
    "juninmd-resend-api-key": (
        "re_"
        + from_alphabet("resend-id", 8, RESEND_ALPHABET)
        + "_"
        + from_alphabet("resend-secret", 24, RESEND_ALPHABET)
    ),
    # registries
    "juninmd-docker-hub-pat": "dckr_pat_" + fixture("dockerhub", 36),
    "juninmd-buildkite-token": "bkua_" + fixture("buildkite", 40),
    # observabilidade / SaaS
    "juninmd-sonarcloud-token": "sqco_" + fixture("sonarcloud", 59),
    "juninmd-newrelic-license-key": fixture("newrelic-license", 40) + "NRAL",
    "juninmd-sentry-dsn": (
        "https://" + fixture("sentry-dsn", 32) + "@o123.ingest.sentry.io/456"
    ),
    "juninmd-datadog-api-key": "ddog_" + fixture("datadog", 48),
    "juninmd-supabase-pat": "sbp_" + fixture("supabase", 40),
    "juninmd-firebase-cloud-messaging-key": (
        "AAAA" + fixture("firebase", 7) + ":" + fixture("firebase-secret", 140)
    ),
    # produtividade
    "juninmd-figma-pat": "figp_" + fixture("figma", 48),
    "juninmd-tailscale-key": (
        "tskey-auth-" + fixture("tailscale-id", 20) + "-" + fixture("tailscale-secret", 20)
    ),
    "juninmd-infisical-token": (
        "st." + uuid_hex("infisical") + "." + fixture("infisical-secret", 32)
    ),
}


def leaky_corpus(destination: Path) -> Path:
    shutil.copytree(ROOT / "testdata" / "leaky", destination)
    lines = ["# Casos gerados em runtime: formatos bloqueados pelo push protection."]
    for rule, secret in RUNTIME_LEAKS.items():
        lines.append(f"# LEAK: {rule}")
        lines.append(secret)
    (destination / "providers.txt").write_text(
        "\n".join(lines) + "\n", encoding="utf-8"
    )
    return destination


# Toda regra custom precisa disparar no corpus vazado. Se voce adicionar uma
# regra nova, adicione o caso em testdata/leaky/ ou em RUNTIME_LEAKS e o id aqui.
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
    "juninmd-aws-access-key-id-extra",
    "juninmd-aws-secret-access-key",
    "juninmd-azure-storage-account-key",
    "juninmd-digitalocean-token-v1",
    "juninmd-vault-token",
    "juninmd-stripe-webhook-secret",
    "juninmd-paypal-braintree-token",
    "juninmd-razorpay-key",
    "juninmd-paystack-key",
    "juninmd-pagarme-key",
    "juninmd-discord-bot-token",
    "juninmd-discord-webhook",
    "juninmd-resend-api-key",
    "juninmd-docker-hub-pat",
    "juninmd-buildkite-token",
    "juninmd-sonarcloud-token",
    "juninmd-newrelic-license-key",
    "juninmd-sentry-dsn",
    "juninmd-datadog-api-key",
    "juninmd-supabase-pat",
    "juninmd-firebase-cloud-messaging-key",
    "juninmd-nvidia-nim-api-key",
    "juninmd-langsmith-api-key",
    "juninmd-fireworks-api-key",
    "juninmd-replicate-api-token",
    "juninmd-elevenlabs-api-key",
    "juninmd-pinecone-api-key",
    "juninmd-wandb-api-key",
    "juninmd-figma-pat",
    "juninmd-tailscale-key",
    "juninmd-infisical-token",
    "juninmd-cloudflare-api-token",
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
