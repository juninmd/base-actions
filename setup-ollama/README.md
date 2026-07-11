# 🦙 Setup Ollama Action

GitHub Action reutilizável para configurar Ollama em pipelines de CI/CD, com suporte nativo a cache de modelos usando `actions/cache@v4`.

## 📋 Funcionalidades

✅ Instala Ollama automaticamente.
✅ Inicia o serviço em background.
✅ Aguarda ele ficar pronto de forma robusta e inteligente (timeout configurável).
✅ Salva/restaura o modelo usando a engine nativa de cache do GitHub Actions (não é necessário passo de cleanup manual).

## 🚀 Uso Básico (Repositórios Externos)

Use diretamente apontando para esse repositório `juninmd/base-actions`:

```yaml
- uses: juninmd/base-actions/setup-ollama@main
  with:
    model: gemma3:1b
```

## 📝 Inputs

| Input          | Obrigatório | Padrão                   | Descrição                                             |
| -------------- | ----------- | ------------------------ | ----------------------------------------------------- |
| `model`        | ✅ Sim       | -                        | Nome do modelo Ollama (ex: `gemma3:1b`, `llama3.2`)   |
| `ollama-host`  | ❌ Não       | `http://localhost:11434` | Host para subir a API do Ollama                       |
| `wait-timeout` | ❌ Não       | `180`                    | Timeout máximo em segundos para Ollama ficar pronto   |
| `pull-timeout` | ❌ Não       | `15`                     | Timeout máximo em minutos para o download do modelo   |
| `cache-enabled`| ❌ Não       | `true`                   | Habilitar cache do modelo para acelerar rodadas       |

## 📤 Outputs

| Output         | Descrição                                 |
| -------------- | ----------------------------------------- |
| `model-cached` | `true` se o modelo foi recuperado do cache|

## 🔄 Exemplo Completo

```yaml
name: Generate AI Content

on: [push]

jobs:
  run-ai:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      # 1. Setup do Ollama com modelo Gemma 3
      - uses: juninmd/base-actions/setup-ollama@main
        id: ollama
        with:
          model: gemma3:1b
          cache-enabled: true

      # 2. Executar script que consome o localhost:11434
      - name: Rodar Script AI
        run: npm run start
```

## 🧠 Funcionamento do Cache
Esta action utiliza `actions/cache@v4` internamente nas pastas do Ollama (`~/.ollama/models`). 

Como a v4 tem um mecanismo de post-run, **o modelo baixado no pull será salvo no cache automaticamente ao final do job inteiro, sem que um passo de cleanup precise ser disparado**. Na rodada seguinte, ele o injeta antes do host levantar, economizando minutos valiosos na pipeline.