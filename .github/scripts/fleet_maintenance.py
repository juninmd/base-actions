#!/usr/bin/env python3
"""Manutencao diaria da frota (daily-maintenance.yml).

Varre os repos do owner com um PAT (FLEET_TOKEN) e:
- relata pipelines vermelhas no branch default, separando billing/infra/codigo;
- reexecuta uma vez os jobs que cairam por infra (runner nao alocado, cancelado);
- aponta workflows lentos, actions de terceiros sem SHA, falta de permissions,
  timeout e concurrency, e cron (politica no-cron);
- abre PR trocando pin de `juninmd/base-actions` por `@main`;
- em repo sem base-actions, PR aberto recebe "request changes" e vira draft.

So escreve com BOT_DRY_RUN=false. Relatorio: GITHUB_STEP_SUMMARY + issue unica.
"""

from __future__ import annotations

import base64
import json
import os
import sys
import time
import urllib.error
import urllib.request

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(__file__))
import fleet_audit as audit  # noqa: E402

API = "https://api.github.com"
GUARD_MARKER = "<!-- base-actions-pr-guard -->"
GUARD_TEXT = (
    f"{GUARD_MARKER}\n**PR recusado: este repositorio nao usa `juninmd/base-actions`.**\n\n"
    "Todo repo precisa chamar ao menos um workflow ou action de "
    "`juninmd/base-actions@main` (ex.: `reusable-validate.yml`). Adicione o workflow "
    "padrao neste PR e marque como *Ready for review*.\n\n"
    "Guia: https://github.com/juninmd/base-actions#-usage"
)
AUTOFIX_BRANCH = "chore/base-actions-main"


def env(name: str, default: str = "") -> str:
    return os.environ.get(name, "").strip() or default


TOKEN = env("GH_TOKEN")
OWNER = env("BOT_OWNER", "juninmd")
ONLY_REPO = env("BOT_REPOSITORY")
DRY_RUN = env("BOT_DRY_RUN", "true").lower() != "false"
SLOW_MINUTES = float(env("BOT_SLOW_MINUTES", "15"))
MAX_REPOS = int(env("BOT_MAX_REPOS", "300"))
REPORT_REPO = env("GITHUB_REPOSITORY", "juninmd/base-actions")
GUARD_ONLY = env("BOT_MODE", "full") == "guard"


def call(method: str, path: str, body: dict | None = None, raw: bool = False):
    url = path if path.startswith("http") else f"{API}{path}"
    data = json.dumps(body).encode() if body is not None else None
    for attempt in range(3):
        req = urllib.request.Request(url, data=data, method=method)
        req.add_header("Authorization", f"Bearer {TOKEN}")
        req.add_header("Accept", "application/vnd.github+json")
        req.add_header("X-GitHub-Api-Version", "2022-11-28")
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                payload = resp.read()
                return payload if raw else (json.loads(payload) if payload else {})
        except urllib.error.HTTPError as err:
            if err.code >= 500 and attempt < 2:
                time.sleep(2 ** attempt)
                continue
            raise
    raise RuntimeError("unreachable")


def get_or_none(path: str):
    try:
        return call("GET", path)
    except urllib.error.HTTPError as err:
        if err.code == 404:
            return None
        raise


def paginate(path: str, key: str | None = None, limit: int = 1000) -> list:
    out, page = [], 1
    sep = "&" if "?" in path else "?"
    while len(out) < limit:
        chunk = call("GET", f"{path}{sep}per_page=100&page={page}")
        items = chunk.get(key, []) if key else chunk
        out.extend(items)
        if len(items) < 100:
            break
        page += 1
    return out[:limit]


def list_repos() -> list[dict]:
    if ONLY_REPO:
        return [call("GET", f"/repos/{ONLY_REPO}")]
    repos = paginate(f"/users/{OWNER}/repos?type=owner&sort=pushed", limit=MAX_REPOS)
    # O relatorio vai para uma issue publica: repo privado fica fora (nome e falhas vazariam).
    return [r for r in repos if not (r["archived"] or r["fork"] or r["disabled"] or r["private"])]


def read_workflows(repo: str, ref: str) -> dict[str, str]:
    listing = get_or_none(f"/repos/{repo}/contents/.github/workflows?ref={ref}") or []
    out = {}
    for item in listing:
        if item.get("type") == "file" and item["name"].endswith((".yml", ".yaml")):
            blob = call("GET", f"/repos/{repo}/contents/{item['path']}?ref={ref}")
            out[item["path"]] = base64.b64decode(blob["content"]).decode("utf-8", "replace")
    return out


def failing_runs(repo: str, branch: str, runs: list[dict]) -> list[dict]:
    out = []
    for run in audit.latest_per_workflow(runs):
        if run.get("conclusion") not in ("failure", "startup_failure", "cancelled", "timed_out"):
            continue
        notes: list[str] = []
        jobs = call("GET", f"/repos/{repo}/actions/runs/{run['id']}/jobs?per_page=50").get("jobs", [])
        for job in jobs:
            if job.get("conclusion") in ("failure", "cancelled", "timed_out"):
                anns = get_or_none(f"/repos/{repo}/check-runs/{job['id']}/annotations") or []
                notes.extend(a.get("message", "") for a in anns)
        kind = audit.classify_failure(notes, run["conclusion"])
        out.append({"path": run["path"], "url": run["html_url"], "kind": kind,
                    "attempt": run.get("run_attempt", 1), "id": run["id"]})
    return out


def rerun_infra(repo: str, failures: list[dict], actions: list[str]) -> None:
    for f in failures:
        if f["kind"] == "infra" and f["attempt"] == 1 and not f["path"].startswith("dynamic/"):
            if not DRY_RUN:
                call("POST", f"/repos/{repo}/actions/runs/{f['id']}/rerun-failed-jobs", {})
            actions.append(f"{repo}: rerun {f['path']}")


def autofix_pins(repo: str, info: dict, workflows: dict[str, str], actions: list[str]) -> None:
    changed = {p: audit.repin_to_main(t) for p, t in workflows.items() if audit.repin_to_main(t) != t}
    if not changed or get_or_none(f"/repos/{repo}/branches/{AUTOFIX_BRANCH}"):
        return
    actions.append(f"{repo}: PR pin->@main ({len(changed)} arquivo(s))")
    if DRY_RUN:
        return
    base = info["default_branch"]
    head = call("GET", f"/repos/{repo}/git/ref/heads/{base}")["object"]["sha"]
    call("POST", f"/repos/{repo}/git/refs", {"ref": f"refs/heads/{AUTOFIX_BRANCH}", "sha": head})
    for path, text in changed.items():
        sha = call("GET", f"/repos/{repo}/contents/{path}?ref={AUTOFIX_BRANCH}")["sha"]
        call("PUT", f"/repos/{repo}/contents/{path}", {
            "message": "ci: reference juninmd/base-actions by @main",
            "content": base64.b64encode(text.encode()).decode(),
            "sha": sha, "branch": AUTOFIX_BRANCH,
        })
    call("POST", f"/repos/{repo}/pulls", {
        "title": "ci: reference juninmd/base-actions by @main",
        "head": AUTOFIX_BRANCH, "base": base,
        "body": "Politica da frota: `juninmd/base-actions` sempre por `@main`, para que "
                "correcoes centrais cheguem a todos os repos no proximo run.\n\n"
                "Aberto pela manutencao diaria (`daily-maintenance.yml`).",
    })


def guard_prs(repo: str, actions: list[str]) -> None:
    """Repo sem base-actions: PR aberto que tambem nao adiciona vira draft + request changes."""
    for pr in paginate(f"/repos/{repo}/pulls?state=open", limit=100):
        if pr.get("draft"):
            continue
        if audit.references_base_actions(read_workflows(repo, pr["head"]["sha"])):
            continue
        actions.append(f"{repo}#{pr['number']}: request changes + draft")
        if DRY_RUN:
            continue
        try:
            call("POST", f"/repos/{repo}/pulls/{pr['number']}/reviews",
                 {"event": "REQUEST_CHANGES", "body": GUARD_TEXT})
        except urllib.error.HTTPError:  # dono do token = autor do PR: GitHub recusa review
            call("POST", f"/repos/{repo}/issues/{pr['number']}/comments", {"body": GUARD_TEXT})
        call("POST", "/graphql", {
            "query": "mutation($id:ID!){convertPullRequestToDraft(input:{pullRequestId:$id}){clientMutationId}}",
            "variables": {"id": pr["node_id"]},
        })


def scan_repo(info: dict, actions: list[str]) -> dict:
    repo, branch = info["full_name"], info["default_branch"]
    if GUARD_ONLY:
        if info["open_issues_count"]:  # inclui PRs; evita listar PR de repo sem nada aberto
            if not audit.references_base_actions(read_workflows(repo, branch)):
                guard_prs(repo, actions)
        return {"repo": repo, "workflows": 0, "base": True, "findings": {k: [] for k in
                ("base_pinned", "third_party_unpinned", "no_permissions", "no_timeout", "no_concurrency", "cron")},
                "failing": [], "slow": []}
    workflows = read_workflows(repo, branch)
    runs = paginate(f"/repos/{repo}/actions/runs?branch={branch}&exclude_pull_requests=true",
                    key="workflow_runs", limit=100) if workflows else []
    row = {"repo": repo, "workflows": len(workflows), "base": audit.references_base_actions(workflows),
           "findings": audit.audit_workflows(workflows),
           "failing": failing_runs(repo, branch, runs),
           "slow": audit.slow_workflows(runs, SLOW_MINUTES)}
    rerun_infra(repo, row["failing"], actions)
    autofix_pins(repo, info, workflows, actions)
    if not row["base"]:
        guard_prs(repo, actions)
    return row


def render(rows: list[dict], actions: list[str], errors: list[str]) -> str:
    red = [(r["repo"], f) for r in rows for f in r["failing"]]
    lines = [f"## Manutencao diaria da frota ({'dry-run' if DRY_RUN else 'aplicado'})", "",
             f"Repos: **{len(rows)}** | sem base-actions: **{sum(not r['base'] for r in rows)}** | "
             f"pipelines vermelhas: **{len(red)}** | acoes: **{len(actions)}** | erros: **{len(errors)}**", ""]
    if red:
        lines += ["### Pipelines vermelhas (branch default)", "", "| Repo | Workflow | Causa |", "|---|---|---|"]
        lines += [f"| {r} | [{f['path']}]({f['url']}) | {f['kind']} |" for r, f in red]
        lines.append("")
    titles = {"base_pinned": "base-actions sem @main", "third_party_unpinned": "Action de terceiro sem SHA",
              "no_permissions": "Sem `permissions:` no topo", "no_timeout": "Job sem `timeout-minutes`",
              "no_concurrency": "PR sem `concurrency`", "cron": "Cron (politica no-cron)"}
    for key, title in titles.items():
        hits = [(r["repo"], h) for r in rows for h in r["findings"][key]]
        if hits:
            lines += [f"<details><summary>{title} ({len(hits)})</summary>", ""]
            lines += [f"- {r}: `{h}`" for r, h in hits[:200]] + ["", "</details>", ""]
    slow = [(r["repo"], p, m) for r in rows for p, m in r["slow"]]
    if slow:
        lines += [f"### Workflows lentos (> {SLOW_MINUTES:g} min em media)", ""]
        lines += [f"- {r}: `{p}` ~{m} min" for r, p, m in slow] + [""]
    for title, items in (("Acoes", actions), ("Erros de varredura", errors)):
        if items:
            lines += [f"### {title}", ""] + [f"- {i}" for i in items] + [""]
    return "\n".join(lines)


def upsert_issue(body: str) -> None:
    title = "Relatorio diario da frota (base-actions)"
    found = [i for i in paginate(f"/repos/{REPORT_REPO}/issues?state=open&labels=fleet-report", limit=50)
             if i["title"] == title]
    if found:
        call("PATCH", f"/repos/{REPORT_REPO}/issues/{found[0]['number']}", {"body": body})
    else:
        call("POST", f"/repos/{REPORT_REPO}/issues", {"title": title, "body": body, "labels": ["fleet-report"]})


def main() -> int:
    if not TOKEN:
        print("::error::FLEET_TOKEN ausente: configure o secret (PAT fine-grained, ver workflow).")
        return 1
    rows, actions, errors = [], [], []
    for info in list_repos():
        try:
            rows.append(scan_repo(info, actions))
        except (urllib.error.URLError, KeyError, ValueError) as err:
            errors.append(f"{info['full_name']}: {err}")
    report = render(rows, actions, errors)
    summary = env("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as fh:
            fh.write(report + "\n")
    print(report)
    if not DRY_RUN and not GUARD_ONLY:
        upsert_issue(report)
    return 1 if errors and len(errors) == len(rows) + len(errors) else 0


if __name__ == "__main__":
    sys.exit(main())
