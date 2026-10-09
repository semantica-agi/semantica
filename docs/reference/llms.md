---
title: "LLMs Module"
description: "Generative LLM providers plus TypeSafe Jev typed decisions."
icon: "microchip"
---

**`semantica.llms`** provides a consistent generation API across major LLM providers and a separate typed-decision API for TypeSafe Jev:

- Generative providers are drop-in replacements for the `llm_provider=` parameter in extractors, reasoners, and agents
- `LiteLLM` routes to 100+ providers with a single class and model-string prefixes
- `HuggingFaceLLM` runs fully on-premise: no API key, no network calls
- Structured output via `generate_typed()` for schema-validated extraction
- `Jev` and `AsyncJev` return Choice, Noul, or Score decisions without pretending to generate text
- Streaming, tool use, and `generate_batch()` for bulk inference


## Exported Classes

```python
from semantica.llms import (
    AsyncJev,
    Groq,
    HuggingFaceLLM,
    Jev,
    JevDecisionResult,
    LiteLLM,
    OpenAI,
)
```

| Class | Provider | API Key Required |
| :----- | :-------- | :---------------- |
| `Groq` | Groq Cloud | `GROQ_API_KEY` |
| `OpenAI` | OpenAI / any OpenAI-compatible gateway | `OPENAI_API_KEY` |
| `LiteLLM` | 100+ providers via LiteLLM routing | Depends on model |
| `HuggingFaceLLM` | Local HuggingFace Transformers | None (local) |
| `Jev` | TypeSafe System One, synchronous | `TYPESAFE_API_KEY` |
| `AsyncJev` | TypeSafe System One, asynchronous | `TYPESAFE_API_KEY` |

<Tip>
  **Anthropic, Gemini, Ollama, DeepSeek, Azure, Bedrock, Cohere, and 90+ others** are all available via `LiteLLM` using their model-string prefix. See the [LiteLLM section](#litellm-100+-providers) below.
</Tip>

## What You Get

- **Unified `LLMProvider` interface**: swap providers with a one-line change, no application code changes
- **`LiteLLM`**: single class for 100+ providers using model-string routing
- **Local models**: `HuggingFaceLLM` runs fully on-premise, no API key
- **Typed decisions**: `Jev` supports bounded Choice, Noul, and Score decisions with probability metadata
- **Streaming**: token-by-token output for low-latency UX
- **Custom gateways**: point `OpenAI` at any OpenAI-compatible endpoint via `base_url`

## Choosing a Provider

<Tabs>
  <Tab title="Groq: Getting Started">
    Free tier, fastest inference, zero setup friction. Best for development and high-throughput extraction pipelines.

    | | |
    | :-- | :-- |
    | **Speed** | Very fast: 100+ tok/s |
    | **Cost** | Free tier available |
    | **Context** | 128k |
    | **Best for** | Development, high-throughput extraction |

    ```python
    import os
    from semantica.llms import Groq

    llm = Groq(
        model="llama-3.1-8b-instant",
        api_key=os.getenv("GROQ_API_KEY"),
        temperature=0.0,
    )
    ```

    Get your free key at [console.groq.com](https://console.groq.com).
  </Tab>
  <Tab title="OpenAI: Production">
    Highest accuracy, best JSON mode and function calling. Use for production pipelines where extraction quality matters.

    | | |
    | :-- | :-- |
    | **Speed** | Fast |
    | **Cost** | Medium |
    | **Context** | 128k |
    | **Best for** | Production quality, JSON extraction, function calling |

    ```python
    import os
    from semantica.llms import OpenAI

    llm = OpenAI(
        model="gpt-4o",
        api_key=os.getenv("OPENAI_API_KEY"),
        temperature=0.0,
        max_tokens=4096,
    )
    ```
  </Tab>
  <Tab title="Ollama: Local / Air-gapped">
    Fully on-premise: no API key, no data leaves your infrastructure. Required for air-gapped deployments.

    | | |
    | :-- | :-- |
    | **Speed** | Medium (hardware-dependent) |
    | **Cost** | Free (local compute only) |
    | **Context** | Varies by model |
    | **Best for** | Privacy, air-gapped, custom fine-tunes |

    ```bash
    # Install Ollama and pull a model first
    ollama pull llama3.2:3b
    ```

    ```python
    from semantica.llms import LiteLLM

    llm = LiteLLM(
        model="ollama/llama3.2:3b",
        api_base="http://localhost:11434",  # Ollama default port
    )
    ```

    <Note>
      No API key required. Ensure the Ollama server is running (`ollama serve`) before creating the `LiteLLM` instance.
    </Note>
  </Tab>
  <Tab title="Claude: Reasoning">
    Largest context window, best multi-hop reasoning, highest safety bar. Use for complex analysis and long-document extraction.

    | | |
    | :-- | :-- |
    | **Speed** | Fast |
    | **Cost** | Medium |
    | **Context** | 200k |
    | **Best for** | Complex reasoning, long documents, safety-critical outputs |

    ```python
    import os
    from semantica.llms import LiteLLM

    llm = LiteLLM(
        model="anthropic/claude-sonnet-5",
        api_key=os.getenv("ANTHROPIC_API_KEY"),
        temperature=0.0,
    )
    ```
  </Tab>
  <Tab title="DeepSeek: Cost Optimization">
    Lowest cost per token for high-volume workloads. Strong on coding and structured data extraction.

    | | |
    | :-- | :-- |
    | **Speed** | Fast |
    | **Cost** | Very low |
    | **Context** | 64k |
    | **Best for** | High-volume pipelines, coding tasks, budget-sensitive workloads |

    ```python
    import os
    from semantica.llms import LiteLLM

    llm = LiteLLM(
        model="deepseek/deepseek-chat",
        api_key=os.getenv("DEEPSEEK_API_KEY"),
        temperature=0.0,
    )
    ```
  </Tab>
  <Tab title="Jev: Typed Decisions">
    Decision-only inference for bounded routing, classification, binary checks, and scoring. Use a generative provider when you need prose or multi-step reasoning.

    | | |
    | :-- | :-- |
    | **Speed** | Very fast |
    | **Output** | Choice, Noul, or Score |
    | **Interface** | `decide()`; not `generate()` |
    | **Best for** | Confidence-gated application decisions |

    ```python
    from semantica.llms import Jev

    decider = Jev()  # reads TYPESAFE_API_KEY
    result = decider.decide(
        state={"risk_score": 0.62},
        question="How should this case be routed?",
        kind="choice",
        choices=["approve", "escalate"],
    )
    ```
  </Tab>
</Tabs>

## API Key Setup

### Environment Variables (Recommended)

```bash
# Add to your shell profile (.bashrc, .zshrc, etc.)
export GROQ_API_KEY="your_groq_api_key_here"
export OPENAI_API_KEY="your_openai_api_key_here"
export ANTHROPIC_API_KEY="your_anthropic_api_key_here"
export TYPESAFE_API_KEY="your_typesafe_api_key_here"

# Reload your shell
source ~/.bashrc
```

### Configuration File Method

```yaml
# config.yaml
llm_provider:
  name: groq
  model: llama-3.1-8b-instant
  temperature: 0.0
# Set GROQ_API_KEY environment variable and pass to constructor
```

### Programmatic Setup

```python
import os
from semantica.llms import Groq, LiteLLM

# Method 1: Direct API key
llm = Groq(api_key="your-api-key-here", model="llama-3.1-8b-instant")

# Method 2: Environment variable (preferred)
llm = Groq(api_key=os.getenv("GROQ_API_KEY"), model="llama-3.1-8b-instant")

# Method 3: Multiple providers via LiteLLM
providers = {
    "fast": LiteLLM(model="groq/llama-3.1-8b-instant", api_key=os.getenv("GROQ_API_KEY")),
    "smart": LiteLLM(model="anthropic/claude-sonnet-5", api_key=os.getenv("ANTHROPIC_API_KEY"))
}
```

### Security Best Practices

<Warning>
Never commit API keys to version control. Use environment variables or secure secret management.
</Warning>

```python
# ❌ Bad - API key in code
llm = Groq(api_key="gsk_abc123...", model="llama-3.1-8b-instant")

# ✅ Good - Environment variable
llm = Groq(api_key=os.getenv("GROQ_API_KEY"), model="llama-3.1-8b-instant")
```

## TypeSafe Jev

`Jev` and `AsyncJev` wrap the official `typesafe-sdk` System One client. They are decision-only providers: neither class implements `generate()`, `generate_structured()`, or `generate_typed()`, and neither can be passed as the `llm_provider=` argument to a generative extractor or reasoner.

<Warning>
  Jev is experimental and early-access. The `llm-typesafe` extra currently supports the reviewed TypeSafe SDK 0.7 API on Python 3.10 or newer. Semantica's base installation remains compatible with Python 3.9 because the SDK is optional and guarded.
</Warning>

<Warning>
  TypeSafe SDK 0.7 emits full request and response bodies through its `typesafe_sdk` logger at `DEBUG`; authorization headers are redacted, but application `state` is not. Keep that logger at `INFO` or higher when state may be sensitive, even if the root logger uses `DEBUG`.
</Warning>

```python
import logging

logging.getLogger("typesafe_sdk").setLevel(logging.INFO)
```

```bash
pip install "semantica[llm-typesafe]"
```

### Constructors

```python
Jev(
    model="jev-latest",
    api_key=None,
    client=None,
    **client_options,
)

AsyncJev(
    model="jev-latest",
    api_key=None,
    client=None,
    **client_options,
)
```

| Argument | Type | Description |
| :--- | :--- | :--- |
| `model` | `str` | TypeSafe model name or alias. Defaults to `jev-latest`. The result preserves the concrete model returned by the service. |
| `api_key` | `Optional[str]` | API key. When omitted, the SDK reads `TYPESAFE_API_KEY`. |
| `client` | compatible client or `None` | Optional injected `TypeSafeClient`/`AsyncTypeSafeClient`, useful for custom transports and tests. Injected clients remain caller-owned. |
| `**client_options` | `Any` | Passed to the SDK client constructor, including `retry`, `timeout`, `headers`, `transport`, or `base_url`. |

### Methods

| Method | Returns | Description |
| :--- | :--- | :--- |
| `decide(state, question, kind, *, choices=None, criteria=None, **request_options)` | `JevDecisionResult` | Make one Choice, Noul, or Score decision. `AsyncJev.decide()` is awaited. |
| `is_available()` | `bool` | Check locally for an injected client or both the SDK and a configured API key. It does not validate the key or make a network request. |
| `close()` | `None` | Close a synchronous client created by `Jev`; injected clients are not closed. |
| `aclose()` | `None` | Asynchronous equivalent for `AsyncJev`. |

`state` accepts a string, mapping, or list. `question` is the instruction evaluated against that state. Inputs by kind:

- `kind="choice"`: pass `choices` as a sequence of labels or a label-to-description mapping. `criteria=` is accepted as an equivalent explicit name. Do not pass both.
- `kind="noul"`: optionally pass `criteria={"true": ..., "false": ...}`.
- `kind="score"`: pass `criteria` as an ordered sequence of rubric levels, beginning at score zero.

Additional request options are forwarded to `system_one()`, such as per-call `model`, `retry`, `timeout`, `extra_headers`, or `extra_body`.

```python
from semantica.llms import Jev

jev = Jev()  # TYPESAFE_API_KEY
result = jev.decide(
    state={"ticket": "Charged twice; please refund this today."},
    question="Which queue should handle this ticket?",
    kind="choice",
    choices={
        "billing": "Charges, invoices, or refunds",
        "technical": "Product or integration failures",
        "other": None,
    },
)
```

### `JevDecisionResult`

| Field | Type | Description |
| :--- | :--- | :--- |
| `kind` | `Literal["choice", "noul", "score"]` | Primitive used for the decision. |
| `value` | `Union[str, bool, float]` | Selected label, Noul boolean at the 0.5 boundary, or expected score. |
| `probability` | `Optional[float]` | Selected-label probability for Choice, raw probability of yes for Noul, and `None` for Score. |
| `confidence` | `float` | SDK confidence for Choice/Score; `abs(2p - 1)` routing certainty for Noul. |
| `probabilities` | `dict` | Full Choice or Score probability distribution. Empty for Noul. |
| `model` | `str` | Concrete model reported by TypeSafe. |
| `request_id` | `Optional[str]` | Request ID when returned by the API. |
| `usage` | `dict` | Reported input/output token usage. |
| `legend` | `dict[int, Any]` | Score-level rubric; empty for Choice and Noul. |

`result.to_dict()` returns a serializable copy suitable for Semantica decision metadata or `cross_system_context`. It deliberately retains the raw Noul probability separately from the derived confidence.

```python
from semantica.llms import AsyncJev

async with AsyncJev() as jev:
    result = await jev.decide(
        state="The message asks for an immediate duplicate-charge refund.",
        question="Does the message explicitly communicate urgency?",
        kind="noul",
    )
```

## Providers

<CodeGroup>

```python Groq
import os
from semantica.llms import Groq

llm = Groq(
    model="llama-3.3-70b-versatile",   # recommended; implementation default: llama-3.1-8b-instant
    api_key=os.getenv("GROQ_API_KEY"),
    max_tokens=64000,
    temperature=0.0,
)
# **Best for:** high-throughput extraction, fast inference at low cost
```

```python OpenAI
import os
from semantica.llms import OpenAI

llm = OpenAI(
    model="gpt-4o",                     # recommended; implementation default: gpt-3.5-turbo
    api_key=os.getenv("OPENAI_API_KEY"),
    temperature=0.0,
)
# **Best for:** general purpose, function calling, JSON mode
```

```python LiteLLM (100+ providers)
import os
from semantica.llms import LiteLLM

# pip install "semantica[llm-litellm]"

# Anthropic Claude
llm = LiteLLM(model="anthropic/claude-opus-4-7",         api_key=os.getenv("ANTHROPIC_API_KEY"))

# Google Gemini
llm = LiteLLM(model="gemini/gemini-1.5-pro",             api_key=os.getenv("GOOGLE_API_KEY"))

# Ollama (local: no API key)
llm = LiteLLM(model="ollama/llama3.2:3b",                api_base="http://localhost:11434")

# DeepSeek
llm = LiteLLM(model="deepseek/deepseek-chat",            api_key=os.getenv("DEEPSEEK_API_KEY"))

# Azure OpenAI
llm = LiteLLM(model="azure/gpt-4o",                      api_key=os.getenv("AZURE_API_KEY"))

# AWS Bedrock
llm = LiteLLM(model="bedrock/anthropic.claude-sonnet-4-5-20250929-v1:0")

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
# Bring your own model: full local control, no API key
```

```python TypeSafe Jev (Decision-only)
from semantica.llms import Jev

decider = Jev(model="jev-latest")  # reads TYPESAFE_API_KEY
result = decider.decide(
    state={"risk_score": 0.62},
    question="How should this case be routed?",
    kind="choice",
    choices=["approve", "escalate"],
)
# Best for typed, confidence-gated application decisions; no text generation
```

</CodeGroup>

## LiteLLM: 100+ Providers

`LiteLLM` is the recommended way to access any provider not directly exported by `semantica.llms`. Use the `provider/model` string format:

```python
import os
from semantica.llms import LiteLLM

# Pattern: LiteLLM(model="<provider>/<model-name>")
providers = {
    "Anthropic":  LiteLLM(model="anthropic/claude-opus-4-7",       api_key=os.getenv("ANTHROPIC_API_KEY")),
    "Gemini":     LiteLLM(model="gemini/gemini-1.5-pro",            api_key=os.getenv("GOOGLE_API_KEY")),
    "Ollama":     LiteLLM(model="ollama/llama3.2:3b",               api_base="http://localhost:11434"),
    "DeepSeek":   LiteLLM(model="deepseek/deepseek-chat",           api_key=os.getenv("DEEPSEEK_API_KEY")),
    "Azure":      LiteLLM(model="azure/gpt-4o",                     api_key=os.getenv("AZURE_API_KEY")),
    "Bedrock":    LiteLLM(model="bedrock/anthropic.claude-sonnet-4-5-20250929-v1:0"),
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

Any OpenAI-compatible endpoint: internal routing layers, Qwen proxies, or private LLaMA deployments:

```python
import os
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

## Using Generative Providers in Extractors

Extractors accept generative providers as `llm_provider=`. Jev is not accepted here because it returns decisions rather than generated text:

```python
import os
from semantica.semantic_extract import NERExtractor, RelationExtractor, TripletExtractor
from semantica.llms import Groq

llm = Groq(model="llama-3.3-70b-versatile", api_key=os.getenv("GROQ_API_KEY"))

ner  = NERExtractor(method="llm",      llm_provider=llm, max_retries=3)
rel  = RelationExtractor(method="llm", llm_provider=llm)
trip = TripletExtractor(method="llm",  llm_provider=llm)
```

## Provider Comparison

| Provider | Import | Speed | Cost | Local | Context | Best For |
| :-------- | :------ | :----- | :---- | :----- | :------- | :-------- |
| Groq | `Groq` | Very fast | Low | No | 128k | High-throughput extraction |
| OpenAI | `OpenAI` | Fast | Medium | No | 128k | General purpose, function calling |
| Anthropic | `LiteLLM(model="anthropic/...")` | Fast | Medium | No | 200k | Complex reasoning, safety |
| Gemini | `LiteLLM(model="gemini/...")` | Fast | Low | No | 1M | Long context, multimodal |
| Ollama | `LiteLLM(model="ollama/...")` | Medium | Free | Yes | Varies | Privacy, air-gapped |
| DeepSeek | `LiteLLM(model="deepseek/...")` | Fast | Very low | No | 64k | Coding, analysis |
| Azure OpenAI | `LiteLLM(model="azure/...")` | Fast | Medium | No | 128k | Enterprise, compliance |
| AWS Bedrock | `LiteLLM(model="bedrock/...")` | Fast | Varies | No | Varies | AWS-native workloads |
| HuggingFace | `HuggingFaceLLM` | Slow | Free | Yes | Varies | Custom models, BYOM |
| TypeSafe Jev | `Jev` / `AsyncJev` | Very fast | Provider pricing | No | Application state | Typed routing, classification, and scoring |

<Tip>
  For production extraction pipelines, Groq delivers the best throughput-to-cost ratio. For complex multi-hop reasoning, Claude Opus or GPT-4o provide the highest accuracy.
</Tip>

## Defaults and Reproducibility

Documentation examples may showcase stronger models for better developer experience, while implementation defaults prioritize reliability and cost efficiency. Understanding actual defaults helps with reproducible results and consistent benchmarking.

**Verified Implementation Defaults:**

| Provider | Default Model | Notes |
| :---------- | :--------------- | :------- |
| `Groq` | `llama-3.1-8b-instant` | Implementation default; examples use `llama-3.3-70b-versatile` for showcase |
| `OpenAI` | `gpt-3.5-turbo` | Implementation default; examples use `gpt-4o` for showcase |
| `HuggingFaceLLM` | `gpt2` | Lightweight, widely compatible |
| `Jev` / `AsyncJev` | `jev-latest` | Early-access alias; pass a concrete model in production when reproducibility requires it |

These are the models used when you construct a provider without specifying `model=`. Examples throughout this documentation use stronger showcase models. Always pass `model=` explicitly in production for reproducible results.

**Why This Matters:**
- Reproducible extraction results across environments
- Consistent baseline performance for benchmarking
- Predictable costs when scaling production workloads

## Performance and Reliability Tips

### Extraction with Retries

```python
import os
from semantica.semantic_extract import NERExtractor
from semantica.llms import Groq

llm = Groq(model="llama-3.3-70b-versatile", api_key=os.getenv("GROQ_API_KEY"))
ner = NERExtractor(method="llm", llm_provider=llm, max_retries=3)

# Process multiple texts with automatic retries
texts = ["Document 1 text...", "Document 2 text...", "Document 3 text..."]
all_entities = []

for text in texts:
    entities = ner.extract(text)
    all_entities.extend(entities)

# Rate limiting handled automatically by provider
```

### Model Selection by Use Case

| Use Case | Recommended Provider/Model | Reasoning |
| :---------- | :--------------------------- | :----------- |
| **Entity Extraction** | `Groq("llama-3.3-70b-versatile")` | Fast, good accuracy for structured tasks |
| **Relation Extraction** | `OpenAI("gpt-4o")` | Best at complex relationship reasoning |
| **Complex Analysis** | `LiteLLM("anthropic/claude-sonnet-5")` | Highest reasoning capability |
| **High Volume/Cost** | `LiteLLM("deepseek/deepseek-chat")` | Lowest cost per token |

### Error Handling

```python
import os
from semantica.llms import Groq
from semantica.semantic_extract import NERExtractor

llm = Groq(
    model="llama-3.3-70b-versatile",
    api_key=os.getenv("GROQ_API_KEY")
)

# Automatic retries for rate limits and transient errors
extractor = NERExtractor(
    method="llm",
    llm_provider=llm,
    max_retries=3      # Retry failed requests automatically
)
```

- [Semantic Extract](/reference/semantic_extract) — Use LLMs for NER and relation extraction.
- [Agno Integration](../integrations/agno) — LLM providers in Agno multi-agent teams.
- [Reasoning](/reference/reasoning) — LLM-backed deductive and abductive reasoning.
- [Context](/reference/context) — GraphRAG uses LLMs for reasoning over knowledge graphs.
