#!/usr/bin/env python3
"""Padroniza `.github/dependabot.yml` da frota (daily-maintenance.yml).

Dependabot nao herda configuracao de um repo para outro: cada repo precisa do
proprio arquivo. Este script aplica, nos repos publicos do owner, a mesma
politica -- editando o YAML no lugar, para preservar comentarios e o estilo de
cada repo:

- `schedule.interval: weekly` -- PR de dependencia so 1x por semana;
- `groups` com catch-all por ecossistema -- 1 PR por ecossistema, nao 20.

O resto do arquivo (cooldown, limite de PRs, prefixo de commit, grupos proprios,
comentarios) e preservado como esta: a politica so impoe o que o Dependabot nao
tem como herdar de outro repo.

Abre um PR por repo que divergir (branch `chore/dependabot-weekly`). Repo com
customizacao que o script nao sabe preservar (ignore/allow/registries/
target-branch/vendor) fica intocado e entra no relatorio. So escreve com
`BOT_DRY_RUN=false`.
"""

from __future__ import annotations

import base64
import copy
import json
import os
import re
import sys
import urllib.error
import urllib.request

import yaml

sys.dont_write_bytecode = True

API = "https://api.github.com"
CONFIG_PATH = ".github/dependabot.yml"
BRANCH = "chore/dependabot-weekly"
TITLE = "chore(deps): padronizar Dependabot (semanal e agrupado)"
ENTRY_RE = re.compile(r"^(?P<indent>[ ]*)-\s+package-ecosystem:\s*(?P<eco>[A-Za-z0-9-]+)\s*$")
# Chaves que carregam decisao do repo e que este script nao tenta adivinhar.
BLOCKER_KEYS = (
    "registries",
    "vendor",
    "target-branch",
    "insecure-external-code-execution",
    "ignore",
    "allow",
)


def env(name: str, default: str = "") -> str:
    return os.environ.get(name, "").strip() or default


TOKEN = env("GH_TOKEN")
OWNER = env("BOT_OWNER", "juninmd")
ONLY_REPO = env("BOT_REPOSITORY")
DRY_RUN = env("BOT_DRY_RUN", "true").lower() != "false"
MAX_REPOS = int(env("BOT_MAX_REPOS", "300"))


def call(method: str, path: str, body: dict | None = None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(f"{API}{path}", data=data, method=method)
    req.add_header("Authorization", f"Bearer {TOKEN}")
    req.add_header("Accept", "application/vnd.github+json")
    if data is not None:
        req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=30) as resp:
        raw = resp.read()
    return json.loads(raw) if raw else {}


def get_or_none(path: str):
    try:
        return call("GET", path)
    except urllib.error.HTTPError as err:
        if err.code == 404:
            return None
        raise


def paginate(path: str, limit: int = 1000) -> list:
    out, page = [], 1
    while len(out) < limit:
        sep = "&" if "?" in path else "?"
        chunk = call("GET", f"{path}{sep}per_page=100&page={page}")
        if not chunk:
            break
        out.extend(chunk)
        if len(chunk) < 100:
            break
        page += 1
    return out[:limit]


def group_name(ecosystem: str) -> str:
    return re.sub(r"[^a-z0-9-]+", "-", ecosystem.lower()).strip("-") or "deps"


def indent_of(line: str) -> int:
    return len(line) - len(line.lstrip(" "))


def insert_after(lines: list[str], index: int, new: list[str]) -> None:
    lines[index + 1:index + 1] = new


def find_key(lines: list[str], start: int, end: int, key: str, indent: int) -> int:
    """Indice da linha `key:` exatamente no indent pedido, ou -1."""
    for i in range(start, end):
        if indent_of(lines[i]) == indent and lines[i].lstrip().startswith(f"{key}:"):
            return i
    return -1


def block_end(lines: list[str], start: int) -> int:
    """Fim do bloco de um item de `updates` (proxima linha de indentacao igual ou menor)."""
    base = indent_of(lines[start])
    for i in range(start + 1, len(lines)):
        stripped = lines[i].strip()
        if not stripped or stripped.startswith("#"):
            continue
        if indent_of(lines[i]) <= base:
            return i
    return len(lines)


def normalize_entry(lines: list[str], start: int, eco: str) -> list[str]:
    """Edita o bloco do item em `start` no lugar. Retorna a lista de campos alterados."""
    child = indent_of(lines[start]) + 2
    pad = " " * child
    changed: list[str] = []

    end = block_end(lines, start)
    sched = find_key(lines, start, end, "schedule", child)
    if sched < 0:
        insert_after(lines, start, [f"{pad}schedule:\n", f"{pad}  interval: weekly\n"])
        changed.append("schedule=weekly")
    elif lines[sched].split(":", 1)[1].strip():
        # `schedule: {interval: monthly}` -- preserva as outras chaves inline
        inline = lines[sched].rstrip("\n")
        fixed = re.sub(r"interval:\s*[^,}]+", "interval: weekly", inline, count=1)
        if "interval: weekly" in fixed:
            lines[sched] = fixed + "\n"
            changed.append("schedule=weekly")
    else:
        found = False
        for i in range(sched + 1, end):
            if indent_of(lines[i]) > child and lines[i].lstrip().startswith("interval:"):
                found = True
                if lines[i].split(":", 1)[1].strip().strip("'\"") != "weekly":
                    lines[i] = f"{' ' * indent_of(lines[i])}interval: weekly\n"
                    changed.append("schedule=weekly")
                break
        if not found:
            insert_after(lines, sched, [f"{pad}  interval: weekly\n"])
            changed.append("schedule=weekly")

    end = block_end(lines, start)
    if find_key(lines, start, end, "groups", child) < 0:
        insert_after(lines, end - 1, [
            f"{pad}groups:\n", f"{pad}  {group_name(eco)}:\n", f"{pad}    patterns: ['*']\n",
        ])
        changed.append("groups=catch-all")
    return changed


def normalize_text(text: str) -> tuple[str, dict[str, list[str]], list[str]]:
    """Retorna (texto normalizado, mudancas por ecossistema, blockers)."""
    try:
        doc = yaml.safe_load(text)
    except yaml.YAMLError as err:
        return text, {}, [f"YAML invalido ({err.problem})"]
    if not isinstance(doc, dict) or not isinstance(doc.get("updates"), list):
        return text, {}, ["estrutura inesperada (sem `updates`)"]
    blockers = [f"chave de topo customizada ({k})" for k in BLOCKER_KEYS if k in doc]
    for entry in doc["updates"]:
        if not isinstance(entry, dict) or "package-ecosystem" not in entry:
            blockers.append("item de `updates` sem `package-ecosystem`")
            continue
        custom = [k for k in BLOCKER_KEYS if k in entry]
        if custom:
            blockers.append(f"{entry['package-ecosystem']}: chave customizada ({', '.join(custom)})")
    if blockers:
        return text, {}, blockers

    lines = text.splitlines(keepends=True)
    changes: dict[str, list[str]] = {}
    # de tras para frente: inserir num bloco nao desloca os blocos anteriores
    starts = [i for i, line in enumerate(lines) if ENTRY_RE.match(line)]
    if len(starts) != len(doc["updates"]):
        # item em flow (`- {package-ecosystem: npm, ...}`): reescreve o documento
        # inteiro pelo YAML parseado. Perde comentario, ganha a politica.
        return normalize_doc(doc, text)
    for start in reversed(starts):
        eco = ENTRY_RE.match(lines[start]).group("eco")
        changed = normalize_entry(lines, start, eco)
        if changed:
            changes.setdefault(eco, []).extend(changed)
    new_text = "".join(lines)
    if not new_text.endswith("\n"):
        new_text += "\n"
    try:
        result = yaml.safe_load(new_text)
    except yaml.YAMLError:
        return normalize_doc(doc, text)
    if not verify(result):
        return normalize_doc(doc, text)
    return new_text, changes, []


def normalize_doc(doc: dict, text: str) -> tuple[str, dict[str, list[str]], list[str]]:
    """Fallback: normaliza o documento parseado e serializa de novo."""
    doc = copy.deepcopy(doc)
    changes: dict[str, list[str]] = {}
    for entry in doc["updates"]:
        changed: list[str] = []
        schedule = entry.get("schedule") if isinstance(entry.get("schedule"), dict) else {}
        if schedule.get("interval") != "weekly":
            entry["schedule"] = {**schedule, "interval": "weekly"}
            changed.append("schedule=weekly")
        if not entry.get("groups"):
            entry["groups"] = {group_name(entry["package-ecosystem"]): {"patterns": ["*"]}}
            changed.append("groups=catch-all")
        if changed:
            changes.setdefault(entry["package-ecosystem"], []).extend(changed)
    if not changes:
        return text, {}, []
    new_text = yaml.safe_dump(doc, sort_keys=False, allow_unicode=True, width=100)
    if not verify(yaml.safe_load(new_text)):
        return text, {}, ["normalizacao geraria config fora da politica"]
    return new_text, changes, []


def verify(doc: dict) -> bool:
    """Confere a politica no documento resultante."""
    if not isinstance(doc, dict) or not isinstance(doc.get("updates"), list):
        return False
    for entry in doc["updates"]:
        if (entry.get("schedule") or {}).get("interval") != "weekly":
            return False
        if not entry.get("groups"):
            return False
    return True


def read_config(repo: str, ref: str) -> str | None:
    blob = get_or_none(f"/repos/{repo}/contents/{CONFIG_PATH}?ref={ref}")
    return None if blob is None else base64.b64decode(blob["content"]).decode("utf-8")


def open_pr(repo: str, info: dict, text: str, changes: dict[str, list[str]]) -> str:
    base = info["default_branch"]
    head_sha = call("GET", f"/repos/{repo}/git/ref/heads/{base}")["object"]["sha"]
    call("POST", f"/repos/{repo}/git/refs", {"ref": f"refs/heads/{BRANCH}", "sha": head_sha})
    current = call("GET", f"/repos/{repo}/contents/{CONFIG_PATH}?ref={BRANCH}")
    call("PUT", f"/repos/{repo}/contents/{CONFIG_PATH}", {
        "message": TITLE,
        "content": base64.b64encode(text.encode()).decode(),
        "sha": current["sha"], "branch": BRANCH,
    })
    detail = "\n".join(f"- `{eco}`: {', '.join(items)}" for eco, items in sorted(changes.items()))
    call("POST", f"/repos/{repo}/pulls", {
        "title": TITLE, "head": BRANCH, "base": base,
        "body": ("Politica da frota para Dependabot: **1 PR por semana**, **agrupado por "
                 "ecossistema**.\n\nMudancas aplicadas:\n" + detail +
                 "\n\nAberto pela manutencao diaria (`daily-maintenance.yml`). "
                 "Comentarios e configuracoes proprias do repo foram preservados."),
    })
    return f"{repo}: PR aberto ({len(changes)} ecossistema(s))"


def main() -> int:
    if not TOKEN:
        print("::error::FLEET_TOKEN ausente: configure o secret (PAT fine-grained, ver workflow).")
        return 1
    repos = ([call("GET", f"/repos/{ONLY_REPO}")] if ONLY_REPO
             else paginate(f"/users/{OWNER}/repos?type=owner&sort=pushed", MAX_REPOS))
    actions, skipped, errors = [], [], []
    for info in repos:
        if info["archived"] or info["fork"] or info["disabled"] or info["private"]:
            continue
        repo = info["full_name"]
        try:
            text = read_config(repo, info["default_branch"])
            if text is None:
                skipped.append(f"{repo}: sem {CONFIG_PATH}")
                continue
            new_text, changes, blockers = normalize_text(text)
            if blockers:
                skipped.append(f"{repo}: {ordinal(blockers)}")
                continue
            if not changes or new_text == text:
                continue
            if get_or_none(f"/repos/{repo}/branches/{BRANCH}"):
                skipped.append(f"{repo}: branch {BRANCH} ja existe")
                continue
            if DRY_RUN:
                actions.append(f"{repo}: " + ", ".join(f"{e}={len(c)}" for e, c in changes.items()))
                continue
            actions.append(open_pr(repo, info, new_text, changes))
        except (urllib.error.URLError, KeyError, ValueError) as err:
            errors.append(f"{repo}: {err}")
    header = f"## Dependabot padronizado ({'dry-run' if DRY_RUN else 'aplicado'})"
    body = [header, "", f"Repos alterados: **{len(actions)}** | pulados: **{len(skipped)}** | erros: **{len(errors)}**", ""]
    body += [f"- {a}" for a in actions]
    if skipped:
        body += ["", "<details><summary>Pulados</summary>", ""] + [f"- {s}" for s in skipped] + ["", "</details>"]
    if errors:
        body += ["", "### Erros", ""] + [f"- {e}" for e in errors]
    report = "\n".join(body)
    summary = env("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as fh:
            fh.write(report + "\n")
    print(report)
    return 1 if errors else 0


def ordinal(items: list[str]) -> str:
    return "; ".join(sorted(set(items)))


if __name__ == "__main__":
    sys.exit(main())
