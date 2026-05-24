---
title: "Split Module"
description: "15+ text chunking methods including recursive, semantic, entity-aware, relation-aware, code, and structural splitting."
icon: "scissors"
---

`semantica.split` breaks documents into chunks that preserve semantic context. Chunking quality directly determines downstream accuracy — a poorly chunked document produces bad embeddings, missed entities, and broken relation triplets. Use the right strategy for your content type and pipeline goal.

## Why Chunking Matters

Most LLMs and embedding models have fixed context windows. Documents larger than that window must be split. But naive splitting (every 500 characters, regardless of structure) destroys semantic context:

- An entity mention like "Apple Inc." split across two chunks loses its context in both
- A relation triplet like "Steve Jobs founded Apple" split at "Steve Jobs" leaves a dangling subject
- Embedding a chunk that mixes two unrelated topics produces a centroid vector that matches neither

Semantica's chunking methods are designed to avoid these failure modes.

## Exported Classes

| Class | Role |
| --- | --- |
| `TextSplitter` | Unified entry point — swap `method=` without changing downstream code |
| `Chunk` | `{text, start_char, end_char, token_count, metadata, entities, relationships}` |
| `SemanticChunker` | Embedding-based topic-shift detection — splits only when content actually changes |
| `StructuralChunker` | Heading/section-based splits from a `ParsedDocument` |
| `EntityAwareChunker` | Prevents named entity mentions from being split across chunk boundaries |
| `RelationAwareChunker` | Keeps subject-predicate-object triplets intact within a single chunk |
| `HierarchicalChunker` | Multi-level chunking producing parent/child chunk relationships |

**Available `method=` values for `TextSplitter`:**

| Method | Best for |
| --- | --- |
| `recursive` | General text — splits on paragraphs, sentences, words in order |
| `sentence` | Conversational text, QA |
| `token` | LLM context window enforcement |
| `semantic_transformer` | Long documents with topic shifts |
| `entity_aware` | KG extraction pipelines |
| `code` | Source code files |
| `structural` | PDFs and DOCX with heading hierarchy |

## What You Get

<CardGroup cols={2}>
  <Card title="TextSplitter" icon="scissors">
    Unified interface for 11 chunking strategies — swap methods without changing downstream code.
  </Card>
  <Card title="Semantic Chunking" icon="brain">
    Embedding-based topic shift detection — splits only when the topic actually changes.
  </Card>
  <Card title="Entity-Aware Chunking" icon="user">
    Entity spans never cross chunk boundaries — guaranteed by boundary adjustment.
  </Card>
  <Card title="Relation-Aware Chunking" icon="arrows-left-right">
    Subject–predicate–object triplets kept within a single chunk for KG pipelines.
  </Card>
  <Card title="Code Splitting" icon="code">
    AST-level boundaries (function, class, method) for source code search and analysis.
  </Card>
  <Card title="Chunk Object" icon="box">
    Output dataclass with text, token count, character offsets, entities, and full metadata.
  </Card>
</CardGroup>

## Quick Start

<Steps>
  <Step title="Choose a splitting method">
    ```python
    from semantica.split import TextSplitter

    splitter = TextSplitter(
        method="recursive",   # see Splitting Methods table
        chunk_size=1000,
        chunk_overlap=200,
    )
    ```
  </Step>
  <Step title="Split raw text">
    ```python
    chunks = splitter.split(text)

    for chunk in chunks:
        print(f"Chunk {chunk.metadata['chunk_index']} / {chunk.metadata['total_chunks']}")
        print(f"  Tokens:  {chunk.token_count}")
        print(f"  Preview: {chunk.text[:80]}...")
    ```
  </Step>
  <Step title="Or split a ParsedDocument">
    ```python
    from semantica.parse import DocumentParser

    parser = DocumentParser()
    parsed = parser.parse("annual_report.pdf")

    splitter = TextSplitter(method="structural")
    chunks   = splitter.split_documents([parsed])

    for chunk in chunks:
        print(f"[h{chunk.metadata['heading_level']}] {chunk.metadata['section_title']}")
    ```
  </Step>
  <Step title="Batch-split a list of documents">
    ```python
    all_chunks = splitter.split_documents(parsed_docs)

    from collections import defaultdict
    by_source = defaultdict(list)
    for chunk in all_chunks:
        by_source[chunk.metadata['source_id']].append(chunk)
    ```
  </Step>
</Steps>

## Splitting Methods

| Method | How It Splits | Best For |
| ------ | ------------- | -------- |
| `recursive` | Paragraph → sentence → word (cascading fallback) | General-purpose default |
| `semantic_transformer` | Embeds sentences, splits at cosine similarity drops | RAG — topic coherence matters |
| `entity_aware` | Adjusts boundaries so entity spans are never cut | NER pipelines |
| `relation_aware` | Keeps subject–predicate–object triplets within one chunk | KG construction |
| `sentence` | Language-aware sentence boundary detection (NLTK/spaCy) | Short documents, Q&A |
| `token` | Exact token count via tiktoken; hard cutoff | LLM context window prep |
| `fixed` | Fixed character count with overlap; fastest, no NLP | Simple batch jobs |
| `sliding_window` | Fixed-step window — heavy overlap for dense retrieval | Bi-encoder retrieval (ColBERT, DPR) |
| `markdown` | Splits at Markdown heading levels (configurable) | Documentation, wikis, MDX |
| `structural` | Splits at `ParsedDocument.sections` boundaries | Structured PDFs and DOCX |
| `code` | AST-level splits at function / class / method boundaries | Source code search and analysis |

## Choosing a Strategy

Use this decision tree before picking a method:

- **Source code?** → `code`
- **Markdown or structured doc with headings?** → `markdown` or `structural`
- **Building a KG?** → `relation_aware` (keeps triplets intact), then `entity_aware` for pure NER
- **RAG system where retrieval quality matters most?** → `semantic_transformer`
- **Dense overlap for bi-encoder retrieval (ColBERT, DPR)?** → `sliding_window`
- **Preparing prompts for a fixed-window LLM?** → `token`
- **Fast splitting with no NLP overhead?** → `recursive` or `fixed`

## TextSplitter Constructor

```python
from semantica.split import TextSplitter

splitter = TextSplitter(
    method="semantic_transformer",   # chunking strategy
    chunk_size=1000,                 # target size in tokens
    chunk_overlap=200,               # token overlap between adjacent chunks
    tokenizer="cl100k_base",         # tiktoken encoding (GPT-4 default)
    min_chunk_size=50,               # discard very short trailing chunks
    include_metadata=True,           # attach source_id, page_number, section_title
    language="en",                   # ISO 639-1 — used by sentence boundary detector
)
```

| Parameter | Type | Default | Description |
| --------- | ---- | ------- | ----------- |
| `method` | `str` | `"recursive"` | Chunking strategy — see table above |
| `chunk_size` | `int` | `1000` | Target size in tokens (characters for `fixed`) |
| `chunk_overlap` | `int` | `200` | Token overlap between adjacent chunks |
| `tokenizer` | `str` | `"cl100k_base"` | tiktoken encoding: `"cl100k_base"` (GPT-4), `"p50k_base"` (GPT-3), `"r50k_base"` (Codex) |
| `min_chunk_size` | `int` | `0` | Discard chunks shorter than this many tokens |
| `similarity_threshold` | `float` | `0.7` | Cosine similarity cutoff for `semantic_transformer` |
| `embedder` | `EmbeddingGenerator` | `None` | Custom embedder for `semantic_transformer` |
| `include_metadata` | `bool` | `True` | Attach `source_id`, `page_number`, `section_title` to each chunk |
| `language` | `str` | `"en"` | ISO 639-1 language code for sentence boundary detection |
| `heading_levels` | `list[int]` | `[1, 2, 3]` | Heading levels to split on for `markdown` method |
| `code_units` | `list[str]` | `["function", "class"]` | AST node types to split on for `code` method |

## Splitting Method Details

<Tabs>
  <Tab title="Recursive (default)">
    Tries paragraph breaks first, then sentence boundaries, then word boundaries — falling back only when the chunk exceeds `chunk_size`:

    ```python
    splitter = TextSplitter(method="recursive", chunk_size=1000, chunk_overlap=200)
    chunks   = splitter.split(text)
    ```

    **Key behaviours:**
    - Preserves paragraph and sentence structure wherever possible
    - Falls back gracefully — never produces chunks larger than `chunk_size`
    - Overlap ensures context continuity across chunk boundaries
    - Good starting point when you're unsure which method to use
  </Tab>
  <Tab title="Semantic">
    Embeds each sentence, then splits whenever cosine similarity between consecutive sentences drops below `similarity_threshold`. Each chunk talks about one topic:

    ```python
    from semantica.split import TextSplitter
    from semantica.embeddings import EmbeddingGenerator

    embedder = EmbeddingGenerator(model="sentence-transformers")
    splitter = TextSplitter(
        method="semantic_transformer",
        embedder=embedder,
        similarity_threshold=0.7,   # 0.6 = more splits, 0.8 = fewer splits
        chunk_size=800,
        chunk_overlap=0,            # not needed — chunks are already coherent
    )
    chunks = splitter.split(text)
    ```

    **Key behaviours:**
    - Produces variable-length chunks — some topics are short, others long
    - Requires an embedder — defaults to `sentence-transformers/all-MiniLM-L6-v2` if not set
    - Slower than `recursive` due to embedding computation; cache embeddings for repeated splits
    - Best retrieval quality for semantic search — chunks map to single coherent topics
  </Tab>
  <Tab title="Entity-Aware">
    Runs NER first, then adjusts chunk boundaries so no entity mention is split across two chunks:

    ```python
    from semantica.split import TextSplitter
    from semantica.semantic_extract import NERExtractor
    from semantica.llms import Groq
    import os

    llm      = Groq(model="llama-3.3-70b-versatile", api_key=os.getenv("GROQ_API_KEY"))
    ner      = NERExtractor(method="llm", llm_provider=llm)
    entities = ner.extract(text)

    splitter = TextSplitter(method="entity_aware", chunk_size=512, chunk_overlap=50)
    chunks   = splitter.split(text, entities=entities)

    for chunk in chunks:
        print(f"Chunk {chunk.metadata['chunk_index']}: {len(chunk.entities)} entities")
    ```

    **Key behaviours:**
    - Entity spans in `chunk.entities` are guaranteed to fall entirely within `chunk.text`
    - Chunk sizes vary slightly from `chunk_size` — boundary adjustments are ≤ one sentence
    - Works with all entity types: PERSON, ORGANIZATION, LOCATION, DATE, custom types
  </Tab>
  <Tab title="Relation-Aware">
    Keeps subject–predicate–object triplets within the same chunk — critical for KG pipelines:

    ```python
    from semantica.split import TextSplitter
    from semantica.semantic_extract import RelationExtractor, NERExtractor
    from semantica.llms import Groq
    import os

    llm           = Groq(model="llama-3.3-70b-versatile", api_key=os.getenv("GROQ_API_KEY"))
    ner           = NERExtractor(method="llm", llm_provider=llm)
    rel_extractor = RelationExtractor(method="llm", llm_provider=llm)

    entities      = ner.extract(text)
    relationships = rel_extractor.extract(text, entities=entities)

    splitter = TextSplitter(method="relation_aware", chunk_size=512)
    chunks   = splitter.split(text, relationships=relationships)

    for chunk in chunks:
        print(f"Chunk {chunk.metadata['chunk_index']}: {len(chunk.relationships)} triplets")
        for rel in chunk.relationships:
            print(f"  {rel['subject']} —[{rel['predicate']}]→ {rel['object']}")
    ```

    **Key behaviours:**
    - Relation triplets in `chunk.relationships` are always fully contained within the chunk
    - Implies entity-aware behaviour — both entities in a triplet are kept whole too
    - Best used as the split step in a `Parse → Split → Extract → Build KG` pipeline
  </Tab>
  <Tab title="Code">
    Parses source files with `CodeParser` and splits at AST-level boundaries:

    ```python
    from semantica.parse import CodeParser
    from semantica.split import TextSplitter

    parser = CodeParser(extract_comments=True, extract_dependencies=True)
    parsed = parser.parse("src/pipeline.py")

    splitter = TextSplitter(
        method="code",
        code_units=["function", "class"],   # "function" | "class" | "method" | "block"
        chunk_overlap=0,                     # code units are self-contained
    )
    chunks = splitter.split_documents([parsed])

    for chunk in chunks:
        print(f"{chunk.metadata['unit_type']}: {chunk.metadata['unit_name']}")
        print(f"  Lines {chunk.start_char}–{chunk.end_char}  ({chunk.token_count} tokens)")
    ```

    **Key behaviours:**
    - Requires a `ParsedDocument` from `CodeParser` — use `split_documents([parsed])`
    - `chunk_overlap=0` recommended — functions and classes are logically self-contained
    - If a class is too large, it is split at method boundaries automatically
    - Supported languages: Python, JavaScript, TypeScript, Java, Go, Rust, C, C++, C#, Ruby, PHP, Swift
  </Tab>
  <Tab title="Structural & Markdown">
    ### Structural

    Uses `ParsedDocument.sections` as natural split points — each document section becomes one chunk:

    ```python
    from semantica.parse import DoclingParser
    from semantica.split import TextSplitter

    parser = DoclingParser(extract_tables=True)
    parsed = parser.parse("annual_report.pdf")

    splitter = TextSplitter(method="structural")
    chunks   = splitter.split_documents([parsed])

    for chunk in chunks:
        level = chunk.metadata['heading_level']
        title = chunk.metadata['section_title']
        print(f"{'  ' * (level - 1)}[h{level}] {title}  ({chunk.token_count} tokens)")
    ```

    ### Markdown

    Splits at Markdown heading boundaries, configurable to specific heading levels:

    ```python
    splitter = TextSplitter(
        method="markdown",
        heading_levels=[1, 2],   # split at # and ## only; ### stays inline
        chunk_size=800,
    )
    chunks = splitter.split(markdown_text)
    ```

  </Tab>
</Tabs>

## Chunk Schema

<AccordionGroup>
  <Accordion title="Chunk dataclass">

```python
@dataclass
class Chunk:
    text:          str         # the chunk's text content
    start_char:    int         # character offset of start in source document
    end_char:      int         # character offset of end in source document
    token_count:   int         # number of tokens (via configured tokenizer)
    metadata:      Dict        # see metadata fields below
    entities:      List[Dict]  # entity spans fully contained in this chunk
    relationships: List[Dict]  # relation triplets fully contained in this chunk
```

  </Accordion>
  <Accordion title="Chunk metadata fields">

| Field | Type | When Present | Description |
| ----- | ---- | ------------ | ----------- |
| `source_id` | `str` | Always | ID of the source `ParsedDocument` |
| `chunk_index` | `int` | Always | Zero-based position within the document |
| `total_chunks` | `int` | Always | Total chunks produced for this document |
| `method` | `str` | Always | Splitting method that produced this chunk |
| `section_title` | `str` | `structural`, `markdown` | Heading text of the containing section |
| `heading_level` | `int` | `structural`, `markdown` | Depth: 1 = h1, 2 = h2, … |
| `page_number` | `int` | `structural` (DoclingParser) | Source page number in PDF/DOCX |
| `unit_type` | `str` | `code` | `"function"` / `"class"` / `"method"` |
| `unit_name` | `str` | `code` | Name of the code unit, e.g. `"process_batch"` |
| `language` | `str` | `sentence`, `recursive` | ISO 639-1 code for detected text language |
| `similarity_score` | `float` | `semantic_transformer` | Cosine similarity to the adjacent chunk |

  </Accordion>
</AccordionGroup>

## Tokenizer Options

| Tokenizer | Models |
| --------- | ------ |
| `cl100k_base` | GPT-4, GPT-3.5-turbo, text-embedding-ada-002 |
| `p50k_base` | GPT-3 (`text-davinci-003`), Codex |
| `r50k_base` | GPT-3 (`davinci`) |

## Pipeline Integration

```python
from semantica.pipeline import Pipeline
from semantica.ingest import FileIngestor
from semantica.parse import DocumentParser
from semantica.split import TextSplitter
from semantica.semantic_extract import NERExtractor
from semantica.llms import Groq
import os

llm = Groq(model="llama-3.3-70b-versatile", api_key=os.getenv("GROQ_API_KEY"))

pipeline = Pipeline()
pipeline.add_step("ingest",   FileIngestor())
pipeline.add_step("parse",    DocumentParser())
pipeline.add_step("split",    TextSplitter(method="semantic_transformer", chunk_size=512))
pipeline.add_step("extract",  NERExtractor(method="llm", llm_provider=llm))

result = pipeline.run("data/reports/")
```

## Tips and Common Pitfalls

<Warning>
  **`chunk_overlap` too small.** Without overlap, a fact that spans a chunk boundary is invisible in both chunks. A 10–20% overlap relative to `chunk_size` is a safe minimum — for `chunk_size=1000`, set `chunk_overlap=100` to `200`.
</Warning>

<Warning>
  **Wrong tokenizer.** If you use `cl100k_base` (GPT-4) but send chunks to a model with a different vocabulary, your token counts will be wrong. Match the tokenizer to your target model.
</Warning>

<Tip>
  **Semantic splitting needs enough sentences.** `semantic_transformer` needs several sentences to detect topic shifts. On documents shorter than ~300 words it behaves like `sentence` splitting — use `recursive` instead.
</Tip>

<Tip>
  **Code units too coarse.** `code_units=["class"]` on a large codebase produces chunks too big to embed well. Use `["function", "method"]` for more granular, independently useful units.
</Tip>

<Tip>
  **Set `min_chunk_size` to avoid fragment chunks.** `min_chunk_size=0` (default) can produce many tiny trailing chunks. Set to ~30–50 tokens to discard fragments that carry no retrieval value.
</Tip>

<CardGroup cols={2}>
  <Card title="Parse" icon="file-lines" href="parse">
    Parse documents before chunking — produces sections and metadata.
  </Card>
  <Card title="Embeddings" icon="vector-square" href="embeddings">
    Embed chunks for vector search and semantic chunking.
  </Card>
  <Card title="Semantic Extract" icon="magnifying-glass" href="semantic_extract">
    Extract entities and relations from individual chunks.
  </Card>
  <Card title="Pipeline" icon="gear" href="pipeline">
    Integrate splitting as a named pipeline step.
  </Card>
</CardGroup>
