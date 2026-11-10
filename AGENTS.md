# AGENTS.md - Base Actions

## Overview
Central repository for standardized GitHub Actions composite actions and reusable workflows across all @juninmd projects.

## Available Actions
- **validate-pr** - Tech-agnostic PR validation (Node/pnpm, Python/uv)
- **docker-build-push** - Docker build with cache + GHCR push
- **deploy-to-argocd** - ArgoCD application sync
- **quality-check** - Code quality checks
- **security-scan** - Gitleaks + TruffleHog no historico git (intervalo do PR ou completo)
- **comments-scan** - Gitleaks + TruffleHog em issues, PRs, comentarios, reviews e releases
- **sast** - TruffleHog + Trivy + Semgrep + zizmor no filesystem atual
- **setup-node-pnpm** - Node.js + pnpm setup
- **setup-ollama** - Ollama setup for CI

## Reusable Workflows (`.github/workflows/`)
- `reusable-validate.yml` - CI agnóstico (Node/pnpm/npm/yarn/bun, Python/uv/pip, Playwright)
- `reusable-security-scan.yml` - Varredura de segredos no historico (Gitleaks + TruffleHog)
- `reusable-comments-scan.yml` - Varredura de segredos em issues/PRs/comentarios (Gitleaks + TruffleHog)
- `reusable-docker-build.yml` - Build e push Docker GHCR multi-arch
- `reusable-deploy.yml` - Deploy e sync ArgoCD
- `reusable-release-drafter.yml` - Release notes e rotulagem de PRs
- `reusable-release.yml` - Publicação de tags e releases semânticas
- `reusable-node-ci.yml` - CI para Node/pnpm
- `reusable-commit-lint.yml` - Validação de Conventional Commits
- `reusable-dependabot-auto-merge.yml` - Auto-merge squash para Dependabot
- `reusable-pages.yml` - Deploy padronizado para GitHub Pages
- `reusable-codeql.yml` - SAST CodeQL avançado
- `reusable-sast.yml` - TruffleHog (segredo verificado ao vivo) + Trivy (CVE/IaC/segredo) + Semgrep + zizmor (workflows); usa `sast/action.yml`
- `reusable-stale.yml` - Gestão automática de issues/PRs inativos
- `reusable-pr-labeler.yml` - Triagem automática de PRs por escopo de pastas

## Structure
```
.github/         # Workflows
validate-pr/     # PR validation action
docker-build-push/   # Docker build action
deploy-to-argocd/    # ArgoCD deploy action
quality-check/   # Quality check action
security-scan/   # Secret scan do historico (Gitleaks + TruffleHog)
comments-scan/   # Secret scan de issues/PRs/comentarios (collect.py + Gitleaks + TruffleHog)
scripts/         # install-tool.sh: instala gitleaks/trufflehog/trivy com sha256 fixado
setup-node-pnpm/ # Node/pnpm setup action
setup-ollama/    # Ollama setup action
sast/            # SAST composite action (TruffleHog + Trivy + Semgrep + zizmor)
```

## Usage
Reference in workflows with `uses: juninmd/base-actions/<action>@main`

## Regras deste repo
- Consumido por 140+ repos via `@main`: commit quebrado aqui = pipeline quebrado em todos.
- Antes de qualquer commit: `make lint` (= `actionlint` + `CI=1 python .github/scripts/lint-actions.py`
  + `shellcheck scripts/*.sh` + `zizmor` + regressao do comments-scan; requer `actionlint`,
  `shellcheck` e `pip install pyyaml zizmor`).
- Testes locais: `python .github/scripts/test-validate-pr-secrets.py`,
  `python .github/scripts/test-comments-scan.py` e
  `python testdata/assert.py gitleaks` (contrato do `gitleaks.toml`).
- Bump de versao de gitleaks/trufflehog/trivy: troque o default em TODAS as actions/reusables
  e adicione o sha256 (tarball e binario, X64 e ARM64) em `scripts/install-tool.sh` — o linter
  bloqueia versao divergente ou sem hash fixado.
- Excecao do zizmor fica no codigo, com o motivo ao lado (`# zizmor: ignore[regra]`); a
  politica de pin (`@main` so para `juninmd/base-actions/*`) fica em `.github/zizmor.yml`.
- Workflow em `pull_request_target`/`issue_comment` nunca faz checkout nem executa conteudo
  do PR/comentario; o texto e dado (arquivo), nunca shell nem expressao `${{ }}`.
- Shell dentro de `action.yml` nunca interpola `${{ inputs.* }}` direto no `run:` —
  passe por `env:` (o linter bloqueia).
- Falha silenciosa é bug: nada de `|| echo "..."` engolindo exit code de teste ou deploy.
- Arquivos YAML são LF puro e sem BOM (`.gitattributes` garante).

## Gates de CI (`.github/workflows/ci.yml`, único gate antes do `main`)
- `lint`: actionlint, `lint-actions.py` (schema, injeção, shellcheck, versoes/hashes dos scanners),
  shellcheck de `scripts/`, zizmor (>= medium), regressão do gate de segredos e do coletor de
  comentarios, bloqueio de `"$PM" test` sem `run` e de `?.` em `node -e`.
- `call-reusable-validate`: chama o próprio reusable (pega `startup_failure`).
- `gitleaks-contract`: `test-gitleaks-config.yml`.
- `smoke-actions`, `smoke-node` (npm/pnpm/yarn), `inputs-honored`, `smoke-gate`, `smoke-lint-blocking`, `smoke-test-script`:
  executam as actions de verdade.
- Workflows `test-*.yml` extras: `test-restricted-token`, `test-security-scan` (gitleaks, trufflehog,
  intervalo invalido), `test-sast`, `test-comments-scan`, `test-validate-pr-branch`.
- Não alterar `action.yml`/workflow sem passar por esses gates: 140+ repos consomem este repo.

## Referencia as actions internas (@main, nunca SHA)

- `uses: juninmd/base-actions/<action>@main` e
  `uses: juninmd/base-actions/.github/workflows/<reusable>.yml@main`.
- Nao fixe `@<sha>` em `juninmd/base-actions`: a atualizacao e centralizada no
  `main` e passa a valer no proximo run.

## Auto-merge de PRs bloqueados por billing

- `.github/workflows/auto-merge-billing-blocked.yml` roda neste repo publico e usa o
  secret `AUTOMERGE_TOKEN` (PAT fine-grained) para mesclar PRs cujos checks nao
  iniciam por `recent account payments have failed` / `spending limit`.
- So mescla autores da allowlist (`AUTOMERGE_AUTHORS`), apenas no branch default,
  e somente quando **toda** falha for de billing.
- Opt-out por PR: label `do-not-merge` (configuravel em `AUTOMERGE_DENY_LABELS`).

### Como reconhecer uma falha de billing (bypass)

Sintoma exato, na anotacao do job:

> The job was not started because recent account payments have failed or your
> spending limit needs to be increased.

Caracteristicas que confirmam que **nao e bug de codigo**:

- o run fica `startup_failure` ou `failure` **sem nenhum job** (`jobs` vazio);
- as vezes ha job, mas o passo nem comeca e a unica anotacao e a de pagamento;
- o mesmo SHA passa em repo publico e falha em repo privado.

Diagnostico rapido:

```bash
gh api "repos/<owner>/<repo>/actions/runs/<run-id>/jobs" \
  --jq '.jobs[].id' | while read -r id; do
    gh api "repos/<owner>/<repo>/check-runs/$id/annotations" --jq '.[].message'
  done
```

Tratamento:

- **Nao** mascare com `continue-on-error`, `|| true` ou remocao de gate: o
  problema e de faturamento, nao do workflow.
- Valide a correcao localmente (install/lint/test/build e `gitleaks detect`) e
  registre no PR que o CI remoto nao iniciou por billing.
- O job `auto-merge-billing-blocked` acima mescla o PR quando o unico bloqueio
  e esse.
- Correcao definitiva e do dono da conta: GitHub > Settings > Billing
  (meio de pagamento e spending limit). Enquanto isso, repos privados seguem
  sem rodar Actions.
