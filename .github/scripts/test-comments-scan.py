#!/usr/bin/env python3
"""Regressao do coletor do comments-scan (comments-scan/collect.py).

Sobe uma API falsa do GitHub em localhost e confere que:
  - o modo full pagina todos os endpoints e grava um arquivo por texto;
  - o indice liga cada arquivo a URL de origem;
  - o modo event le o payload (inclusive o texto ANTERIOR de uma edicao) sem
    tocar na API;
  - endpoint ilegivel (403) derruba a coleta em vez de virar "nada encontrado".

Sem rede e sem dependencia: roda no job de lint.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

COLLECT = Path(__file__).resolve().parents[2] / "comments-scan" / "collect.py"
REPO = "octo/demo"
calls: list[str] = []
deny: set[str] = set()


def routes(base: str) -> dict:
    return {
        f"/repos/{REPO}/issues": {
            1: [
                {"number": 1, "title": "bug", "body": "corpo da issue", "html_url": "https://gh.test/i/1", "user": {"login": "ana"}},
                {"number": 2, "title": "feat", "body": "corpo do PR", "html_url": "https://gh.test/p/2", "user": {"login": "bob"}, "pull_request": {}},
            ],
            2: [{"number": 3, "title": "so titulo", "body": None, "html_url": "https://gh.test/i/3", "user": {"login": "ana"}}],
        },
        f"/repos/{REPO}/issues/comments": {1: [{"id": 11, "body": "comentario em issue", "html_url": "https://gh.test/i/1#c11", "user": {"login": "eve"}}]},
        f"/repos/{REPO}/pulls/comments": {1: [{"id": 21, "body": "comentario de review", "html_url": "https://gh.test/p/2#r21", "user": {"login": "bob"}}]},
        f"/repos/{REPO}/comments": {1: [{"id": 31, "body": "comentario em commit", "html_url": "https://gh.test/c/31", "user": {"login": "ana"}}]},
        f"/repos/{REPO}/releases": {1: [{"id": 41, "name": "v1", "body": "notas", "html_url": "https://gh.test/r/41", "author": {"login": "ana"}}]},
        f"/repos/{REPO}/pulls/2/reviews": {1: [{"id": 51, "body": "corpo do review", "html_url": "https://gh.test/p/2#rv51", "user": {"login": "eve"}}]},
    }


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):  # silencio no log do CI
        pass

    def do_GET(self):
        parsed = urlparse(self.path)
        calls.append(parsed.path)
        base = f"http://127.0.0.1:{self.server.server_port}"
        table = routes(base).get(parsed.path)
        if parsed.path in deny or table is None:
            self.send_response(403 if parsed.path in deny else 404)
            self.end_headers()
            self.wfile.write(b'{"message":"Resource not accessible by integration"}')
            return
        page = int(parse_qs(parsed.query).get("page", ["1"])[0])
        body = json.dumps(table.get(page, [])).encode()
        self.send_response(200)
        if page + 1 in table:
            self.send_header("Link", f'<{base}{parsed.path}?page={page + 1}>; rel="next"')
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(body)


def run(out: Path, port: int, **env) -> subprocess.CompletedProcess:
    full = {
        "PATH": os.environ.get("PATH", ""),
        "GITHUB_API_URL": f"http://127.0.0.1:{port}",
        "GITHUB_REPOSITORY": REPO,
        "GH_TOKEN": "x",
        "SCAN_OUT": str(out),
        # o proxy do ambiente nao pode interceptar o localhost do teste
        "NO_PROXY": "127.0.0.1,localhost",
        "no_proxy": "127.0.0.1,localhost",
    }
    full.update(env)
    return subprocess.run([sys.executable, str(COLLECT)], env=full, capture_output=True, text=True)


def check(cond: bool, msg: str, failures: list[str]) -> None:
    if not cond:
        failures.append(msg)


def main() -> int:
    failures: list[str] = []
    server = HTTPServer(("127.0.0.1", 0), Handler)
    port = server.server_port
    threading.Thread(target=server.serve_forever, daemon=True).start()

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)

        # 1) full
        out = tmp_path / "full"
        proc = run(out, port, SCAN_MODE="full")
        check(proc.returncode == 0, f"full: exit {proc.returncode}: {proc.stdout}{proc.stderr}", failures)
        index = json.loads((out / "index.json").read_text()) if (out / "index.json").exists() else {}
        expected = {
            "issue-1.txt": "https://gh.test/i/1",
            "pull-request-2.txt": "https://gh.test/p/2",
            "issue-3.txt": "https://gh.test/i/3",  # veio da pagina 2: prova a paginacao
            "issue-comment-11.txt": "https://gh.test/i/1#c11",
            "review-comment-21.txt": "https://gh.test/p/2#r21",
            "commit-comment-31.txt": "https://gh.test/c/31",
            "release-41.txt": "https://gh.test/r/41",
            "review-51.txt": "https://gh.test/p/2#rv51",
        }
        for name, url in expected.items():
            check(name in index, f"full: faltou {name} (indice: {sorted(index)})", failures)
            check(index.get(name, {}).get("url") == url, f"full: URL errada em {name}", failures)
            check((out / name).is_file(), f"full: arquivo {name} nao gravado", failures)
        check("comentario em issue" in (out / "issue-comment-11.txt").read_text(), "full: corpo nao gravado", failures)
        check(index.get("issue-comment-11.txt", {}).get("author") == "eve", "full: autor nao gravado", failures)

        # 2) event: payload de comentario editado, sem nenhuma chamada de API
        calls.clear()
        event = tmp_path / "event.json"
        event.write_text(json.dumps({
            "action": "edited",
            "comment": {"id": 99, "body": "texto novo", "html_url": "https://gh.test/i/1#c99", "user": {"login": "eve"}},
            "issue": {"number": 1, "title": "bug", "body": "corpo", "html_url": "https://gh.test/i/1", "user": {"login": "ana"}},
            "changes": {"body": {"from": "texto ANTIGO com segredo"}},
        }))
        out = tmp_path / "event"
        proc = run(out, port, SCAN_MODE="auto", SCAN_EVENT_PATH=str(event))
        check(proc.returncode == 0, f"event: exit {proc.returncode}: {proc.stdout}{proc.stderr}", failures)
        index = json.loads((out / "index.json").read_text())
        check("event-comment-99.txt" in index, f"event: comentario ausente ({sorted(index)})", failures)
        check("event-issue-1.txt" in index, "event: issue ausente", failures)
        previous = [n for n in index if n.startswith("event-previous-")]
        check(len(previous) == 1 and "ANTIGO" in (out / previous[0]).read_text(), "event: texto anterior da edicao nao foi varrido", failures)
        check(not calls, f"event: nao deveria chamar a API (chamou {calls})", failures)

        # 3) auto sem texto no evento cai no full
        event.write_text(json.dumps({"schedule": "0 0 * * *"}))
        out = tmp_path / "auto"
        proc = run(out, port, SCAN_MODE="auto", SCAN_EVENT_PATH=str(event))
        check(proc.returncode == 0 and "modo=full" in proc.stdout, f"auto: deveria cair no full: {proc.stdout}", failures)

        # 4) falha fechada: endpoint negado derruba a coleta
        deny.add(f"/repos/{REPO}/issues/comments")
        proc = run(tmp_path / "deny", port, SCAN_MODE="full")
        check(proc.returncode != 0 and "::error::" in proc.stdout, "403 deveria derrubar a coleta, nao virar 'nada encontrado'", failures)
        deny.clear()

        # 5) entradas invalidas
        proc = run(tmp_path / "bad", port, SCAN_MODE="full", SCAN_SINCE="ontem; id")
        check(proc.returncode != 0, "since invalido deveria falhar", failures)
        proc = run(tmp_path / "bad2", port, SCAN_MODE="full", SCAN_REPOSITORY="../../etc")
        check(proc.returncode != 0, "repositorio invalido deveria falhar", failures)

    server.shutdown()
    for failure in failures:
        print(f"::error::{failure}")
    print(f"test-comments-scan: {'FALHOU' if failures else 'ok'} ({len(failures)} falha(s))")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
