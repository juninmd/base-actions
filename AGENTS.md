# AGENTS.md - Base Actions

## Overview
Central repository for standardized GitHub Actions composite actions and reusable workflows across all @juninmd projects.

## Available Actions
- **validate-pr** - Tech-agnostic PR validation (Node/pnpm, Python/uv)
- **docker-build-push** - Docker build with cache + GHCR push
- **deploy-to-argocd** - ArgoCD application sync
- **quality-check** - Code quality checks
- **security-scan** - Security vulnerability scanning
- **setup-node-pnpm** - Node.js + pnpm setup
- **setup-ollama** - Ollama setup for CI

## Structure
```
.github/         # Workflows
validate-pr/     # PR validation action
docker-build-push/   # Docker build action
deploy-to-argocd/    # ArgoCD deploy action
quality-check/   # Quality check action
security-scan/   # Security scan action
setup-node-pnpm/ # Node/pnpm setup action
setup-ollama/    # Ollama setup action
```

## Usage
Reference in workflows with `uses: juninmd/base-actions/<action>@main`

## Regras deste repo
- Consumido por 140+ repos via `@main`: commit quebrado aqui = pipeline quebrado em todos.
- Antes de qualquer commit: `actionlint` e `python .github/scripts/lint-actions.py`.
- Shell dentro de `action.yml` nunca interpola `${{ inputs.* }}` direto no `run:` —
  passe por `env:` (o linter bloqueia).
- Falha silenciosa é bug: nada de `|| echo "..."` engolindo exit code de teste ou deploy.
- Arquivos YAML são LF puro e sem BOM (`.gitattributes` garante).
