#!/usr/bin/env python3
"""Baixa o texto que vive FORA do git (issues, PRs, comentarios, reviews,
releases) para arquivos, para o Gitleaks e o TruffleHog varrerem.

Segredo colado em comentario nao passa por nenhum gate de codigo: nao esta no
historico git, entao nem o security-scan nem o sast enxergam. Aqui cada texto
vira um arquivo e um indice (index.json) liga o arquivo a URL de origem.

Modos:
  event  le so o payload do evento (GITHUB_EVENT_PATH) — zero chamada de API,
         serve para issue_comment / issues / pull_request_review(_comment) /
         pull_request / release / discussion(_comment)
  full   pagina a API do repositorio inteiro (opcionalmente desde SINCE)
  auto   event quando o evento carrega texto, senao full

Todo texto e tratado como DADO: nunca e interpolado em shell nem avaliado.
So usa a biblioteca padrao (roda no python3 do runner, sem pip).
"""
from __future__ import annotations

import datetime as dt
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

API = os.environ.get("GITHUB_API_URL", "https://api.github.com").rstrip("/")
REPO = os.environ.get("SCAN_REPOSITORY") or os.environ.get("GITHUB_REPOSITORY", "")
TOKEN = os.environ.get("GH_TOKEN", "")
MODE = (os.environ.get("SCAN_MODE") or "auto").strip().lower()
SINCE = (os.environ.get("SCAN_SINCE") or "").strip()
OUT = Path(os.environ.get("SCAN_OUT") or "gh-text-dump")
EVENT_PATH = os.environ.get("SCAN_EVENT_PATH") or os.environ.get("GITHUB_EVENT_PATH", "")
MAX_ITEMS = int(os.environ.get("SCAN_MAX_ITEMS") or "20000")
INCLUDE_REVIEWS = (os.environ.get("SCAN_INCLUDE_REVIEWS") or "true").lower() == "true"

# chaves do payload que carregam texto escrito por pessoas
EVENT_KEYS = ("comment", "issue", "pull_request", "review", "release", "discussion", "answer")

index: dict[str, dict] = {}


def fail(msg: str) -> "None":
    print(f"::error::{msg}")
    raise SystemExit(1)


def save(kind: str, ident, text: str, url: str, author: str = "", updated: str = "") -> None:
    """Grava um texto. Nome previsivel e sem nada vindo do conteudo."""
    if not text or not text.strip():
        return
    if len(index) >= MAX_ITEMS:
        return
    safe_id = re.sub(r"[^0-9A-Za-z_-]", "_", str(ident))[:80]
    rel = f"{kind}-{safe_id}.txt"
    (OUT / rel).write_text(text, encoding="utf-8", errors="replace")
    index[rel] = {"kind": kind, "url": url or "", "author": author or "", "updated": updated or ""}


def login(obj: dict) -> str:
    return ((obj or {}).get("user") or (obj or {}).get("author") or {}).get("login", "") or ""


def text_of(*parts) -> str:
    return "\n\n".join(p for p in parts if isinstance(p, str) and p.strip())


# ─── modo evento ────────────────────────────────────────────────────────────
def from_event() -> int:
    if not EVENT_PATH or not os.path.isfile(EVENT_PATH):
        return 0
    with open(EVENT_PATH, encoding="utf-8") as fh:
        event = json.load(fh)
    before = len(index)
    for key in EVENT_KEYS:
        obj = event.get(key)
        if not isinstance(obj, dict):
            continue
        save(
            f"event-{key.replace('_', '-')}",
            obj.get("id") or obj.get("number") or key,
            text_of(obj.get("title"), obj.get("name"), obj.get("body")),
            obj.get("html_url", ""),
            login(obj),
            obj.get("updated_at") or obj.get("submitted_at") or "",
        )
    # edicao: o texto ANTERIOR tambem vem no payload e continua no historico de
    # edicoes do GitHub — editar o comentario nao apaga o segredo.
    changes = event.get("changes")
    if isinstance(changes, dict):
        for field, change in changes.items():
            if isinstance(change, dict) and isinstance(change.get("from"), str):
                target = next((event[k] for k in EVENT_KEYS if isinstance(event.get(k), dict)), {})
                save(
                    f"event-previous-{re.sub(r'[^a-z]', '', field.lower()) or 'text'}",
                    target.get("id") or target.get("number") or "edit",
                    change["from"],
                    target.get("html_url", ""),
                    login(target),
                )
    return len(index) - before


# ─── modo completo ──────────────────────────────────────────────────────────
def since_iso() -> str:
    """SINCE aceita '30d' (dias para tras) ou uma data ISO-8601."""
    if not SINCE:
        return ""
    m = re.fullmatch(r"(\d{1,4})d", SINCE)
    if m:
        when = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=int(m.group(1)))
        return when.strftime("%Y-%m-%dT%H:%M:%SZ")
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}(T\d{2}:\d{2}:\d{2}Z)?", SINCE):
        return SINCE if "T" in SINCE else SINCE + "T00:00:00Z"
    fail(f"input `since` invalido: '{SINCE}' (use '30d' ou data ISO, ex. 2026-01-31)")
    return ""


def request(url: str):
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "base-actions-comments-scan",
    }
    if TOKEN:
        headers["Authorization"] = f"Bearer {TOKEN}"
    last = ""
    for attempt in range(4):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=60) as resp:
                return json.load(resp), resp.headers.get("Link", "")
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", "replace")[:300]
            last = f"HTTP {exc.code}: {body}"
            remaining = exc.headers.get("X-RateLimit-Remaining")
            if exc.code in (403, 429) and (remaining == "0" or exc.headers.get("Retry-After")):
                wait = int(exc.headers.get("Retry-After") or 0)
                if not wait:
                    wait = max(1, int(exc.headers.get("X-RateLimit-Reset") or 0) - int(time.time()))
                if wait > 300:
                    break
                time.sleep(wait + 1)
                continue
            if exc.code in (500, 502, 503, 504):
                time.sleep(2 * (attempt + 1))
                continue
            break
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            last = str(exc)
            time.sleep(2 * (attempt + 1))
    path = urllib.parse.urlparse(url).path
    hint = ""
    if "403" in last or "404" in last:
        hint = (
            " — o job precisa de `permissions: contents: read, issues: read, "
            "pull-requests: read` (em repo privado o token nao le issue/PR sem isso)"
        )
    # Falha fechada: endpoint que nao pode ser lido NAO vira "nada encontrado".
    fail(f"nao foi possivel ler {path}: {last}{hint}")


def paginate(path: str, params: dict):
    query = urllib.parse.urlencode({k: v for k, v in params.items() if v})
    url = f"{API}/repos/{REPO}/{path}" + (f"?{query}" if query else "")
    while url:
        data, link = request(url)
        if not isinstance(data, list):
            return
        yield from data
        if len(index) >= MAX_ITEMS:
            return
        nxt = re.search(r'<([^>]+)>;\s*rel="next"', link or "")
        url = nxt.group(1) if nxt else ""
        # so segue paginacao dentro da propria API: o header nao e confiavel
        # para apontar o token a outro host
        if url and not url.startswith(API + "/"):
            return


def from_api() -> int:
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", REPO):
        fail(f"repositorio invalido: '{REPO}'")
    since = since_iso()
    before = len(index)
    pulls: list[int] = []

    # /issues devolve issues E pull requests (titulo + corpo)
    for item in paginate("issues", {"state": "all", "per_page": 100, "since": since}):
        is_pr = "pull_request" in item
        if is_pr:
            pulls.append(item["number"])
        save(
            "pull-request" if is_pr else "issue",
            item["number"],
            text_of(item.get("title"), item.get("body")),
            item.get("html_url", ""),
            login(item),
            item.get("updated_at", ""),
        )
    # comentarios de issue e a conversa de PR
    for c in paginate("issues/comments", {"per_page": 100, "since": since}):
        save("issue-comment", c["id"], c.get("body") or "", c.get("html_url", ""), login(c), c.get("updated_at", ""))
    # comentarios de review em linha de codigo
    for c in paginate("pulls/comments", {"per_page": 100, "since": since}):
        save("review-comment", c["id"], c.get("body") or "", c.get("html_url", ""), login(c), c.get("updated_at", ""))
    # comentarios em commit (a API nao filtra por data)
    for c in paginate("comments", {"per_page": 100}):
        if since and (c.get("updated_at") or "") < since:
            continue
        save("commit-comment", c["id"], c.get("body") or "", c.get("html_url", ""), login(c), c.get("updated_at", ""))
    # notas de release
    for r in paginate("releases", {"per_page": 100}):
        if since and (r.get("published_at") or r.get("created_at") or "") < since:
            continue
        save("release", r["id"], text_of(r.get("name"), r.get("body")), r.get("html_url", ""), login(r), r.get("published_at") or "")
    # corpo do review (o texto do "Approve / Request changes"): uma chamada por PR
    if INCLUDE_REVIEWS:
        for number in pulls:
            if len(index) >= MAX_ITEMS:
                break
            for rv in paginate(f"pulls/{number}/reviews", {"per_page": 100}):
                save("review", rv["id"], rv.get("body") or "", rv.get("html_url", ""), login(rv), rv.get("submitted_at") or "")
    return len(index) - before


def main() -> int:
    if MODE not in ("auto", "event", "full"):
        fail(f"input `mode` invalido: '{MODE}' (use auto, event ou full)")
    OUT.mkdir(parents=True, exist_ok=True)

    used = MODE
    count = 0
    if MODE in ("auto", "event"):
        count = from_event()
        used = "event"
        if MODE == "event" and count == 0:
            print("::notice::O evento nao carrega texto (comentario/issue/PR/review) — nada a varrer")
    if MODE == "full" or (MODE == "auto" and count == 0):
        used = "full"
        count = from_api()

    (OUT / "index.json").write_text(json.dumps(index, indent=1, sort_keys=True), encoding="utf-8")
    kinds: dict[str, int] = {}
    for meta in index.values():
        kinds[meta["kind"]] = kinds.get(meta["kind"], 0) + 1
    detail = ", ".join(f"{k}={v}" for k, v in sorted(kinds.items())) or "vazio"
    print(f"modo={used} textos={len(index)} ({detail})")
    if len(index) >= MAX_ITEMS:
        print(f"::warning::limite de {MAX_ITEMS} textos atingido — varredura parcial; use `since` para fatiar")
    out = os.environ.get("GITHUB_OUTPUT")
    if out:
        with open(out, "a", encoding="utf-8") as fh:
            fh.write(f"mode={used}\ncount={len(index)}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
