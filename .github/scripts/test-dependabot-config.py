#!/usr/bin/env python3
"""Politica de Dependabot da frota (dependabot_config.py): sem rede."""
import os
import sys

import yaml

sys.path.insert(0, os.path.dirname(__file__))
import dependabot_config as d  # noqa: E402

failures = []


def check(name, cond):
    if not cond:
        failures.append(name)


LEGACY = """version: 2
updates:
  # comentario do repo que precisa sobreviver
  - package-ecosystem: npm
    directory: /
    schedule:
      interval: daily
    open-pull-requests-limit: 20
    commit-message:
      prefix: deps
  - package-ecosystem: cargo
    directory: /
    schedule:
      interval: weekly
"""

text, changes, blockers = d.normalize_text(LEGACY)
doc = yaml.safe_load(text)
entries = {e["package-ecosystem"]: e for e in doc["updates"]}
check("sem blocker em config padrao", blockers == [])
check("npm e cargo entraram nas mudancas", set(changes) == {"npm", "cargo"})
check("npm semanal", entries["npm"]["schedule"]["interval"] == "weekly")
check("grupo catch-all npm", entries["npm"]["groups"] == {"npm": {"patterns": ["*"]}})
check("grupo por ecossistema", entries["cargo"]["groups"] == {"cargo": {"patterns": ["*"]}})
check("directory preservado", entries["npm"]["directory"] == "/")
check("comentario preservado", "# comentario do repo que precisa sobreviver" in text)
check("indentacao do repo preservada", text.splitlines()[3].startswith("  - package-ecosystem: npm"))
check("politica nao mexe no que o repo escolheu",
      entries["npm"]["open-pull-requests-limit"] == 20 and entries["npm"]["commit-message"]["prefix"] == "deps")
check("sem cooldown inventado", "cooldown" not in entries["npm"])

again, changes2, _ = d.normalize_text(text)
check("idempotente", changes2 == {} and again == text)

# grupo customizado e limite proprio ficam como estao
CUSTOM = """version: 2
updates:
  - package-ecosystem: npm
    directory: /
    schedule: {interval: monthly}
    groups:
      react:
        patterns: ['react*']
    open-pull-requests-limit: 3
"""
ctext, cchanges, _ = d.normalize_text(CUSTOM)
cdoc = yaml.safe_load(ctext)
check("grupo customizado preservado", cdoc["updates"][0]["groups"] == {"react": {"patterns": ["react*"]}})
check("limite proprio preservado", cdoc["updates"][0]["open-pull-requests-limit"] == 3)
check("interval inline corrigido", cdoc["updates"][0]["schedule"] == {"interval": "weekly"})
check("grupo customizado nao conta como mudanca", cchanges == {"npm": ["schedule=weekly"]})

# decisao do repo (ignore/allow/registries/target-branch/vendor) bloqueia sem alterar texto
for key, value in (("ignore", [{"dependency-name": "x"}]), ("registries", ["*"]),
                   ("target-branch", "next"), ("allow", [{"dependency-type": "direct"}]),
                   ("vendor", True)):
    doc_in = {"version": 2, "updates": [
        {"package-ecosystem": "pip", "directory": "/", "schedule": {"interval": "daily"}, key: value}]}
    out, ch, bl = d.normalize_text(yaml.safe_dump(doc_in))
    check(f"blocker {key}", bool(bl) and not ch and yaml.safe_load(out) == doc_in)

# arquivo invalido / estrutura inesperada nao explodem
check("YAML invalido vira blocker", d.normalize_text("updates: [")[2] != [])
check("sem updates vira blocker", d.normalize_text("version: 1\n")[2] != [])
check("item sem ecosystem vira blocker", d.normalize_text(
    "version: 2\nupdates:\n  - directory: /\n")[2] != [])
check("estilo flow e normalizado", d.normalize_text(
    "version: 2\nupdates:\n  - {package-ecosystem: npm, directory: /, schedule: {interval: daily}}\n")[2] == [])
flow_out = d.normalize_text(
    "version: 2\nupdates:\n  - {package-ecosystem: npm, directory: /, schedule: {interval: daily}}\n")[0]
flow_doc = yaml.safe_load(flow_out)
check("flow virou semanal", flow_doc["updates"][0]["schedule"] == {"interval": "weekly"})
check("flow ganhou grupo", flow_doc["updates"][0]["groups"] == {"npm": {"patterns": ["*"]}})

# `directories:` (plural) dos repos de actions continua la
DIRS = """version: 2
updates:
  - package-ecosystem: github-actions
    directories:
      - /
      - /deploy
    schedule:
      interval: weekly
"""
dtext, _, dbl = d.normalize_text(DIRS)
check("directories preservado", yaml.safe_load(dtext)["updates"][0]["directories"] == ["/", "/deploy"] and not dbl)
check("lista de directories nao vira grupo",
      yaml.safe_load(dtext)["updates"][0]["groups"] == {"github-actions": {"patterns": ["*"]}})

check("nome de grupo saneado", d.group_name("GitHub Actions@v2") == "github-actions-v2")
check("verify aceita politica completa", d.verify(yaml.safe_load(text)))
check("verify recusa diario", not d.verify({"updates": [{"schedule": {"interval": "daily"}, "groups": {"a": {}}}]}))

if failures:
    print("FALHOU: " + "; ".join(failures))
    sys.exit(1)
print("ok: politica de dependabot")
