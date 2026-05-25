---
title: "LLMs Module"
description: "Unified interface for Groq, OpenAI, LiteLLM (Anthropic, Gemini, Ollama, DeepSeek, Azure, Bedrock, 100+ models), and HuggingFace."
icon: "microchip"
---

`semantica.llms` provides a single consistent API across every major LLM provider. Every provider is a drop-in replacement for the `llm_provider=` parameter in extractors, reasoning engines, and agents.

## Exported Classes

```python
from semantica.llms import Groq, OpenAI, LiteLLM, HuggingFaceLLM
```

| Class | Provider | API Key Required |
| ----- | -------- | ---------------- |
| `Groq` | Groq Cloud | `GROQ_API_KEY` |
| `OpenAI` | OpenAI / any OpenAI-compatible gateway | `OPENAI_API_KEY` |
| `LiteLLM` | 100+ providers via LiteLLM routing | Depends on model |
| `HuggingFaceLLM` | Local HuggingFace Transformers | None (local) |

<Tip>
  **Anthropic, Gemini, Ollama, DeepSeek, Azure, Bedrock, Cohere, and 90+ others** are all available via `LiteLLM` using their model-string prefix. See the [LiteLLM section](#litellm-100-providers) below.
</Tip>

## What You Get

- **Unified `LLMProvider` interface** — swap providers with a one-line change, no application code changes
- **`LiteLLM`** — single class for 100+ providers using model-string routing
- **Local models** — `HuggingFaceLLM` runs fully on-premise, no API key
- **Streaming** — token-by-token output for low-latency UX
- **Custom gateways** — point `OpenAI` at any OpenAI-compatible endpoint via `base_url`

## Providers

<CodeGroup>

```python Groq
from semantica.llms import Groq
import os

llm = Groq(
    model="llama-3.3-70b-versatile",   # default
    api_key=os.getenv("GROQ_API_KEY"),
    max_tokens=64000,
    temperature=0.0,
)
# Best for: high-throughput extraction, fast inference at low cost
```

```python OpenAI
from semantica.llms import OpenAI
import os

llm = OpenAI(
    model="gpt-4o",
    api_key=os.getenv("OPENAI_API_KEY"),
    temperature=0.0,
)
# Best for: general purpose, function calling, JSON mode
```

```python LiteLLM (100+ providers)
from semantica.llms import LiteLLM
import os

# pip install "semantica[llm-litellm]"

# Anthropic Claude
llm = LiteLLM(model="anthropic/claude-opus-4-5",         api_key=os.getenv("ANTHROPIC_API_KEY"))

# Google Gemini
llm = LiteLLM(model="gemini/gemini-1.5-pro",             api_key=os.getenv("GOOGLE_API_KEY"))

# Ollama (local — no API key)
llm = LiteLLM(model="ollama/llama3.2:3b",                api_base="http://localhost:11434")

# DeepSeek
llm = LiteLLM(model="deepseek/deepseek-chat",            api_key=os.getenv("DEEPSEEK_API_KEY"))

# Azure OpenAI
llm = LiteLLM(model="azure/gpt-4o",                      api_key=os.getenv("AZURE_API_KEY"))

# AWS Bedrock
llm = LiteLLM(model="bedrock/anthropic.claude-3-5-sonnet-20241022-v2:0")

# Novita AI
llm = LiteLLM(model="novita/deepseek/deepseek-v3.2",     api_key=os.getenv("NOVITA_API_KEY"))
```

```python HuggingFaceLLM (Local)
from semantica.llms import HuggingFaceLLM

llm = HuggingFaceLLM(
    model="mistralai/Mistral-7B-Instruct-v0.3",
    device="cuda",           # "cpu" | "cuda" | "mps"
    max_new_tokens=512,
    temperature=0.1,
)
# Bring your own model — full local control, no API key
```

</CodeGroup>

## LiteLLM — 100+ Providers

`LiteLLM` is the recommended way to access any provider not directly exported by `semantica.llms`. Use the `provider/model` string format:

```python
from semantica.llms import LiteLLM
import os

# Pattern: LiteLLM(model="<provider>/<model-name>")
providers = {
    "Anthropic":  LiteLLM(model="anthropic/claude-opus-4-5",       api_key=os.getenv("ANTHROPIC_API_KEY")),
    "Gemini":     LiteLLM(model="gemini/gemini-1.5-pro",            api_key=os.getenv("GOOGLE_API_KEY")),
    "Ollama":     LiteLLM(model="ollama/llama3.2:3b",               api_base="http://localhost:11434"),
    "DeepSeek":   LiteLLM(model="deepseek/deepseek-chat",           api_key=os.getenv("DEEPSEEK_API_KEY")),
    "Azure":      LiteLLM(model="azure/gpt-4o",                     api_key=os.getenv("AZURE_API_KEY")),
    "Bedrock":    LiteLLM(model="bedrock/anthropic.claude-3-5-sonnet-20241022-v2:0"),
    "Cohere":     LiteLLM(model="cohere/command-r-plus",            api_key=os.getenv("COHERE_API_KEY")),
    "Novita AI":  LiteLLM(model="novita/deepseek/deepseek-v3.2",    api_key=os.getenv("NOVITA_API_KEY")),
}

# Every LiteLLM instance implements the same .generate() interface
response = providers["Anthropic"].generate("Explain GraphRAG in one paragraph.")
```

<Note>
  The full list of supported LiteLLM model strings is at [docs.litellm.ai/docs/providers](https://docs.litellm.ai/docs/providers). Use the `provider/model` format shown above.
</Note>

## Custom / Enterprise Gateways

Any OpenAI-compatible endpoint — internal routing layers, Qwen proxies, or private LLaMA deployments:

```python
from semantica.llms import OpenAI

llm = OpenAI(
    model="qwen2.5-72b",
    api_key=os.getenv("GATEWAY_API_KEY"),
    base_url="https://my-internal-gateway.company.com/v1",
)
```

<Note>
  `base_url` is validated at construction time. Non-HTTP(S) schemes raise `ValueError` to prevent SSRF attacks (fixed in v0.5.0).
</Note>

## Using in Extractors

All extractors accept any provider as `llm_provider=`:

```python
from semantica.semantic_extract import NERExtractor, RelationExtractor, TripletExtractor

llm = Groq(model="llama-3.3-70b-versatile", api_key=os.getenv("GROQ_API_KEY"))

ner  = NERExtractor(method="llm",      llm_provider=llm, max_retries=3)
rel  = RelationExtractor(method="llm", llm_provider=llm)
trip = TripletExtractor(method="llm",  llm_provider=llm)
```

## Provider Comparison

| Provider | Import | Speed | Cost | Local | Context | Best For |
| -------- | ------ | ----- | ---- | ----- | ------- | -------- |
| Groq | `Groq` | Very fast | Low | No | 128k | High-throughput extraction |
| OpenAI | `OpenAI` | Fast | Medium | No | 128k | General purpose, function calling |
| Anthropic | `LiteLLM(model="anthropic/...")` | Fast | Medium | No | 200k | Complex reasoning, safety |
| Gemini | `LiteLLM(model="gemini/...")` | Fast | Low | No | 1M | Long context, multimodal |
| Ollama | `LiteLLM(model="ollama/...")` | Medium | Free | Yes | Varies | Privacy, air-gapped |
| DeepSeek | `LiteLLM(model="deepseek/...")` | Fast | Very low | No | 64k | Coding, analysis |
| Azure OpenAI | `LiteLLM(model="azure/...")` | Fast | Medium | No | 128k | Enterprise, compliance |
| AWS Bedrock | `LiteLLM(model="bedrock/...")` | Fast | Varies | No | Varies | AWS-native workloads |
| HuggingFace | `HuggingFaceLLM` | Slow | Free | Yes | Varies | Custom models, BYOM |

<Tip>
  For production extraction pipelines, Groq delivers the best throughput-to-cost ratio. For complex multi-hop reasoning, Claude Opus or GPT-4o provide the highest accuracy.
</Tip>

<CardGroup cols={2}>
  <Card title="Semantic Extract" icon="magnifying-glass" href="semantic_extract">
    Use LLMs for NER and relation extraction.
  </Card>
  <Card title="Agno Integration" icon="robot" href="../integrations/agno">
    LLM providers in Agno multi-agent teams.
  </Card>
  <Card title="Reasoning" icon="brain" href="reasoning">
    LLM-backed deductive and abductive reasoning.
  </Card>
  <Card title="Context" icon="diagram-project" href="context">
    GraphRAG uses LLMs for reasoning over knowledge graphs.
  </Card>
</CardGroup>
