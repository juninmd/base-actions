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
