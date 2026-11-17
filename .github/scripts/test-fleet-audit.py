#!/usr/bin/env python3
"""Regras puras da manutencao diaria (fleet_audit.py): sem rede."""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
import fleet_audit as a  # noqa: E402

SHA = "a" * 40
failures = []


def check(name, cond):
    if not cond:
        failures.append(name)


wf = {
    "w.yml": f"""on: [pull_request]
jobs:
  a:
    uses: juninmd/base-actions/.github/workflows/reusable-validate.yml@{SHA}
  b:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@{SHA}
""",
}
f = a.audit_workflows(wf)
check("base pinada detectada", len(f["base_pinned"]) == 1)
check("terceiro sem SHA so o checkout", [x for x in f["third_party_unpinned"]] == ["w.yml: actions/checkout@v4"])
check("sem permissions", f["no_permissions"] == ["w.yml"])
check("job com runner sem timeout", f["no_timeout"] == ["w.yml"])
check("PR sem concurrency", f["no_concurrency"] == ["w.yml"])
check("reusable nao conta como runner", a.audit_workflows({"x.yml": "jobs:\n  a:\n    uses: ./x\n"})["no_timeout"] == [])
check("cron", a.audit_workflows({"c.yml": "on:\n  schedule:\n    - cron: '0 7 * * *'\n"})["cron"] == ["c.yml"])

fixed = a.repin_to_main(wf["w.yml"])
check("repin troca sha por main", "reusable-validate.yml@main" in fixed and SHA in fixed)  # SHA do setup-node fica
check("repin e idempotente", a.repin_to_main(fixed) == fixed)
check("repin nao toca terceiro", "actions/checkout@v4" in fixed)
check("usa base", a.references_base_actions(wf))
check("nao usa base", not a.references_base_actions({"n.yml": "jobs:\n  a:\n    uses: actions/x@v1\n"}))

check("billing", a.classify_failure(["The job was not started because recent account payments have failed"], "failure") == "billing")
check("infra", a.classify_failure(["The job was not acquired by Runner of type hosted"], "cancelled") == "infra")
check("code", a.classify_failure([], "failure") == "code")

runs = [
    {"path": "p", "event": "push", "created_at": "2026-01-01T00:00:00Z", "conclusion": "failure"},
    {"path": "p", "event": "push", "created_at": "2026-01-02T00:00:00Z", "conclusion": "success"},
    {"path": "q", "event": "pull_request", "created_at": "2026-01-02T00:00:00Z", "conclusion": "failure"},
]
check("ultima run por workflow, sem PR", [r["conclusion"] for r in a.latest_per_workflow(runs)] == ["success"])
slow = a.slow_workflows([{"path": "p", "conclusion": "success", "run_started_at": "2026-01-01T00:00:00Z",
                          "updated_at": "2026-01-01T00:30:00Z"}], 15)
check("workflow lento", slow == [("p", 30.0)])

if failures:
    print("FAIL:", *failures, sep="\n  ")
    sys.exit(1)
print("fleet-audit: ok")
