# Base Actions 🚀

Central repository for standardizing GitHub Actions workflows across all **juninmd** projects.

## 📋 Features

- **Validate PR**: Tech-agnostic validation (Node/pnpm/npm, Python/uv/pip). Checks for secrets, builds, lints, and tests.
- **Docker Build & Push**: Standardized build with cache and push to GHCR.
- **ArgoCD Deploy**: Automated sync for ArgoCD applications.
- **Commit Lint**: Conventional Commits validation for PRs and pushes.
- **Node CI**: pnpm typecheck, build and lint.
- **Release & Tagging**: Date-based tag generation plus GitHub release notes.
- **Security**: Gitleaks + TruffleHog no historico git e em issues/PRs/comentarios; Trivy, Semgrep e zizmor no filesystem (ver [Camadas de seguranca](#️-camadas-de-seguranca)).
- **Quality Check / Security Scan / Comments Scan / SAST / Setup Node+pnpm / Setup Ollama**: composite actions avulsas (ver [Composite actions avulsas](#-composite-actions-avulsas)).

## 📌 Versionamento

Ao publicar um release `vX.Y.Z`, o workflow `update-major-tag` move a tag `vX`. Prefira
`@v1` a `@main`: um commit quebrado no `main` so chega a voce no proximo release.
Toda action de terceiro usada aqui e fixada por SHA de commit.

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
      node-version: '22'       # Optional
      test-script: 'test'      # script do package.json rodado na etapa de teste (padrao: test)
      lint-blocking: false     # true = falha de lint reprova o gate (padrao: so warning)
      strict-install: false    # true = lockfile desatualizado reprova (padrao: fallback com warning)
      audit: true              # true = executa auditoria de vulnerabilidades (padrao: true)
      audit-level: 'high'      # nivel minimo de severidade (low, moderate, high, critical) (padrao: high)
      audit-blocking: false    # true = vulnerabilidade reprova o gate (padrao: false)
```

Suporta npm, pnpm e yarn (detectado pelo lockfile) e Python (uv/pip). O cache de
dependencias e automatico (npm via `setup-node`, pnpm via store).

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
      BUILD_SECRETS: ${{ format('npmrc=//npm.pkg.github.com/:_authToken={0}', secrets.GITHUB_TOKEN) }}  # opcional
```

Tags publicadas: `latest` (somente na branch default) e o SHA completo do commit.

A composite `docker-build-push` aceita `secrets` (BuildKit, `id=value` por linha) para
tokens de registry no build, ex.: `npmrc=//npm.pkg.github.com/:_authToken=${{ secrets.GITHUB_TOKEN }}`
com `RUN --mount=type=secret,id=npmrc,target=/root/.npmrc` no Dockerfile. Nunca use
`build-args` para token: ele fica no historico da imagem.
O reusable repassa isso via o secret opcional `BUILD_SECRETS` (mesmo formato) e expoe os
inputs `provenance` (default `true`) e `sbom` (default `false`).
Cache do buildx e escopado por workflow + imagem, para duas imagens do mesmo repo nao
disputarem a mesma entrada.

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

Opcoes (todas com default conservador): `require-token: true` reprova quando o secret
nao chega (padrao: pula com warning), `force`/`prune` (padrao `false`) e
`wait-timeout: 300` espera a app ficar Synced e Healthy (padrao `0`: so dispara).

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

### 7. Release Drafter & Autolabeler
Add this to `.github/workflows/release-drafter.yml`:

```yaml
name: Release Drafter
on:
  push:
    branches: [main]
  pull_request_target:
    types: [opened, reopened, synchronize]

jobs:
  draft:
    uses: juninmd/base-actions/.github/workflows/reusable-release-drafter.yml@main
```

### 8. Dependabot Auto-Merge
Add this to `.github/workflows/dependabot-auto-merge.yml`:

```yaml
name: Dependabot Auto-Merge
on:
  pull_request:

jobs:
  auto-merge:
    uses: juninmd/base-actions/.github/workflows/reusable-dependabot-auto-merge.yml@main
```

### 9. GitHub Pages Deploy
Add this to `.github/workflows/pages.yml`:

```yaml
name: Deploy Pages
on:
  push:
    branches: [main]
  workflow_dispatch:

jobs:
  pages:
    uses: juninmd/base-actions/.github/workflows/reusable-pages.yml@main
    with:
      artifact-path: 'dist'
```

### 10. CodeQL SAST Analysis
Add this to `.github/workflows/codeql.yml`:

```yaml
name: CodeQL
on:
  push:
    branches: [main]
  pull_request:
  schedule:
    - cron: '0 3 * * 1'

jobs:
  analyze:
    uses: juninmd/base-actions/.github/workflows/reusable-codeql.yml@main
    with:
      language: 'javascript-typescript'
```

### 11. Stale Issues & PRs
Add this to `.github/workflows/stale.yml`:

```yaml
name: Stale
on:
  schedule:
    - cron: '30 1 * * *'
  workflow_dispatch:

jobs:
  stale:
    uses: juninmd/base-actions/.github/workflows/reusable-stale.yml@main
```

### 12. PR Labeler
Add this to `.github/workflows/labeler.yml`:

```yaml
name: PR Labeler
on:
  pull_request_target:

jobs:
  label:
    uses: juninmd/base-actions/.github/workflows/reusable-pr-labeler.yml@main
```

### 13. Segredos em issues, PRs e comentarios
Segredo colado em comentario nao esta no git: nenhum gate de codigo enxerga. Este workflow
varre cada texto novo na hora (payload do evento, sem API) e o repositorio inteiro no
agendamento, com Gitleaks + TruffleHog. Add this to `.github/workflows/comments-scan.yml`:

```yaml
name: Comments Scan
on:
  issue_comment: { types: [created, edited] }
  issues: { types: [opened, edited] }
  pull_request_review: { types: [submitted, edited] }
  pull_request_review_comment: { types: [created, edited] }
  schedule: [{ cron: '17 4 * * 1' }]
  workflow_dispatch:

permissions:
  contents: read

jobs:
  comments:
    permissions:
      contents: read
      issues: read
      pull-requests: read
    uses: juninmd/base-actions/.github/workflows/reusable-comments-scan.yml@main
```

Achou segredo em comentario: **revogue a credencial e apague o comentario** — editar nao
remove o valor do historico de edicoes do GitHub.
Falso positivo confirmado (ou credencial ja revogada) entra no baseline pelo input
`ignore`, com a chave que o proprio resumo do job mostra na coluna "Ignore"
(ex. `ignore: issue-25:juninmd-hardcoded-password`).

## 🛡️ Camadas de seguranca

| Camada | Onde | Ferramentas | Reprova por padrao? |
|---|---|---|---|
| Segredo no historico git (PR: so o intervalo do PR) | `validate-pr`, `security-scan`, `reusable-security-scan.yml` | **Gitleaks** (formato, ruleset central) + **TruffleHog** (credencial verificada ao vivo) | sim |
| Segredo fora do git | `comments-scan`, `reusable-comments-scan.yml` | Gitleaks + TruffleHog | sim |
| Filesystem atual | `sast`, `reusable-sast.yml` | TruffleHog, **Trivy** (CVE + IaC + segredo), **Semgrep** | sim |
| Workflows do GitHub Actions | `sast` (scanner `zizmor`) | **zizmor** | nao (`fail-zizmor: true` liga) |
| Dependencias | `validate-pr` (`audit`) | npm/pnpm/yarn/bun audit, pip-audit, cargo-audit, govulncheck | nao (`audit-blocking: true` liga) |
| SAST semantico | `reusable-codeql.yml` | CodeQL | conforme o repo |

Gitleaks e TruffleHog rodam **lado a lado** e se complementam: o Gitleaks casa formato
(pega segredo ja revogado e os padroes internos do `gitleaks.toml`), o TruffleHog testa a
credencial na API do provedor e so reprova a que **ainda autentica** — por isso nao sofre
com fixture nem exemplo de documentacao. `trufflehog-verify: false` troca para modo
inventario; `trufflehog: false` desliga.

Os binarios (gitleaks, trufflehog, trivy) sao instalados por `scripts/install-tool.sh`, que
confere o **sha256 fixado no repo** — do tarball baixado e do binario restaurado do cache.
Versao customizada (sem hash fixado) cai no `checksums.txt` do proprio release, com aviso.

## 🧩 Composite actions avulsas

| Action | Para que serve |
|---|---|
| `security-scan` | Gitleaks + TruffleHog (binarios com sha256 fixado e cache) no historico completo ou num intervalo `base..head` |
| `comments-scan` | Gitleaks + TruffleHog em issues, PRs, comentarios, reviews e notas de release |
| `sast` | TruffleHog + Trivy + Semgrep + zizmor no filesystem atual |
| `quality-check` | Lint e testes com pnpm; script ausente e erro de configuracao, nao sucesso |
| `setup-node-pnpm` | Node + pnpm (corepack quando ha `packageManager`) e install com cache |
| `setup-ollama` | Ollama em versao fixa (checksum) + modelo em cache; so Linux |

```yaml
- uses: juninmd/base-actions/security-scan@main
- uses: juninmd/base-actions/setup-ollama@main
  with:
    model: gemma3:1b
```

## 🛠 Desenvolvimento

Requisitos locais: `actionlint`, `shellcheck`, Python 3 com `pyyaml` (`pip install pyyaml`) e,
para o contrato do ruleset, `gitleaks`. Os runtimes das actions (Node, Python, Docker) vem do
runner do GitHub, nao da sua maquina.

`make lint` roda os mesmos gates do CI (actionlint + `lint-actions.py` + shellcheck dos
`scripts/` + zizmor + regressoes; para o zizmor, `pip install zizmor`). Veja
[CONTRIBUTING.md](CONTRIBUTING.md) e [SECURITY.md](SECURITY.md).

## 🔐 Permissoes exigidas do repositorio chamador

Um reusable workflow so consegue **reduzir** as permissoes do token do chamador.
Se o seu workflow declara `permissions:` no topo, o job que chama precisa conceder:

| Workflow chamado | Permissoes necessarias no caller |
|---|---|
| `reusable-validate.yml` | `contents: read` |
| `reusable-security-scan.yml` | `contents: read` |
| `reusable-sast.yml` | `contents: read` |
| `reusable-comments-scan.yml` | `contents: read`, **`issues: read`**, **`pull-requests: read`** |
| `reusable-docker-build.yml` | `contents: read`, **`packages: write`** |
| `reusable-deploy.yml` | `contents: read` |

Omitir o bloco `permissions:` no caller tambem funciona (herda o default do repo).
O que **nao** funciona e declarar menos do que o workflow chamado pede — isso vira
`startup_failure` sem log de step. Coberto por `test-restricted-token.yml`.

## ⚠️ Mudancas de comportamento

- `security-scan` / `validate-pr`: o **TruffleHog** passou a rodar ao lado do Gitleaks.
  Credencial verificada ao vivo no intervalo do PR (ou no historico, no
  `reusable-security-scan`) reprova. Desligue com `trufflehog: 'false'`.
- `security-scan`: intervalo que o git nao resolve (clone raso, force-push) nao passa mais
  verde. Antes o Gitleaks recebia `bad object`, varria **0 commits** e reportava "no leaks
  found"; agora cai na varredura do historico disponivel, com warning.
- `sast`: os achados do scanner `secret` do Trivy passaram a **contar** (eram descartados em
  silencio). Fixture com segredo falso de proposito: `trivy-skip-dirs`, `trivy-skip-files`
  ou `.trivyignore`.
- `sast`: todos os scanners rodam e um unico gate reprova no fim (antes o primeiro com
  achado pulava os seguintes). Semgrep que nao instala **reprova** com `fail-semgrep: true`
  (antes sumia num `::debug::` com job verde).
- `sast`: novo scanner **zizmor** nos workflows, em modo relatorio (`fail-zizmor: 'false'`).
- `reusable-dependabot-auto-merge.yml`: a guarda passou de `github.actor` (forjavel) para o
  autor do PR (`pull_request.user.login`).
- `setup-ollama`: `ollama-host` com espaco ou quebra de linha e rejeitado (o valor vai para
  o `GITHUB_ENV`).
- `validate-pr`: recusa rodar em `pull_request_target` (executaria codigo do PR com o token
  e os secrets do repositorio base). Use `pull_request`.
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
| `juninmd-google-gemini-auth-key` | chave nova do Gemini/AI Studio (`AQ.Ab...`); o padrão só pega `AIza...` |
| `juninmd-openrouter-api-key` | `sk-or-v1-...` |
| `juninmd-groq-api-key` | `gsk_...` |
| `juninmd-xai-api-key` | `xai-...` (xAI/Grok) |
| `juninmd-google-oauth-client-secret` | `GOCSPX-...` |
| `juninmd-authorization-header` | `Bearer …` / `Basic …` hardcoded |

O ruleset padrão do Gitleaks não cobria vários desses formatos. O catálogo
completo — 68 regras custom, regex, origem (tokenix, TruffleHog, Gitleaks) e os
padrões que ficaram de fora por risco de falso positivo — está em
[SECRET-PATTERNS.md](SECRET-PATTERNS.md).

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

> `setup-ollama` baixa a versao fixada do release oficial e confere o tarball contra o
> `sha256sum.txt` publicado (sem `curl | sh`), como actionlint e gitleaks.

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
