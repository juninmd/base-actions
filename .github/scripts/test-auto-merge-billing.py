#!/usr/bin/env python3
"""billing_only (auto_merge_billing_blocked.py) contra uma API falsa: sem rede."""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(__file__))
import auto_merge_billing_blocked as m  # noqa: E402

BILLING = [{"message": "The job was not started because recent account payments have failed"}]
failures = []


def check(name, cond):
    if not cond:
        failures.append(name)


def fake_api(runs, ignore_page=False):
    def api(path, check=True):
        if "/annotations" in path:
            run_id = int(path.split("/check-runs/")[1].split("/")[0])
            return BILLING if runs[run_id]["billing"] else [{"message": "AssertionError"}]
        page = int((re.search(r"[?&]page=(\d+)", path) or [0, 1])[1])
        size = int(re.search(r"per_page=(\d+)", path)[1])
        start = 0 if ignore_page else (page - 1) * size
        batch = [{"id": i, "name": f"c{i}", "status": "completed", "conclusion": "failure"}
                 for i in range(start, min(start + size, len(runs)))]
        return {"total_count": len(runs), "check_runs": batch}
    return api


PR = {"number": 1, "head": {"sha": "a" * 40}, "base": {"repo": {"full_name": "o/r"}}}

m.api = fake_api([{"billing": True}] * 100 + [{"billing": False}] + [{"billing": True}] * 49)
check("falha real na pagina 2 bloqueia o merge", m.billing_only(PR) is False)

m.api = fake_api([{"billing": True}] * 150)
check("150 falhas de billing em 2 paginas liberam", m.billing_only(PR) is True)

m.api = fake_api([{"billing": True}] * 150, ignore_page=True)
check("API que nao avanca a pagina falha fechado", m.billing_only(PR) is False)

m.api = fake_api([{"billing": True}] * 3)
check("pagina unica de billing libera", m.billing_only(PR) is True)

if failures:
    print("FAIL:", *failures, sep="\n  ")
    sys.exit(1)
print("auto-merge-billing: ok")
