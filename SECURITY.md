# Politica de seguranca

Este repositorio publica GitHub Actions usadas por 140+ repositorios. Uma falha aqui
afeta todos eles, por isso as vulnerabilidades sao tratadas com prioridade.

## Como reportar

Nao abra issue publica. Use o **Private vulnerability reporting** do GitHub
(aba *Security* > *Report a vulnerability*) ou escreva para o mantenedor
[@juninmd](https://github.com/juninmd).

Inclua a action/workflow afetado, os passos para reproduzir e o impacto esperado
(ex.: execucao de codigo no runner do consumidor, vazamento de token).

## Escopo

- Injecao de script em `action.yml` ou `.github/workflows/*`.
- Download de binarios sem verificacao de integridade.
- Permissoes excessivas do `GITHUB_TOKEN` pedidas por um reusable workflow.
- Segredos expostos em log ou no historico do repositorio.

## Praticas adotadas

- Actions de terceiros fixadas por SHA de commit (validado em CI).
- Binarios baixados (gitleaks, ollama) conferidos contra checksum publicado.
- Inputs passados por `env:`, nunca interpolados no `run:` (validado em CI).
- Varredura de segredos com Gitleaks em todo PR.
