#!/usr/bin/env python3
"""Lint das composite actions deste repo.

actionlint cobre .github/workflows, mas ignora os action.yml das composite
actions — que é justamente onde vive quase todo o shell deste repositório.
Este script fecha esse buraco:

  1. schema mínimo (name/description/runs, shell obrigatório em step com run)
  2. injecao de script: ${{ <contexto influenciavel> }} dentro de bloco run:
     (checagem sintatica, best-effort: nao segue proveniencia de env)
  3. shellcheck em cada bloco run: (pulado se o binário não existir)
  4. toda action de terceiro fixada por SHA de commit (tag e mutavel; este repo
     e consumido por 140+ repos, entao uma tag movida vira supply chain)
  5. versao do Gitleaks igual nos tres lugares que a declaram
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import tempfile
import traceback
from pathlib import Path

import yaml

# contextos que um autor de PR/workflow externo consegue influenciar e que,
# interpolados direto no corpo de um `run:`, viram execução de código
UNTRUSTED = re.compile(
    r"(?:"
    r"inputs\.[A-Za-z0-9_-]+"
    r"|github\.event\."
    r"|github\.head_ref"
    r"|github\.ref_name"
    r"|github\.actor"
    r"|github\.triggering_actor"
    r"|steps\.[A-Za-z0-9_-]+\.outputs[.\[]"
    r"|needs\.[A-Za-z0-9_-]+\.outputs[.\[]"
    r"|env\.[A-Z_]*(?:TOKEN|SECRET)"
    r")"
)
INTERPOLATION = re.compile(r"\$\{\{(.+?)\}\}", re.S)
INPUT_REF = re.compile(r"inputs\.([a-zA-Z0-9_-]+)")
SHELLCHECK_IGNORE = "SC2016,SC1091,SC2154,SC2086"
USES = re.compile(r"^\s*(?:-\s+)?uses:\s*(\S+)", re.M)
SHA_PIN = re.compile(r"^[^@\s]+@[0-9a-f]{40}$")

errors: list[str] = []
warnings: list[str] = []


def walk_strings(node):
    """Strings do YAML parseado, menos qualquer `description:`.

    Comentario nao aparece (o YAML ja foi parseado) e description e prosa:
    citar `inputs.foo` num texto nunca deve contar como uso nem como referencia.
    """
    if isinstance(node, str):
        yield node
    elif isinstance(node, list):
        for item in node:
            yield from walk_strings(item)
    elif isinstance(node, dict):
        for key, value in node.items():
            if key == "description":
                continue
            yield from walk_strings(value)


def check_step(path: str, idx: int, step) -> list[str]:
    if not isinstance(step, dict):
        errors.append(f"{path}: step #{idx} não é um mapping YAML")
        return []
    name = step.get("name", f"#{idx}")
    script = step.get("run")
    if script is None:
        return []
    if not isinstance(script, str):
        errors.append(f"{path}: step '{name}' tem `run` que não é string")
        return []
    if not step.get("shell"):
        errors.append(f"{path}: step '{name}' tem `run` sem `shell` (composite exige shell explícito)")
    for hit in INTERPOLATION.finditer(script):
        if UNTRUSTED.search(hit.group(1)):
            errors.append(
                f"{path}: step '{name}' interpola {hit.group(0).strip()} dentro do `run` "
                f"— passe via `env:` para evitar injeção de shell"
            )
    return [script]


def shellcheck(path: str, scripts: list[str]) -> None:
    exe = shutil.which("shellcheck")
    if not exe:
        if os.environ.get("CI"):
            errors.append(f"{path}: shellcheck ausente no CI — a analise de shell nao pode ser pulada")
        else:
            warnings.append(f"{path}: shellcheck ausente — analise de shell pulada (local)")
        return
    for i, script in enumerate(scripts):
        with tempfile.NamedTemporaryFile(
            "w", suffix=".sh", delete=False, encoding="utf-8", newline=chr(10)
        ) as fh:
            # placeholders viram literais para o shellcheck não engasgar com ${{ }}
            body = INTERPOLATION.sub("PLACEHOLDER", script).replace(chr(13), "")
            fh.write("#!/usr/bin/env bash" + chr(10) + body)
            tmp = fh.name
        try:
            out = subprocess.run(
                [exe, "-e", SHELLCHECK_IGNORE, "-S", "warning", "-f", "gcc", tmp],
                capture_output=True, text=True,
            )
            if out.returncode != 0:
                for line in out.stdout.splitlines():
                    # gcc format: <tmpfile>:<line>:<col>: <level>: <msg>
                    parts = line.split(":", 3)
                    if len(parts) == 4 and parts[1].isdigit():
                        errors.append(f"{path} (run #{i}, linha {parts[1]}):{parts[3]}")
                    else:
                        errors.append(f"{path} (run #{i}): {line}")
        finally:
            os.unlink(tmp)


def check_action(path: str) -> None:
    with open(path, encoding="utf-8") as fh:
        raw = fh.read()
    if raw.startswith("\ufeff"):
        errors.append(f"{path}: arquivo começa com BOM UTF-8 (quebra o parser do runner)")
    doc = yaml.safe_load(raw)
    if not isinstance(doc, dict):
        errors.append(f"{path}: raiz do YAML não é um mapping")
        return
    for key in ("name", "description", "runs"):
        if not doc.get(key):
            errors.append(f"{path}: chave obrigatória ausente: `{key}`")
    runs = doc.get("runs")
    if not isinstance(runs, dict) or runs.get("using") != "composite":
        return

    declared_raw = doc.get("inputs") or {}
    declared = set(declared_raw) if isinstance(declared_raw, dict) else set()
    steps = runs.get("steps")
    if not isinstance(steps, list):
        errors.append(f"{path}: `runs.steps` ausente ou não é lista")
        return

    scripts: list[str] = []
    for idx, step in enumerate(steps):
        scripts += check_step(path, idx, step)

    # varre o YAML parseado (não o texto cru): comentários e descrições de input
    # não contam como uso, senão citar `inputs.foo` num comentário vira falso positivo
    used: set[str] = set()
    for text in walk_strings(doc):
        used.update(INPUT_REF.findall(text))
    for unknown in sorted(used - declared):
        errors.append(f"{path}: referencia `inputs.{unknown}` que não está declarado")
    for unused in sorted(declared - used):
        # input mantido so por compatibilidade de callers: declarar e suficiente
        if str(declared_raw[unused].get("description", "")).lower().startswith("deprecated"):
            continue
        warnings.append(f"{path}: input `{unused}` declarado e nunca usado")

    shellcheck(path, scripts)


def check_pins() -> int:
    """Actions de terceiros precisam de SHA; locais e do proprio repo ficam de fora."""
    files = sorted(
        [*Path(".github/workflows").glob("*.yml"), *Path(".").glob("*/action.yml")]
    )
    for path in files:
        raw = path.read_text(encoding="utf-8")
        for ref in USES.findall(raw):
            if ref.startswith("./") or ref.startswith("juninmd/base-actions/"):
                continue
            if ref.startswith("docker://") or not SHA_PIN.match(ref):
                errors.append(f"{path.as_posix()}: `uses: {ref}` nao esta fixado por SHA de commit")
    return len(files)


def check_gitleaks_version() -> None:
    """Mesma versao nos tres lugares; um bump esquecido testa uma versao e roda outra."""
    found: dict[str, str] = {}
    action = yaml.safe_load(Path("security-scan/action.yml").read_text(encoding="utf-8"))
    found["security-scan/action.yml"] = str(action["inputs"]["gitleaks-version"]["default"])
    reusable = yaml.safe_load(
        Path(".github/workflows/reusable-security-scan.yml").read_text(encoding="utf-8")
    )
    wf_call = reusable.get("on", reusable.get(True))["workflow_call"]
    found["reusable-security-scan.yml"] = str(wf_call["inputs"]["gitleaks-version"]["default"])
    match = re.search(
        r"^\s*VERSION=(\S+)", Path(".github/workflows/test-gitleaks-config.yml").read_text(encoding="utf-8"), re.M
    )
    found["test-gitleaks-config.yml"] = match.group(1) if match else "<nao encontrada>"
    if len(set(found.values())) != 1:
        errors.append(f"versao do Gitleaks divergente: {found}")


def main() -> int:
    targets = sorted(
        os.path.join(d, "action.yml").replace(os.sep, "/")
        for d in os.listdir(".")
        if os.path.isfile(os.path.join(d, "action.yml"))
    )
    if not targets:
        print("::error::nenhuma composite action encontrada", file=sys.stderr)
        return 1
    for path in targets:
        try:
            check_action(path)
        except Exception as exc:  # o CI precisa da annotation, não de um traceback
            errors.append(f"{path}: falha ao analisar ({exc.__class__.__name__}: {exc})")
            traceback.print_exc(file=sys.stderr)
    check_pins()
    check_gitleaks_version()
    for w in warnings:
        print(f"::warning::{w}")
    for e in errors:
        print(f"::error::{e}")
    print(f"{chr(10)}{len(targets)} actions verificadas — {len(errors)} erro(s), {len(warnings)} aviso(s)")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
