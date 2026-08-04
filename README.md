# Base Actions 🚀

Central repository for standardizing GitHub Actions workflows across all **juninmd** projects.

## 📋 Features

- **Validate PR**: Tech-agnostic validation (Node/pnpm/npm, Python/uv/pip). Checks for secrets, builds, lints, and tests.
- **Docker Build & Push**: Standardized build with cache and push to GHCR.
- **ArgoCD Deploy**: Automated sync for ArgoCD applications.
- **Commit Lint**: Conventional Commits validation for PRs and pushes.
- **Node CI**: pnpm typecheck, build and lint.
- **Release & Tagging**: Date-based tag generation plus GitHub release notes.

## 🛠 Usage

### 1. PR Validation
Add this to `.github/workflows/validate.yml` in your repository:

```yaml
name: Validate
on: [pull_request]

jobs:
  check:
    uses: juninmd/base-actions/.github/workflows/reusable-validate.yml@main
    with:
      node-version: '22' # Optional
```

### 2. Docker Build & Push
Add this to `.github/workflows/build.yml`:

```yaml
name: Build
on:
  push:
    branches: [main]

jobs:
  docker:
    uses: juninmd/base-actions/.github/workflows/reusable-docker-build.yml@main
    with:
      image-name: ${{ github.repository }}
    secrets:
      GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}
```

### 3. ArgoCD Sync
Add this to `.github/workflows/deploy.yml`:

```yaml
name: Deploy
on:
  workflow_run:
    workflows: ["Build"]
    types: [completed]

jobs:
  sync:
    if: ${{ github.event.workflow_run.conclusion == 'success' }}
    uses: juninmd/base-actions/.github/workflows/reusable-deploy.yml@main
    with:
      app-name: 'my-app'
    secrets:
      ARGOCD_AUTH_TOKEN: ${{ secrets.ARGOCD_AUTH_TOKEN }}
```

### 4. Commit Lint
Add this to `.github/workflows/commit-lint.yml`:

```yaml
name: Commit Lint
on: [pull_request]

jobs:
  lint:
    uses: juninmd/base-actions/.github/workflows/reusable-commit-lint.yml@main
```

### 5. Node CI
Add this to `.github/workflows/ci.yml`:

```yaml
name: CI
on: [push, pull_request]

jobs:
  build:
    uses: juninmd/base-actions/.github/workflows/reusable-node-ci.yml@main
    with:
      node-version: '22' # Optional
```

### 6. Release & Tagging
Add this to `.github/workflows/release.yml`:

```yaml
name: Release
on:
  push:
    branches: [main]

jobs:
  release:
    uses: juninmd/base-actions/.github/workflows/reusable-release.yml@main
    with:
      branch: 'main'
    secrets:
      GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}
```

## 🔐 Ruleset de secrets (`gitleaks.toml`)

`validate-pr` e `security-scan` usam o ruleset central deste repositório, que estende o
padrão do Gitleaks com regras nascidas de vazamentos reais encontrados nos repositórios:

| regra | pega |
|---|---|
| `juninmd-hardcoded-password` | `password: 'algo'` literal em código ou config |
| `juninmd-oracle-connect-string` | `connectString: 'host:porta/SID'` |
| `juninmd-db-uri-credentials` | `mysql://user:senha@host`, `postgres://`, `mongodb://`, `amqp://`… |
| `juninmd-internal-hostname` | host de rede interna (`*.intranet`, `*.corp`, `*.internal`, `*.lan`) |
| `juninmd-aws-rds-endpoint` | endpoint de RDS / Redshift / ElastiCache |
| `juninmd-authorization-header` | `Bearer …` / `Basic …` hardcoded |

O ruleset padrão do Gitleaks não pegava nenhum desses casos.

### Sobrepor num repositório específico

Um `gitleaks.toml` (ou `.gitleaks.toml`) na raiz do repositório tem precedência — a action
detecta e não copia o central. Para aceitar um achado pontual, use `.gitleaksignore` com o
fingerprint, que é o mecanismo nativo do Gitleaks.

### Mexer nas regras

`testdata/` é o contrato: `leaky/` tem uma amostra por regra e **precisa** ser detectado,
`clean/` tem os placeholders que **não** podem acusar. O workflow `test-gitleaks-config.yml`
roda `testdata/assert.py` e falha se qualquer um dos dois lados quebrar. Regra nova só entra
com caso de teste junto.

```bash
python testdata/assert.py gitleaks   # roda igual na máquina
```

---
Built with ❤️ by [juninmd](https://github.com/juninmd)
