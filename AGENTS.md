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

## Reusable Workflows (`.github/workflows/`)
- `reusable-validate.yml` - CI agnóstico (Node/pnpm/npm/yarn/bun, Python/uv/pip, Playwright)
- `reusable-security-scan.yml` - Varredura de segredos (Gitleaks)
- `reusable-docker-build.yml` - Build e push Docker GHCR multi-arch
- `reusable-deploy.yml` - Deploy e sync ArgoCD
- `reusable-release-drafter.yml` - Release notes e rotulagem de PRs
- `reusable-release.yml` - Publicação de tags e releases semânticas
- `reusable-node-ci.yml` - CI para Node/pnpm
- `reusable-commit-lint.yml` - Validação de Conventional Commits
- `reusable-dependabot-auto-merge.yml` - Auto-merge squash para Dependabot
- `reusable-pages.yml` - Deploy padronizado para GitHub Pages
- `reusable-codeql.yml` - SAST CodeQL avançado
- `reusable-stale.yml` - Gestão automática de issues/PRs inativos
- `reusable-pr-labeler.yml` - Triagem automática de PRs por escopo de pastas

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
