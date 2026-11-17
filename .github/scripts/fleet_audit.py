"""Regras puras da manutencao diaria da frota (sem rede): testaveis isoladamente.

Entrada: texto dos workflows de um repo e metadados de runs. Saida: achados.
"""

from __future__ import annotations

import re

BASE = "juninmd/base-actions/"
USES = re.compile(r"^\s*-?\s*uses:\s*['\"]?([^\s'\"#]+)", re.MULTILINE)
SHA = re.compile(r"@[0-9a-f]{40}$")
BASE_PIN = re.compile(r"(juninmd/base-actions/[^@\s'\"]+)@(?!main\b)([^\s'\"#]+)")
CRON = re.compile(r"^\s*-?\s*cron\s*:", re.MULTILINE)
TOP_PERMISSIONS = re.compile(r"^permissions\s*:", re.MULTILINE)
CONCURRENCY = re.compile(r"^\s*concurrency\s*:", re.MULTILINE)
RUNS_ON = re.compile(r"^\s+runs-on\s*:", re.MULTILINE)
TIMEOUT = re.compile(r"^\s+timeout-minutes\s*:", re.MULTILINE)
PR_TRIGGER = re.compile(r"\bpull_request(_target)?\b")

BILLING = re.compile(r"recent account payments have failed|spending limit", re.IGNORECASE)
INFRA = re.compile(
    r"not acquired by Runner|lost communication with the server|runner has received a shutdown"
    r"|internal server error|hosted runner .* encountered an error",
    re.IGNORECASE,
)


def uses_refs(text: str) -> list[str]:
    return USES.findall(text)


def references_base_actions(workflows: dict[str, str]) -> bool:
    return any(ref.startswith(BASE) for text in workflows.values() for ref in uses_refs(text))


def audit_workflows(workflows: dict[str, str]) -> dict[str, list[str]]:
    """Achados por categoria; cada item e `arquivo: detalhe`."""
    out: dict[str, list[str]] = {
        "base_pinned": [],
        "third_party_unpinned": [],
        "no_permissions": [],
        "no_timeout": [],
        "no_concurrency": [],
        "cron": [],
    }
    for name, text in sorted(workflows.items()):
        for ref in uses_refs(text):
            if ref.startswith(BASE):
                if not ref.endswith("@main"):
                    out["base_pinned"].append(f"{name}: {ref}")
            elif not (ref.startswith("./") or ref.startswith("docker://") or SHA.search(ref)):
                out["third_party_unpinned"].append(f"{name}: {ref}")
        if not TOP_PERMISSIONS.search(text):
            out["no_permissions"].append(name)
        # Job que chama reusable nao tem runs-on: so conta job com runner proprio.
        if len(TIMEOUT.findall(text)) < len(RUNS_ON.findall(text)):
            out["no_timeout"].append(name)
        if PR_TRIGGER.search(text) and not CONCURRENCY.search(text):
            out["no_concurrency"].append(name)
        if CRON.search(text):
            out["cron"].append(name)
    return out


def repin_to_main(text: str) -> str:
    """Troca `juninmd/base-actions/...@<sha|tag>` por `@main` (politica do repo)."""
    return BASE_PIN.sub(lambda m: f"{m.group(1)}@main", text)


def classify_failure(annotations: list[str], conclusion: str) -> str:
    """billing | infra | code. Billing e infra nao se corrigem com codigo."""
    joined = "\n".join(annotations)
    if BILLING.search(joined):
        return "billing"
    if INFRA.search(joined) or conclusion == "cancelled":
        return "infra"
    return "code"


def latest_per_workflow(runs: list[dict]) -> list[dict]:
    """Ultima run de cada workflow (por `path`), ignorando eventos de PR."""
    best: dict[str, dict] = {}
    for run in runs:
        if run.get("event") in ("pull_request", "pull_request_target"):
            continue
        cur = best.get(run["path"])
        if cur is None or run["created_at"] > cur["created_at"]:
            best[run["path"]] = run
    return list(best.values())


def slow_workflows(runs: list[dict], budget_minutes: float) -> list[tuple[str, float]]:
    """Workflows cuja media das runs com sucesso passa do orcamento (minutos)."""
    from datetime import datetime

    def minutes(run: dict) -> float | None:
        start, end = run.get("run_started_at"), run.get("updated_at")
        if not start or not end:
            return None
        fmt = "%Y-%m-%dT%H:%M:%SZ"
        return (datetime.strptime(end, fmt) - datetime.strptime(start, fmt)).total_seconds() / 60

    acc: dict[str, list[float]] = {}
    for run in runs:
        if run.get("conclusion") != "success":
            continue
        value = minutes(run)
        if value is not None:
            acc.setdefault(run["path"], []).append(value)
    return sorted(
        ((path, round(sum(v) / len(v), 1)) for path, v in acc.items() if sum(v) / len(v) > budget_minutes),
        key=lambda item: -item[1],
    )
