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
      push: ${{ github.event_name != 'pull_request' }}  # PR = build-only
      charts-path: apps/my-app                          # opcional: pin da tag em app-charts
    secrets:
      GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}
      CHARTS_TOKEN: ${{ secrets.CHARTS_TOKEN }}         # opcional
```

Tags publicadas: `latest` (somente na branch default) e o SHA completo do commit.
Cache do buildx e escopado por workflow para os repos nao disputarem a mesma entrada.

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

## 🔐 Permissoes exigidas do repositorio chamador

Um reusable workflow so consegue **reduzir** as permissoes do token do chamador.
Se o seu workflow declara `permissions:` no topo, o job que chama precisa conceder:

| Workflow chamado | Permissoes necessarias no caller |
|---|---|
| `reusable-validate.yml` | `contents: read` |
| `reusable-security-scan.yml` | `contents: read` |
| `reusable-docker-build.yml` | `contents: read`, **`packages: write`** |
| `reusable-deploy.yml` | `contents: read` |

Omitir o bloco `permissions:` no caller tambem funciona (herda o default do repo).
O que **nao** funciona e declarar menos do que o workflow chamado pede — isso vira
`startup_failure` sem log de step. Coberto por `test-restricted-token.yml`.

## ⚠️ Mudancas de comportamento

- `validate-pr`: teste Python vermelho agora **derruba o job** (antes era engolido por
  `2>/dev/null || echo "No tests found"`).
- `reusable-validate.yml`: os inputs `node-version`/`python-version`/`pnpm-version` voltaram
  a ser repassados para a action. Antes eram aceitos e ignorados em silencio.
- `reusable-validate.yml`: o checkout passou a usar `persist-credentials: false` por padrao.
  O `validate-pr` instala as dependencias do PR, e um `postinstall` malicioso leria o header
  de auth do `.git/config` para usar o `GITHUB_TOKEN` do job. **Se o seu repositorio tem
  dependencia `git+https://github.com/...` privada**, o install passa a dar 403 — ligue de
  volta com `persist-credentials: true`.
- `deploy-to-argocd`: um sync com erro agora **derruba o job** (antes so imprimia aviso).
  Use `fail-on-error: 'false'` para voltar ao comportamento antigo.
- `docker-build-push`: a tag `:latest` so e publicada na branch default. Manifesto que
  aponte para `:latest` a partir de build de branch deixa de receber a imagem nova —
  use a tag de SHA.
- `reusable-docker-build.yml`: com `charts-path` preenchido, nao achar nenhum manifesto
  referenciando a imagem agora e **erro** (antes era aviso com job verde).
- `quality-check`: com `run-test: 'true'` e sem script `test` no package.json agora falha,
  em vez de passar verde.
- `quality-check`: o step interno usava `uses: ./setup-node-pnpm`, e caminho relativo em
  composite action resolve contra o workspace do CHAMADOR — a action estava quebrada para
  qualquer consumidor externo. Passou a referenciar `juninmd/base-actions/setup-node-pnpm@main`.
- `setup-ollama`: a verificacao do modelo passou a ser exata. `grep -F` era substring, entao
  pedir `llama3` com `llama3.2:3b` em cache pulava o pull e o job ficava verde com o modelo
  errado.
- `docker-build-push`: as attestations de proveniencia (SLSA) continuam LIGADAS. O input
  `provenance` existe para desligar quando o consumidor nao entende OCI image index.

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

## 🧪 Desenvolvendo neste repo

> ⚠️ `setup-ollama` instala via `curl https://ollama.com/install.sh | sh`, sem checksum —
> ao contrario do actionlint e do gitleaks, que sao pinados e verificados. O instalador do
> Ollama nao publica hash estavel; e risco de cadeia de suprimentos aceito conscientemente.

```bash
actionlint                              # lint dos workflows
python .github/scripts/lint-actions.py  # lint das composite actions
python testdata/assert.py gitleaks      # contrato do ruleset de secrets
```

O workflow `CI` roda os tres — o contrato do gitleaks entra via `workflow_call`, entao
roda em todo PR e nao so quando `gitleaks.toml` e tocado. Mais os smoke tests, que executam
as actions de verdade: um caso que **exige** que um teste vermelho derrube o `validate-pr`,
um que assere `node -v` depois de pedir `node-version: '20'`, e um que chama o proprio
`reusable-validate.yml` para pegar `startup_failure` na hora.

---
Built with ❤️ by [juninmd](https://github.com/juninmd)
