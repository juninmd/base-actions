# Contribuindo

Este repo e consumido por 140+ repos via `@main`: **commit quebrado aqui = pipeline
quebrado em todos**. Trate cada PR como uma mudanca em producao.

## Antes do commit

```bash
make lint   # actionlint + lint-actions.py (com shellcheck)
```

Regras que o linter e o CI cobram:

- Shell dentro de `action.yml` nunca interpola `${{ inputs.* }}` no `run:`: passe por `env:`.
- Action de terceiro sempre fixada por SHA de commit, com a versao no comentario
  (`uses: actions/checkout@<sha> # v7`). O Dependabot atualiza SHA e comentario.
- Falha silenciosa e bug: nada de `|| echo` engolindo o exit code de teste ou deploy.
- Reusable workflow nunca pede permissao acima de `contents: read` sem necessidade:
  o teto do caller derruba o run inteiro com `startup_failure`.
- Defaults novos devem preservar o comportamento atual. Comportamento mais estrito entra
  como input opt-in (ex.: `lint-blocking`, `strict-install`, `require-token`).
- YAML em LF, sem BOM.

## Commits e releases

Conventional Commits (`feat:`, `fix:`, `chore:`...): o Release Drafter monta as notas
e escolhe a versao a partir das labels do PR.

Ao publicar um release `vMAJOR.MINOR.PATCH`, o workflow `update-major-tag` move a tag
`vMAJOR`. O primeiro release deve ser `v1.0.0` (ajuste o rascunho antes de publicar).
Consumidores devem migrar de `@main` para `@v1`.
