# Catálogo de padrões de secrets

Pesquisa feita em 2026-11-05 para ampliar o ruleset central de `gitleaks.toml`.
O critério foi **cobertura máxima com baixo falso positivo**: prefixos únicos e
formatos documentados entram como regra; padrões genéricos/contextuais só entram
com entropia ou palavra-chave próxima.

## Fontes consultadas

| Fonte | O que fornece | Tamanho | Link |
|---|---|---|---|
| Gitleaks default | ruleset curado, com allowlists e entropia | 222 regras | https://github.com/gitleaks/gitleaks/blob/master/config/gitleaks.toml |
| tokenix | regras de referência do `scan-secrets` | 63 regras | https://github.com/juninmd/tokenix/blob/main/assets/secret-rules/default.toml |
| TruffleHog | detectores por provedor, com regex e verificação | 893 detectores | https://github.com/trufflesecurity/trufflehog/tree/main/pkg/detectors |
| detect-secrets (Yelp) | plugins de detecção | 28 arquivos | https://github.com/Yelp/detect-secrets/tree/master/detect_secrets/plugins |
| secretlint | regras por provedor | 39 regras | https://github.com/secretlint/secretlint/tree/master/packages/%40secretlint |

## Cobertura atual

- `gitleaks.toml` estende o ruleset padrão com `useDefault = true`.
- 43 regras custom: 6 nascidas de vazamentos reais, 5 de Gemini/provedores de IA
  e 32 incorporadas nesta rodada a partir do tokenix/TruffleHog.
- Total efetivo: **222 padrão + 43 custom = 265 regras**.

## Regras custom deste repositório

| regra | pega | fonte |
|---|---|---|
| `juninmd-hardcoded-password` | Senha literal atribuida no codigo (nao vem de variavel de ambiente) | vazamento real |
| `juninmd-oracle-connect-string` | Connect string de Oracle apontando para um host real | vazamento real |
| `juninmd-db-uri-credentials` | URI de conexao com usuario e senha embutidos | vazamento real |
| `juninmd-internal-hostname` | Hostname de rede interna corporativa exposto no codigo | vazamento real |
| `juninmd-aws-rds-endpoint` | Endpoint de banco gerenciado da AWS exposto no codigo | vazamento real |
| `juninmd-authorization-header` | Token Bearer ou Basic escrito direto no codigo | vazamento real |
| `juninmd-google-gemini-auth-key` | Chave de autenticacao do Google Gemini no formato AQ.Ab... | tokenix + GitHub |
| `juninmd-openrouter-api-key` | Chave de API do OpenRouter (sk-or-v1-...) | tokenix + GitHub |
| `juninmd-groq-api-key` | Chave de API da Groq (gsk_...) | tokenix + GitHub |
| `juninmd-xai-api-key` | Chave de API da xAI/Grok (xai-...) | tokenix + GitHub |
| `juninmd-google-oauth-client-secret` | Client secret do Google OAuth (GOCSPX-...) | tokenix + GitHub |
| `juninmd-aws-access-key-id-extra` | AWS access key ID com prefixos que o ruleset padrao nao cobre | tokenix |
| `juninmd-aws-secret-access-key` | AWS secret access key atribuida no codigo | tokenix |
| `juninmd-azure-storage-account-key` | AccountKey de Azure Storage embutida em connection string | tokenix |
| `juninmd-digitalocean-token-v1` | Token v1 da DigitalOcean com prefixo dot_ (nao coberto pelo padrao) | tokenix |
| `juninmd-vault-token` | Token do HashiCorp Vault (service, batch ou recovery) | tokenix |
| `juninmd-stripe-webhook-secret` | Webhook signing secret do Stripe | tokenix |
| `juninmd-paypal-braintree-token` | Access token de producao do PayPal Braintree | tokenix |
| `juninmd-razorpay-key` | Chave de API do Razorpay (live ou test) | TruffleHog |
| `juninmd-paystack-key` | Secret key do Paystack (live ou test) | TruffleHog |
| `juninmd-pagarme-key` | Chave de API live do Pagar.me | TruffleHog |
| `juninmd-discord-bot-token` | Token de bot do Discord | tokenix |
| `juninmd-discord-webhook` | Webhook do Discord com token embutido | tokenix |
| `juninmd-resend-api-key` | Chave de API do Resend | TruffleHog |
| `juninmd-docker-hub-pat` | Personal access token do Docker Hub | tokenix |
| `juninmd-buildkite-token` | Token de agente/API do Buildkite | TruffleHog |
| `juninmd-sonarcloud-token` | Token do SonarCloud no formato sqco_ | TruffleHog |
| `juninmd-newrelic-license-key` | License key do New Relic | tokenix |
| `juninmd-sentry-dsn` | DSN do Sentry com chave publica embutida | tokenix |
| `juninmd-datadog-api-key` | API key do Datadog com prefixo dd... | tokenix |
| `juninmd-supabase-pat` | Personal access token do Supabase | tokenix |
| `juninmd-firebase-cloud-messaging-key` | Chave legada do Firebase Cloud Messaging | tokenix |
| `juninmd-nvidia-nim-api-key` | Chave de API do NVIDIA NIM | TruffleHog |
| `juninmd-langsmith-api-key` | Chave de API do LangSmith | TruffleHog |
| `juninmd-fireworks-api-key` | Chave de API da Fireworks AI | TruffleHog |
| `juninmd-replicate-api-token` | Token de API do Replicate | TruffleHog |
| `juninmd-elevenlabs-api-key` | Chave de API da ElevenLabs | TruffleHog |
| `juninmd-pinecone-api-key` | Chave de API do Pinecone | TruffleHog |
| `juninmd-wandb-api-key` | Chave de API do Weights & Biases | TruffleHog |
| `juninmd-figma-pat` | Personal access token do Figma (figp_ novo e figd_ legado) | TruffleHog |
| `juninmd-tailscale-key` | Chave de autenticacao do Tailscale | TruffleHog |
| `juninmd-infisical-token` | Service token do Infisical | TruffleHog |
| `juninmd-cloudflare-api-token` | API token do Cloudflare no formato cfut_/cfat_ | TruffleHog |

## Padrões pesquisados que ficaram fora

Estes formatos apareceram no TruffleHog/tokenix, mas dependem de contexto
(`deepgram`, `vercel`, `miro`, ...) ou são UUIDs/segredos sem prefixo estável.
Entrar com eles sem verificação aumentaria muito o falso positivo; ficam
documentados para uma próxima rodada com regra composta.

| formato | motivo |
|---|---|
| Deepgram (`deepgram` + 40 chars) | chave sem prefixo; exige contexto e entropia |
| AssemblyAI (`assemblyai` + 32 chars) | chave sem prefixo; exige contexto |
| DeepSeek (`sk-` + 32) | colide com OpenAI/generic-api-key; coberto em parte |
| Vercel (24 alfanuméricos) | valor curto e comum; exige contexto |
| ngrok (27_20 alfanuméricos) | exige a palavra `ngrok` na mesma linha |
| Honeycomb (32 hex ou 22 alfanuméricos) | valor curto/genérico |
| Better Stack (24 alfanuméricos) | valor curto/genérico |
| Miro (27 alfanuméricos) | valor curto/genérico |
| Railway | sem prefixo estável no detector |
| Coda/Snyk/Asana OAuth (UUID) | UUID isolado não é segredo; ruleset padrão já usa contexto |
| `llm-api-key` genérico (`sk-...`) | OpenAI/Anthropic/generic já cobrem; regra ampla demais |
| `basic-auth-url` / `db-connection-uri` | já cobertos por `juninmd-db-uri-credentials` e `juninmd-hardcoded-password` |

## Evidência de teste

O corpus versionado fica em `testdata/leaky/` e `testdata/clean/`. Formatos que
o push protection do GitHub reconhece como chave real são gerados em runtime no
`testdata/assert.py` (`RUNTIME_LEAKS`), dentro de um diretório temporário, para
não bloquear o push de valores inventados.

```bash
python testdata/assert.py gitleaks
# leaky/: 43/43 regras custom dispararam
# clean/: 0 falsos positivos

gitleaks detect --no-git --source . --config gitleaks.toml
# no leaks found
```

Para adicionar uma regra nova: inclua o caso em `testdata/leaky/` ou em
`RUNTIME_LEAKS`, adicione o id em `EXPECTED` e rode o contrato acima.
