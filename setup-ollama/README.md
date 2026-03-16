# 🦙 Setup Ollama Action

GitHub Action reutilizável para configurar Ollama em GitHub Actions com suporte a cache de modelos.

## 📋 Features

✅ Instala Ollama automaticamente
✅ Aguarda Ollama ficar pronto com timeout configurável
✅ Faz pull do modelo especificado
✅ Cache de modelos do Ollama para executar mais rápido
✅ Outputs para verificar status

## 🚀 Uso Básico

```yaml
- uses: ./.github/actions/setup-ollama
  with:
    model: gemma3:1b
```

## 📝 Inputs

| Input | Required | Default | Descrição |
|-------|----------|---------|-----------|
| `model` | ✅ Sim | - | Nome do modelo Ollama (ex: `gemma3:1b`, `llama2`) |
| `ollama-host` | ❌ Não | `http://localhost:11434` | URL onde Ollama estará disponível |
| `wait-timeout` | ❌ Não | `120` | Timeout máximo em segundos para Ollama ficar pronto |
| `cache-enabled` | ❌ Não | `true` | Habilitar cache de modelos |

## 📤 Outputs

| Output | Descrição |
|--------|-----------|
| `ollama-ready` | `true` se Ollama estava pronto antes do timeout |
| `model-cached` | `true` se o modelo foi restaurado do cache |

## 🔄 Exemplo Completo

### Com Cache (Recomendado)

```yaml
name: ML Pipeline

on: [push]

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: ./.github/actions/setup-ollama
        id: ollama
        with:
          model: gemma3:1b
          cache-enabled: true
          wait-timeout: 120

      - name: Usar Ollama
        run: |
          curl -s http://localhost:11434/api/tags
          echo "Model was cached: ${{ steps.ollama.outputs.model-cached }}"

      - uses: ./.github/actions/cleanup-ollama
        if: always()
        with:
          cache-enabled: true
          cache-key: ollama-models-gemma3:1b
```

### Em Repositórios Externos

Você pode usar essa action em outros repositórios importando-a do repositório original:

```yaml
- uses: juninmd/quiz-shorts-generator/.github/actions/setup-ollama@master
  with:
    model: llama2
```

Ou se você fizer fork, crie um repositório central de actions:

```yaml
- uses: seu-org/github-actions/.github/actions/setup-ollama@main
  with:
    model: mistral
```

## 🎯 Use Cases

### 1. ML Training Pipeline
```yaml
- uses: ./.github/actions/setup-ollama
  with:
    model: llama2
```

### 2. API Testing
```yaml
- uses: ./.github/actions/setup-ollama
  with:
    model: gemma3:1b
    wait-timeout: 180
```

### 3. Code Generation
```yaml
- uses: ./.github/actions/setup-ollama
  with:
    model: mistral
    cache-enabled: true
```

## ⚙️ Como Usar em Outro Repositório

### Opção 1: Importar da URL do Repositório

```yaml
- uses: juninmd/quiz-shorts-generator/.github/actions/setup-ollama@main
  with:
    model: gemma3:1b
```

### Opção 2: Copiar para seu Repositório

```bash
# Copy the action to your repo
cp -r .github/actions/setup-ollama /seu/repo/.github/actions/

# Use localmente
- uses: ./.github/actions/setup-ollama
  with:
    model: gemma3:1b
```

## 🐛 Troubleshooting

### Ollama não responde após timeout

```yaml
- uses: ./.github/actions/setup-ollama
  with:
    model: gemma3:1b
    wait-timeout: 300  # Aumentar timeout
```

### Cache não funciona

Certifique-se de usar a cleanup action com o cache-key configurado:

```yaml
- uses: ./.github/actions/cleanup-ollama
  if: always()
  with:
    cache-enabled: true
    cache-key: ollama-models-${{ env.MODEL_NAME }}
```

## 📚 Actions Relacionadas

- **setup-ollama**: Instala e inicializa Ollama
- **cleanup-ollama**: Para Ollama e salva cache

## 📄 Licença

MIT

---

💡 **Dica**: Combine com `actions/cache` para cache adicional de dependências do projeto!
