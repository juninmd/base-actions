#!/usr/bin/env python3
"""Mescla PRs cujos checks nao iniciam por billing/spending limit do GitHub.

Por que este script vive no juninmd/base-actions (repo publico):
quando a conta esta com spending limit/billing bloqueado, o GitHub nao inicia
NENHUM job nos repositorios privados. Logo, um workflow dentro desses repos nao
consegue nem rodar nem mesclar o proprio PR. Este bot roda no repo publico e usa
um PAT fine-grained (secret AUTOMERGE_TOKEN) para agir nos demais repos.

Guardrails:
- so mescla PR de autor na allowlist (padrao: juninmd + bots de automacao);
- so mescla PR aberto, nao-draft, para o branch default, sem conflito;
- so mescla quando TODOS os checks que falharam trazem a assinatura de billing
  (qualquer falha "de verdade" bloqueia o merge);
- respeita as labels de opt-out (padrao: do-not-merge, wip, blocked, hold);
- DRY_RUN por padrao em execucao manual; schedule mescla de verdade;
- limite de merges por execucao.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time

sys.dont_write_bytecode = True
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

BILLING_RE = re.compile(
    r"recent account payments have failed|spending limit needs to be increased",
    re.IGNORECASE,
)
PASSING = {"success", "neutral", "skipped"}
ALLOWED_STATES = {"clean", "unstable", "blocked", "behind", "has_hooks"}


def env(name: str, default: str = "") -> str:
    value = os.environ.get(name, "").strip()
    return value or default


DRY_RUN = env("BOT_DRY_RUN", "false").lower() == "true"
ONLY_REPO = env("BOT_REPOSITORY")
AUTHORS = {
    a.strip()
    for a in env(
        "BOT_AUTHORS",
        "juninmd,dependabot[bot],renovate[bot],github-actions[bot],"
        "claude[bot],copilot-swe-agent[bot],google-labs-jules[bot]",
    ).split(",")
    if a.strip()
}
DENY_LABELS = {
    l.strip().lower()
    for l in env("BOT_DENY_LABELS", "do-not-merge,wip,blocked,hold").split(",")
    if l.strip()
}
try:
    MAX_MERGES = max(1, int(env("BOT_MAX_MERGES", "20")))
except ValueError:
    MAX_MERGES = 20

stats = {"merged": 0, "skipped": 0, "failed": 0, "seen": 0}
summary: list[str] = []


def log(msg: str) -> None:
    print(msg, flush=True)


def notice(msg: str) -> None:
    print(f"::notice::{msg}", flush=True)


def warn(msg: str) -> None:
    print(f"::warning::{msg}", flush=True)


def gh(*args: str, check: bool = True) -> str:
    proc = subprocess.run(
        ["gh", *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if check and proc.returncode != 0:
        raise RuntimeError(
            f"gh {' '.join(args)} falhou ({proc.returncode}): "
            f"{(proc.stderr or proc.stdout).strip()[:400]}"
        )
    return proc.stdout


def api(path: str, check: bool = True):
    out = gh("api", path, check=check)
    if not out.strip():
        return None
    return json.loads(out)


def list_repos():
    """Repos do owner com PR/issue aberto (evita varrer repos vazios)."""
    page = 1
    while page <= 10:
        batch = api(f"user/repos?affiliation=owner&per_page=100&page={page}")
        if not batch:
            return
        for repo in batch:
            if repo.get("archived") or repo.get("fork"):
                continue
            if ONLY_REPO and repo["full_name"] != ONLY_REPO:
                continue
            if not repo.get("open_issues_count"):
                continue
            if not (repo.get("permissions") or {}).get("push", False):
                continue
            yield repo
        page += 1


def refresh_pr(repo: str, number: int):
    for attempt in range(3):
        pr = api(f"repos/{repo}/pulls/{number}")
        if pr and pr.get("mergeable") is not None:
            return pr
        time.sleep(2 + attempt)
    return pr


def billing_only(pr: dict) -> bool:
    """True somente se o unico motivo de falha for billing/spending limit."""
    repo = pr["base"]["repo"]["full_name"]
    sha = pr["head"]["sha"]
    data = api(f"repos/{repo}/commits/{sha}/check-runs?per_page=100")
    if not data or not data.get("total_count"):
        log(f"    {repo}#{pr['number']}: sem check-runs no commit; sem evidencia de billing")
        return False

    billing = False
    for run in data.get("check_runs", []):
        if run.get("status") != "completed":
            log(f"    {repo}#{pr['number']}: check '{run.get('name')}' ainda {run.get('status')}")
            return False
        if (run.get("conclusion") or "").lower() in PASSING:
            continue
        anns = api(f"repos/{repo}/check-runs/{run['id']}/annotations", check=False) or []
        message = " ".join(str(a.get("message", "")) for a in anns)
        if BILLING_RE.search(message):
            billing = True
            continue
        log(
            f"    {repo}#{pr['number']}: check '{run.get('name')}' falhou por motivo real"
            f" ({message[:120] or 'sem anotacao'})"
        )
        return False
    return billing


def merge_method(repo: dict) -> str:
    if repo.get("allow_squash_merge", True):
        return "squash"
    if repo.get("allow_merge_commit", True):
        return "merge"
    return "rebase"


def merge(repo: str, pr: dict, method: str) -> bool:
    number = pr["number"]
    sha = pr["head"]["sha"]
    args = [
        "pr",
        "merge",
        str(number),
        "-R",
        repo,
        "--match-head-commit",
        sha,
        f"--{method}",
    ]
    if DRY_RUN:
        notice(f"DRY-RUN: mesclaria {repo}#{number} ({method}, head {sha[:7]})")
        return True
    try:
        gh(*args)
        return True
    except RuntimeError as exc:
        log(f"    merge normal bloqueado em {repo}#{number}; aplicando --admin: {exc}")
    try:
        gh(*args, "--admin")
        return True
    except RuntimeError as exc:
        warn(f"nao foi possivel mesclar {repo}#{number}: {exc}")
        return False


def process(repo: dict) -> None:
    name = repo["full_name"]
    default_branch = repo.get("default_branch") or "main"
    prs = api(f"repos/{name}/pulls?state=open&per_page=100") or []
    for pr in prs:
        stats["seen"] += 1
        number = pr["number"]
        author = (pr.get("user") or {}).get("login", "")
        labels = {(l.get("name") or "").lower() for l in pr.get("labels", [])}
        head = pr["head"]["sha"][:7]

        if pr.get("draft"):
            stats["skipped"] += 1
            continue
        if author not in AUTHORS:
            log(f"  - {name}#{number}: autor '{author}' fora da allowlist")
            stats["skipped"] += 1
            continue
        if labels & DENY_LABELS:
            log(f"  - {name}#{number}: label de opt-out {sorted(labels & DENY_LABELS)}")
            stats["skipped"] += 1
            continue
        if pr["base"]["ref"] != default_branch:
            log(f"  - {name}#{number}: base '{pr['base']['ref']}' != default '{default_branch}'")
            stats["skipped"] += 1
            continue

        if pr.get("mergeable") is None:
            pr = refresh_pr(name, number)
        if not pr or pr.get("mergeable") is False:
            log(f"  - {name}#{number}: conflito/nao mesclavel")
            stats["skipped"] += 1
            continue
        state = (pr.get("mergeable_state") or "unknown").lower()
        if state not in ALLOWED_STATES:
            log(f"  - {name}#{number}: mergeable_state='{state}'")
            stats["skipped"] += 1
            continue

        log(f"  > {name}#{number} por {author} ({head}) — verificando checks")
        if not billing_only(pr):
            stats["skipped"] += 1
            summary.append(f"skip {name}#{number}: falha nao relacionada a billing")
            continue

        method = merge_method(repo)
        if merge(name, pr, method):
            stats["merged"] += 1
            summary.append(f"merged {name}#{number} ({method})")
        else:
            stats["failed"] += 1
            summary.append(f"failed {name}#{number}")

        if stats["merged"] >= MAX_MERGES:
            warn(f"limite de {MAX_MERGES} merges por execucao atingido; parando")
            return


def main() -> int:
    if not env("GH_TOKEN") and not env("GITHUB_TOKEN"):
        warn("AUTOMERGE_TOKEN nao configurado; nada a fazer")
        return 0

    log(f"dry_run={DRY_RUN} only_repo={ONLY_REPO or '*'} max_merges={MAX_MERGES}")
    for repo in list_repos():
        try:
            process(repo)
        except Exception as exc:  # um repo com erro nao derruba a varredura
            warn(f"erro em {repo.get('full_name')}: {exc}")
            stats["failed"] += 1
        if stats["merged"] >= MAX_MERGES:
            break

    log(
        f"resumo: vistos={stats['seen']} mesclados={stats['merged']} "
        f"ignorados={stats['skipped']} falhas={stats['failed']}"
    )
    step_summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if step_summary:
        with open(step_summary, "a", encoding="utf-8") as fh:
            fh.write("## Auto-merge billing-blocked\n\n")
            fh.write(
                f"- vistos: {stats['seen']}\n"
                f"- mesclados: {stats['merged']}\n"
                f"- ignorados: {stats['skipped']}\n"
                f"- falhas: {stats['failed']}\n"
                f"- dry-run: {DRY_RUN}\n\n"
            )
            for line in summary[:200]:
                fh.write(f"- {line}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
