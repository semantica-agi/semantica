---
title: "LLMs Module"
description: "Unified interface for Groq, OpenAI, Anthropic, Gemini, Ollama, DeepSeek, Novita AI, LiteLLM, and HuggingFace."
icon: "microchip"
---

`semantica.llms` provides a single consistent API across 8+ LLM providers. Every provider is a drop-in replacement for the `llm_provider=` parameter in extractors, reasoning engines, and agents.

## What You Get

- **8+ provider integrations** — Groq, OpenAI, Anthropic, Gemini, Ollama, DeepSeek, Novita AI, LiteLLM, HuggingFace
- **Unified `LLMProvider` interface** — swap providers with a one-line change, no application changes needed
- **`ProviderFactory`** — instantiate any provider by name from a config dict
- **Local models** — Ollama and HuggingFace run fully on-premise with no API key
- **Streaming** — token-by-token output for low-latency UX
- **Custom gateways** — point any OpenAI-compatible endpoint via `base_url`

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
# Best for: high-throughput extraction, fast inference
```

```python OpenAI
from semantica.llms import OpenAI
import os

# pip install "semantica[llm-openai]"
llm = OpenAI(
    model="gpt-4o",
    api_key=os.getenv("OPENAI_API_KEY"),
    temperature=0.0,
)
# Best for: general purpose, function calling
```

```python Anthropic
from semantica.llms import Anthropic
import os

# pip install "semantica[llm-anthropic]"
llm = Anthropic(
    model="claude-opus-4-7",
    api_key=os.getenv("ANTHROPIC_API_KEY"),
    max_tokens=8192,
)
# Best for: complex reasoning, long context, safety
```

```python Gemini
from semantica.llms import Gemini
import os

# pip install "semantica[llm-gemini]"
llm = Gemini(
    model="gemini-1.5-pro",
    api_key=os.getenv("GOOGLE_API_KEY"),
)
# Best for: long context (1M tokens), multimodal tasks
```

```python Ollama (Local)
from semantica.llms import Ollama

# pip install "semantica[llm-ollama]"
llm = Ollama(
    model="llama3.2:3b",
    base_url="http://localhost:11434",
)
# Best for: local inference, air-gapped environments
# No API key required
```

```python DeepSeek
from semantica.llms import DeepSeek
import os

llm = DeepSeek(
    model="deepseek-chat",
    api_key=os.getenv("DEEPSEEK_API_KEY"),
)
# Best for: coding tasks and analysis at very low cost
```

```python LiteLLM (100+ models)
from semantica.llms import LiteLLM
import os

# pip install "semantica[llm-litellm]"
llm = LiteLLM(
    model="gpt-4o",       # any LiteLLM-supported model string
    api_key=os.getenv("OPENAI_API_KEY"),
)
# Supports: OpenAI, Anthropic, Gemini, Cohere, Azure, Bedrock, and 90+ more
```

```python HuggingFace (BYOM)
from semantica.llms import HuggingFace

llm = HuggingFace(
    model="mistralai/Mistral-7B-Instruct-v0.3",
    device="cuda",           # "cpu" | "cuda" | "mps"
    max_new_tokens=512,
    temperature=0.1,
)
# Bring your own model — full local control, no API key
```

</CodeGroup>

## Provider Factory

Instantiate any provider by name string — useful when provider is loaded from config:

```python
from semantica.llms import create_provider

llm = create_provider("groq",      model="llama-3.3-70b-versatile")
llm = create_provider("openai",    model="gpt-4o")
llm = create_provider("anthropic", model="claude-opus-4-7")
llm = create_provider("gemini",    model="gemini-1.5-pro")
llm = create_provider("ollama",    model="llama3.2")
llm = create_provider("deepseek",  model="deepseek-chat",   api_key=os.getenv("DEEPSEEK_API_KEY"))
llm = create_provider("novita",    model="deepseek/deepseek-v3.2", api_key=os.getenv("NOVITA_API_KEY"))
llm = create_provider("litellm",   model="gpt-4o")
```

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

| Provider | Speed | Cost | Local | Context | Best For |
| -------- | ----- | ---- | ----- | ------- | -------- |
| Groq | Very fast | Low | No | 128k | High-throughput extraction |
| OpenAI | Fast | Medium | No | 128k | General purpose, function calling |
| Anthropic | Fast | Medium | No | 200k | Complex reasoning, safety |
| Gemini | Fast | Low | No | 1M | Long context, multimodal |
| Ollama | Medium | Free | Yes | Varies | Privacy, no API key |
| DeepSeek | Fast | Very low | No | 64k | Coding, analysis |
| Novita AI | Fast | Low | No | Varies | DeepSeek-based tasks |
| LiteLLM | Varies | Varies | Varies | Varies | Multi-provider routing |
| HuggingFace | Slow | Free | Yes | Varies | Custom models, BYOM |

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
