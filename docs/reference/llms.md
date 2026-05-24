---
title: "LLMs Module"
description: "Unified interface for Groq, OpenAI, Anthropic, Gemini, Ollama, DeepSeek, Novita AI, LiteLLM, and HuggingFace — swap providers with a one-line change."
icon: "microchip"
---

`semantica.llms` gives every Semantica module a single, consistent interface to 9+ LLM providers. Every extractor, reasoning engine, and context graph accepts any provider through the same `llm_provider=` parameter — swap Groq for Anthropic, or a cloud API for a local Ollama model, by changing one line.

## What You Get

<CardGroup cols={2}>
  <Card title="9+ Provider Integrations" icon="plug">
    Groq, OpenAI, Anthropic, Gemini, Ollama, DeepSeek, Novita AI, LiteLLM, and HuggingFace — all behind one interface.
  </Card>
  <Card title="Unified LLMProvider Interface" icon="arrows-left-right">
    `complete()`, `chat()`, and `stream()` work identically across all providers — swap with a one-line change.
  </Card>
  <Card title="LiteLLM (100+ Models)" icon="gear">
    One class, every provider — Anthropic, Gemini, Ollama, DeepSeek, Azure, Bedrock, and 90+ more via LiteLLM model strings.
  </Card>
  <Card title="Local Inference" icon="server">
    Ollama and HuggingFace run fully on-premise — no API key, no data leaves your machine, air-gap compatible.
  </Card>
  <Card title="Streaming" icon="bolt">
    Token-by-token output via `stream()` for responsive agent pipelines and live UI updates.
  </Card>
  <Card title="Retry & Error Handling" icon="rotate">
    Configurable `max_retries` with exponential backoff. Typed exceptions: `LLMAuthenticationError`, `LLMRateLimitError`, `LLMContextLengthError`.
  </Card>
</CardGroup>

## Installation

The base install includes Groq and DeepSeek. Other providers require optional extras:

| Provider | Install Command | API Key Required |
| -------- | --------------- | ---------------- |
| Groq | `pip install semantica` | Yes — `GROQ_API_KEY` |
| DeepSeek | `pip install semantica` | Yes — `DEEPSEEK_API_KEY` |
| Novita AI | `pip install semantica` | Yes — `NOVITA_API_KEY` |
| OpenAI | `pip install "semantica[llm-openai]"` | Yes — `OPENAI_API_KEY` |
| Anthropic | `pip install "semantica[llm-anthropic]"` | Yes — `ANTHROPIC_API_KEY` |
| Gemini | `pip install "semantica[llm-gemini]"` | Yes — `GOOGLE_API_KEY` |
| Ollama | `pip install "semantica[llm-ollama]"` | No — local server |
| LiteLLM | `pip install "semantica[llm-litellm]"` | Varies by target |
| HuggingFace | `pip install "semantica[llm-huggingface]"` | No — local weights |
| All providers | `pip install "semantica[all]"` | Varies |

## Quick Start

<Steps>
  <Step title="Pick a provider">
    ```python
    from semantica.llms import Groq
    import os

    llm = Groq(model="llama-3.3-70b-versatile", api_key=os.getenv("GROQ_API_KEY"))
    ```
  </Step>
  <Step title="Pass it to any Semantica module">
    ```python
    from semantica.semantic_extract import NERExtractor

    ner = NERExtractor(method="llm", llm_provider=llm)
    ```
  </Step>
  <Step title="Extract — swap providers by changing only step 1">
    ```python
    entities = ner.extract("Apple Inc. was founded by Steve Jobs in 1976.")
    ```
  </Step>
  <Step title="Use LiteLLM for config-driven provider selection">
    ```python
    from semantica.llms import LiteLLM
    from semantica.core import ConfigManager

    config = ConfigManager("config.yaml")
    # LiteLLM model strings include the provider prefix:
    # "anthropic/claude-opus-4-7", "gemini/gemini-1.5-pro", "ollama/llama3.2"
    llm = LiteLLM(
        model=config.get("llm_provider.model"),
        api_key=config.get("llm_provider.api_key"),
    )
    ```
  </Step>
</Steps>

## Providers

<CodeGroup>

```python Groq
from semantica.llms import Groq
import os

llm = Groq(
    model="llama-3.3-70b-versatile",   # default and recommended
    api_key=os.getenv("GROQ_API_KEY"),
    temperature=0.0,
    max_tokens=64000,
    max_retries=3,
    timeout=60,
)
```

```python OpenAI
from semantica.llms import OpenAI
import os

llm = OpenAI(
    model="gpt-4o",
    api_key=os.getenv("OPENAI_API_KEY"),
    temperature=0.0,
    max_tokens=4096,
    max_retries=3,
    timeout=120,
    organization=None,   # optional org ID
)
```

```python Anthropic (via LiteLLM)
from semantica.llms import LiteLLM
import os

# Anthropic Claude is accessed via LiteLLM using the "anthropic/" prefix
llm = LiteLLM(
    model="anthropic/claude-opus-4-7",
    api_key=os.getenv("ANTHROPIC_API_KEY"),
    max_tokens=8192,
    temperature=0.0,
)
```

```python Gemini (via LiteLLM)
from semantica.llms import LiteLLM
import os

# Google Gemini is accessed via LiteLLM using the "gemini/" prefix
llm = LiteLLM(
    model="gemini/gemini-1.5-pro",
    api_key=os.getenv("GOOGLE_API_KEY"),
    temperature=0.0,
    max_tokens=8192,
)
```

```python Ollama / Local (via LiteLLM)
from semantica.llms import LiteLLM

# Ollama local models via LiteLLM using the "ollama/" prefix
llm = LiteLLM(
    model="ollama/llama3.2",
    base_url="http://localhost:11434",  # default Ollama address
    temperature=0.0,
    timeout=180,   # local models can be slower; increase for large models
)
# No API key — model runs entirely on your machine
```

```python DeepSeek (via Groq or LiteLLM)
from semantica.llms import Groq   # Groq hosts DeepSeek models
import os

llm = Groq(
    model="deepseek-r1-distill-llama-70b",
    api_key=os.getenv("GROQ_API_KEY"),
    temperature=0.0,
    max_tokens=4096,
)

# Or via LiteLLM for the native DeepSeek endpoint:
from semantica.llms import LiteLLM
llm = LiteLLM(
    model="deepseek/deepseek-chat",
    api_key=os.getenv("DEEPSEEK_API_KEY"),
    temperature=0.0,
    max_tokens=4096,
)
```

```python Novita AI (via LiteLLM)
from semantica.llms import LiteLLM
import os

# Novita AI via LiteLLM using the "novita/" prefix
llm = LiteLLM(
    model="novita/deepseek/deepseek-v3",
    api_key=os.getenv("NOVITA_API_KEY"),
    temperature=0.0,
    max_tokens=4096,
)
```

```python LiteLLM (100+ models)
from semantica.llms import LiteLLM
import os

llm = LiteLLM(
    model="gpt-4o",           # any LiteLLM model string
    api_key=os.getenv("OPENAI_API_KEY"),
    temperature=0.0,
    max_tokens=4096,
)
# Supports: OpenAI, Anthropic, Gemini, Cohere, Azure, Bedrock, Together AI, and 90+ more
# Use the LiteLLM model string format: "anthropic/claude-opus-4-7", "bedrock/anthropic.claude-v2"
```

```python HuggingFace (Local)
from semantica.llms import HuggingFaceLLM

llm = HuggingFaceLLM(
    model="mistralai/Mistral-7B-Instruct-v0.3",
    device="cuda",           # "cpu" | "cuda" | "mps" (Apple Silicon)
    max_new_tokens=512,
    temperature=0.1,
    load_in_4bit=True,       # enable 4-bit quantisation to reduce VRAM
)
# No API key — weights downloaded from Hugging Face Hub (or loaded from local path)
```

</CodeGroup>

## Constructor Parameters

### Common Parameters

| Parameter | Type | Default | Description |
| --------- | ---- | ------- | ----------- |
| `model` | `str` | Provider default | Model identifier string |
| `api_key` | `str` | `None` | API key — reads from environment if omitted |
| `temperature` | `float` | `0.0` | Sampling temperature: 0 = deterministic, 1 = creative |
| `max_tokens` | `int` | Provider default | Maximum tokens in the response |
| `max_retries` | `int` | `3` | Number of retry attempts on transient failures |
| `timeout` | `int` | `60` | Request timeout in seconds |
| `base_url` | `str` | Provider default | Override the API endpoint — useful for proxies and gateways |

### Provider-Specific Parameters

| Provider | Parameter | Description |
| -------- | --------- | ----------- |
| `OpenAI` | `organization` | OpenAI organisation ID |
| `OpenAI` | `project` | OpenAI project ID |
| `LiteLLM` | `model` | Full LiteLLM model string, e.g. `"anthropic/claude-opus-4-7"`, `"gemini/gemini-1.5-pro"`, `"ollama/llama3.2"` |
| `LiteLLM` | `base_url` | Override endpoint — use for Ollama (`http://localhost:11434`) or proxies |
| `HuggingFaceLLM` | `device` | Compute device: `"cpu"` / `"cuda"` / `"mps"` |
| `HuggingFaceLLM` | `load_in_4bit` | Enable 4-bit quantisation (requires `bitsandbytes`) |
| `HuggingFaceLLM` | `max_new_tokens` | Maximum new tokens to generate (replaces `max_tokens`) |

## Direct API Usage

Providers can be used directly — not just through Semantica modules:

```python
from semantica.llms import Groq
import os

llm = Groq(model="llama-3.3-70b-versatile", api_key=os.getenv("GROQ_API_KEY"))

# Single completion
response = llm.complete("What is a knowledge graph?")
print(response.text)          # answer string
print(response.input_tokens)  # tokens consumed by the prompt
print(response.output_tokens) # tokens in the response
print(response.model)         # model that served the request

# Multi-turn chat
messages = [
    {"role": "system", "content": "You are a knowledge graph expert."},
    {"role": "user",   "content": "What is the difference between RDF and property graphs?"},
]
response = llm.chat(messages)
print(response.text)

# Streaming — token-by-token output
for token in llm.stream("Explain knowledge graph reasoning in 3 sentences."):
    print(token, end="", flush=True)
```

## LLMResponse Object

All three methods (`complete`, `chat`, `stream`) return a `LLMResponse` dataclass:

<AccordionGroup>
  <Accordion title="LLMResponse schema">

```python
@dataclass
class LLMResponse:
    text:          str    # the generated text
    model:         str    # model identifier that served the request
    input_tokens:  int    # tokens consumed by the prompt
    output_tokens: int    # tokens in the generated response
    total_tokens:  int    # input_tokens + output_tokens
    latency_ms:    float  # wall-clock time for the API call in milliseconds
    finish_reason: str    # "stop" | "length" | "content_filter" | "tool_calls"
```

  </Accordion>
</AccordionGroup>

## Error Handling

<AccordionGroup>
  <Accordion title="Exception hierarchy and when each is raised">

```python
from semantica.llms import Groq
from semantica.utils import SemanticaError
import os

try:
    llm      = Groq(model="llama-3.3-70b-versatile", api_key=os.getenv("GROQ_API_KEY"))
    response = llm.complete("Summarise this document.")
    print(response.text)

except LLMAuthenticationError as e:
    # Invalid or expired API key
    print(f"Authentication failed: {e}")

except LLMRateLimitError as e:
    # Rate limit hit — Semantica retries automatically up to max_retries
    print(f"Rate limited after retries: {e}")

except LLMContextLengthError as e:
    # Prompt exceeds the model's context window
    print(f"Prompt too long ({e.token_count} tokens, limit {e.context_limit}): {e}")

except LLMProviderError as e:
    # General provider-side error (5xx, model unavailable, etc.)
    print(f"Provider error: {e}")

except SemanticaError as e:
    # Catch-all for all Semantica framework errors
    print(f"Framework error: {e}")
```

| Exception | When Raised |
| --------- | ----------- |
| `LLMAuthenticationError` | Invalid or missing API key |
| `LLMRateLimitError` | Rate limit exceeded after all retries |
| `LLMContextLengthError` | Prompt exceeds the model's context window |
| `LLMProviderError` | Provider-side error (5xx, unavailability) |
| `LLMTimeoutError` | Request exceeded the `timeout` parameter |

  </Accordion>
</AccordionGroup>

## Custom and Enterprise Gateways

Any provider that exposes an OpenAI-compatible REST API can be used by passing `base_url`:

```python
from semantica.llms import OpenAI
import os

# Internal LLM routing gateway
llm = OpenAI(
    model="qwen2.5-72b",
    api_key=os.getenv("GATEWAY_API_KEY"),
    base_url="https://llm-gateway.internal.company.com/v1",
)

# Azure OpenAI Service
llm = OpenAI(
    model="gpt-4o",
    api_key=os.getenv("AZURE_OPENAI_API_KEY"),
    base_url="https://my-resource.openai.azure.com/openai/deployments/gpt-4o",
)

# Self-hosted vLLM server
llm = OpenAI(
    model="meta-llama/Llama-3.1-8B-Instruct",
    api_key="not-needed",
    base_url="http://localhost:8000/v1",
)
```

<Note>
  `base_url` is validated at construction time. Non-HTTP(S) schemes raise `ValueError` to prevent SSRF attacks (fixed in v0.5.0).
</Note>

## Using in Semantica Modules

Every module that uses an LLM accepts any provider through `llm_provider=`:

```python
from semantica.llms import Groq, Anthropic
from semantica.semantic_extract import NERExtractor, RelationExtractor, TripletExtractor
from semantica.ontology import LLMOntologyGenerator
from semantica.reasoning import ReasoningEngine
from semantica.context import AgentContext, ContextGraph
from semantica.vector_store import VectorStore
import os

groq_llm   = Groq(model="llama-3.3-70b-versatile", api_key=os.getenv("GROQ_API_KEY"))
claude_llm = Anthropic(model="claude-opus-4-7",     api_key=os.getenv("ANTHROPIC_API_KEY"))

# Extraction — use fast Groq for high-throughput NER
ner  = NERExtractor(method="llm",      llm_provider=groq_llm)
rel  = RelationExtractor(method="llm", llm_provider=groq_llm)
trip = TripletExtractor(method="llm",  llm_provider=groq_llm)

# Complex reasoning — use Claude for accuracy
engine = ReasoningEngine(llm_provider=claude_llm)

# Ontology generation from natural language
gen = LLMOntologyGenerator(llm_provider=claude_llm)
```

## Provider Comparison

| Provider | Speed | Cost | Local | Max Context | Best For |
| -------- | ----- | ---- | ----- | ----------- | -------- |
| **Groq** | ⚡ Very fast | 💲 Low | No | 128k | High-throughput extraction, fast pipelines |
| **OpenAI** | Fast | 💲💲 Medium | No | 128k | General purpose, function calling, JSON mode |
| **Anthropic** | Fast | 💲💲 Medium | No | 200k | Complex reasoning, long documents, safety |
| **Gemini** | Fast | 💲 Low | No | 1M | Very long context, multimodal (text + image) |
| **Ollama** | Medium | Free | ✅ Yes | Varies | Privacy, air-gapped, no API key |
| **DeepSeek** | Fast | 💲 Very low | No | 64k | Coding tasks, structured analysis |
| **Novita AI** | Fast | 💲 Low | No | Varies | DeepSeek and LLaMA models, cost-effective |
| **LiteLLM** | Varies | Varies | Varies | Varies | Multi-provider routing, vendor abstraction |
| **HuggingFace** | Slow | Free | ✅ Yes | Varies | Custom and fine-tuned models, full local control |

## Environment Variables

| Variable | Provider | Notes |
| -------- | -------- | ----- |
| `GROQ_API_KEY` | Groq | Required for Groq cloud |
| `OPENAI_API_KEY` | OpenAI, LiteLLM | Also used for OpenAI-compatible gateways |
| `ANTHROPIC_API_KEY` | Anthropic | Required for Claude |
| `GOOGLE_API_KEY` | Gemini | Required for Gemini |
| `DEEPSEEK_API_KEY` | DeepSeek | Required for DeepSeek cloud |
| `NOVITA_API_KEY` | Novita AI | Required for Novita AI |
| `HUGGINGFACE_HUB_TOKEN` | HuggingFace | Required for gated models (optional for public models) |

## YAML Configuration

```yaml
# config.yaml
llm_provider:
  name: "groq"
  model: "llama-3.3-70b-versatile"
  api_key: "${GROQ_API_KEY}"   # reads from environment
  temperature: 0.0
  max_tokens: 64000
  max_retries: 3
  timeout: 60
```

Load it with `ConfigManager`:

```python
from semantica.core import ConfigManager
from semantica.llms import create_provider

config = ConfigManager("config.yaml")
llm    = create_provider(
    config.get("llm_provider.name"),
    model=config.get("llm_provider.model"),
    api_key=config.get("llm_provider.api_key"),
    temperature=config.get("llm_provider.temperature", default=0.0),
)
```

## Tips and Common Pitfalls

<Warning>
  **Always set `temperature=0.0` for extraction tasks.** NER, relation extraction, and triplet generation need deterministic output — any temperature above 0 introduces randomness that produces inconsistent entity types or hallucinated relationships. Reserve higher temperatures for creative or summarisation tasks.
</Warning>

<Tip>
  **Set `max_retries=3` in production.** Transient rate limits and 5xx errors are normal at scale. All providers retry automatically up to `max_retries` with exponential backoff. Without retries, a single rate-limit hit fails an entire pipeline step that would have succeeded on the second attempt.
</Tip>

<Tip>
  **Use `create_provider()` for config-driven pipelines.** Hard-coding `Groq(...)` in Python means changing the provider requires a code change and redeploy. `create_provider(config.get("llm_provider.name"), ...)` lets you switch from Groq to Anthropic by editing `config.yaml` — no code changes.
</Tip>

<Tip>
  **Use `base_url` for internal gateways and Azure.** Enterprise deployments often route LLM calls through an internal proxy or Azure OpenAI Service. Pass `base_url="https://llm-gateway.internal/v1"` to `OpenAI` — you get the same Semantica integration without changing any module code. Non-HTTP schemes raise `ValueError` (SSRF protection, v0.5.0+).
</Tip>

<Warning>
  **Catch `LLMContextLengthError` explicitly.** If your chunking is misconfigured, a document chunk can exceed the model's context window. Catch `LLMContextLengthError` and log `e.token_count` — it tells you exactly how much to reduce your `chunk_size`. Don't let it surface as a generic failure.
</Warning>

<Tip>
  **Use Ollama or HuggingFace for air-gapped environments.** When data cannot leave the network, Ollama (local inference) or HuggingFace (local weights) are the only viable options. Both support the same `llm_provider=` interface — no other code changes needed.
</Tip>

<CardGroup cols={2}>
  <Card title="Semantic Extract" icon="magnifying-glass" href="semantic_extract">
    NER, relation extraction, and triplet generation with LLMs.
  </Card>
  <Card title="Reasoning" icon="brain" href="reasoning">
    LLM-backed deductive, abductive, and Datalog reasoning.
  </Card>
  <Card title="Ontology" icon="sitemap" href="ontology">
    Generate ontologies from natural language using LLMs.
  </Card>
  <Card title="Context" icon="diagram-project" href="context">
    GraphRAG and decision intelligence powered by LLMs.
  </Card>
</CardGroup>
