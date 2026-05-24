---
title: "Normalize Module"
description: "Text cleaning, entity canonicalization, date normalization, number conversion, language detection, and encoding repair — before extraction runs."
icon: "broom"
---

`semantica.normalize` standardizes raw data before extraction and graph construction. All normalizers expose both convenience functions (one-liners) and stateful class instances (full control over configuration and reuse).

## Why Normalize Before Extraction

Unstructured data is inconsistent by nature. Without normalization, the same real-world entity appears as dozens of variants in your graph:

- `"Apple Inc."`, `"Apple Computer Inc."`, `"APPLE INC."`, `"Apple, Inc."` — four nodes, one company
- `"Jan 1st, 2020"`, `"01/01/2020"`, `"2020-01-01"` — three formats, one date
- `"$1.2B"`, `"1,200,000,000"`, `"1.2 billion USD"` — three strings, one number
- `"Hello World"` vs `"Hello World"` — a non-breaking space that breaks string matching

Normalization collapses these variants before any extractor, deduplicator, or graph builder sees the data — producing cleaner entities, fewer false duplicates, and more reliable downstream results.

## Exported Classes

```python
from semantica.normalize import (
    # Text normalization
    TextNormalizer,              # coordinator: strip_html, normalize_unicode, fix_encoding
    UnicodeNormalizer,           # NFC/NFD/NFKC/NFKD normalization
    WhitespaceNormalizer,        # collapse spaces, normalize line endings
    SpecialCharacterProcessor,   # smart quotes, dashes, diacritics
    TextCleaner,                 # general text cleaning utilities
    # Entity normalization
    EntityNormalizer,            # coordinator: normalize_entity(text, entity_type)
    AliasResolver,               # resolve "ML" -> "Machine Learning" via dictionary
    EntityDisambiguator,         # disambiguate("Apple", context=...) with confidence
    NameVariantHandler,          # normalize("Dr. JOHN P. SMITH Jr.") -> "John P. Smith"
    # Date/time normalization
    DateNormalizer,              # normalize_date(str) -> ISO 8601
    TimeZoneNormalizer,          # normalize to UTC or target timezone
    RelativeDateProcessor,       # "3 days ago" -> datetime
    TemporalExpressionParser,    # "Q2 2023" -> {start, end, type}
    # Number normalization
    NumberNormalizer,            # normalize_number("$1.2B") -> 1200000000.0
    UnitConverter,               # convert(100, from_unit="km/h", to_unit="m/s")
    CurrencyNormalizer,          # normalize("$42.50") -> {amount, currency, raw}
    ScientificNotationHandler,   # parse scientific notation strings
    # Data cleaning
    DataCleaner,                 # remove_duplicates, fill_missing
    DataValidator,               # validate(records, schema={"name": str, "age": int})
    DuplicateDetector,           # detect duplicate records by similarity threshold
    MissingValueHandler,         # fill missing values: mean/median/mode/constant
    # Language & encoding
    LanguageDetector,            # detect(text) -> {language, confidence}
    EncodingHandler,             # detect_encoding, to_utf8, remove_bom
    # Convenience functions
    normalize_text,              # normalize_text(text, method="default")
    normalize_entity,            # normalize_entity(name, entity_type="Person")
    normalize_date,              # normalize_date("Jan 1st, 2020")
    normalize_number,            # normalize_number("$1,234.56")
    clean_text,                  # clean_text(text)
    detect_language,             # detect_language(text)
    resolve_aliases,             # resolve_aliases(text, aliases_dict)
)
```

## What You Get

<CardGroup cols={2}>
  <Card title="TextNormalizer" icon="text-size">
    Unicode forms, whitespace collapse, HTML stripping, smart-quote and dash replacement.
  </Card>
  <Card title="EntityNormalizer" icon="building">
    Corporate suffix normalization, honorific removal, alias resolution, and disambiguation.
  </Card>
  <Card title="DateNormalizer" icon="calendar">
    Any date format → ISO 8601; relative dates, timezones, and date ranges.
  </Card>
  <Card title="NumberNormalizer" icon="hashtag">
    Currency, scientific notation, unit abbreviations, and percentages → float.
  </Card>
  <Card title="LanguageDetector" icon="globe">
    50+ languages with confidence scoring and batch detection.
  </Card>
  <Card title="EncodingHandler" icon="code">
    Encoding detection, UTF-8 conversion, BOM removal, and cp1252 repair.
  </Card>
</CardGroup>

<Note>
  **v0.5.0 fix:** Encoding repair now handles cp1252 and latin-1 characters that previously caused crashes on Windows when processing documents with non-ASCII content.
</Note>

## Recommended Processing Order

<Steps>
  <Step title="EncodingHandler — fix encoding first">
    Broken bytes corrupt everything downstream. Always run this before anything else.

    ```python
    from semantica.normalize import EncodingHandler

    handler   = EncodingHandler()
    utf8_text = handler.to_utf8(raw_bytes)
    ```
  </Step>
  <Step title="TextNormalizer — unicode, whitespace, HTML">
    ```python
    from semantica.normalize import TextNormalizer

    normalizer  = TextNormalizer(strip_html=True, normalize_unicode=True)
    clean_text  = normalizer.normalize_text(utf8_text)
    ```
  </Step>
  <Step title="EntityNormalizer — canonicalize entity names">
    ```python
    from semantica.normalize import EntityNormalizer

    normalizer = EntityNormalizer()
    canonical  = normalizer.normalize_entity("Apple Computer Inc.", entity_type="Organization")
    # → "Apple Inc."
    ```
  </Step>
  <Step title="DateNormalizer and NumberNormalizer — parse structured values">
    ```python
    from semantica.normalize import DateNormalizer, NumberNormalizer

    date_norm = DateNormalizer(target_timezone="UTC")
    num_norm  = NumberNormalizer()

    date = date_norm.normalize_date("Jan 1st, 2020")   # → "2020-01-01"
    num  = num_norm.normalize_number("$1.2B")          # → 1200000000.0
    ```
  </Step>
  <Step title="LanguageDetector — detect language on clean text">
    ```python
    from semantica.normalize import LanguageDetector

    detector = LanguageDetector()
    lang     = detector.detect("Bonjour le monde")
    # → {"language": "fr", "confidence": 0.98}
    ```
  </Step>
</Steps>

## Convenience Functions

The fastest path — one import, one call:

```python
from semantica.normalize import (
    normalize_text, normalize_entity, normalize_date,
    normalize_number, clean_data, detect_language, handle_encoding,
)

clean  = normalize_text("  Hello,   World!!  \n\n")         # → "Hello, World!!"
entity = normalize_entity("Apple Computer Inc.", entity_type="Organization")  # → "Apple Inc."
date   = normalize_date("Jan 1st, 2020")                    # → "2020-01-01"
num    = normalize_number("$1.2B")                          # → 1200000000.0
lang   = detect_language("Bonjour le monde")                # → {"language": "fr", "confidence": 0.98}
```

## Normalizers

<Tabs>
  <Tab title="TextNormalizer">
    Cleans raw text at the character and token level:

    ```python
    from semantica.normalize import TextNormalizer

    normalizer = TextNormalizer(
        lowercase=False,
        remove_punctuation=False,
        remove_extra_whitespace=True,
        strip_html=True,
        normalize_unicode=True,
        fix_encoding=True,
        form="NFC",              # "NFC" | "NFD" | "NFKC" | "NFKD"
    )

    normalized = normalizer.normalize_text(raw_text)
    ```

    | Parameter | Type | Default | Description |
    | --------- | ---- | ------- | ----------- |
    | `lowercase` | `bool` | `False` | Convert to lowercase — use for bag-of-words matching, not NER |
    | `remove_punctuation` | `bool` | `False` | Strip all punctuation — use for keyword extraction only |
    | `remove_extra_whitespace` | `bool` | `True` | Collapse tabs, newlines, non-breaking spaces into single spaces |
    | `strip_html` | `bool` | `False` | Remove HTML tags and decode `&amp;`, `&lt;`, etc. |
    | `normalize_unicode` | `bool` | `True` | Apply Unicode normal form |
    | `fix_encoding` | `bool` | `True` | Repair common encoding mojibake (cp1252 / latin-1 → UTF-8) |
    | `form` | `str` | `"NFC"` | Unicode normalization form: `"NFC"` / `"NFD"` / `"NFKC"` / `"NFKD"` |

    **Unicode form guide:**

    | Form | Use When |
    | ---- | -------- |
    | `NFC` | Default — best for storage and display |
    | `NFKC` | Search indexing — normalises ligatures, fullwidth chars, and fractions |
    | `NFD` | Stripping diacritics — split é → e + combining accent, then strip accents |
    | `NFKD` | Same as NFD but also decomposes compatibility characters |

    **Sub-normalizers for fine-grained control:**

    ```python
    from semantica.normalize import UnicodeNormalizer, WhitespaceNormalizer, SpecialCharacterProcessor

    unicode_norm = UnicodeNormalizer(form="NFC")
    text = unicode_norm.normalize("café")

    ws_norm = WhitespaceNormalizer()
    text    = ws_norm.normalize("Hello\t\t World\n\n")  # → "Hello World"

    processor = SpecialCharacterProcessor()
    text      = processor.process("'Hello'")  # '' → '', -- → -
    ```
  </Tab>
  <Tab title="EntityNormalizer">
    Canonicalises entity name variants — corporate suffixes, honorifics, case, and punctuation:

    ```python
    from semantica.normalize import EntityNormalizer

    normalizer = EntityNormalizer()

    # Corporate name normalization
    normalizer.normalize_entity("Apple Computer, Inc.", entity_type="Organization")  # → "Apple Inc."
    normalizer.normalize_entity("APPLE INC.",           entity_type="Organization")  # → "Apple Inc."

    # Person name normalization
    normalizer.normalize_entity("JOBS, STEVE", entity_type="Person")  # → "Steve Jobs"
    ```

    **Key behaviours:**
    - Corporate suffix normalization handles: `Inc`, `Inc.`, `Incorporated`, `Ltd`, `Limited`, `Corp`, `Corporation`, `LLC`, `GmbH`, `PLC`, and 30+ more
    - `entity_type="Person"` activates last-name-first reversal, honorific removal, and suffix stripping

    **Sub-normalizers:**

    ```python
    from semantica.normalize import AliasResolver, EntityDisambiguator, NameVariantHandler

    resolver = AliasResolver(aliases={
        "ML":  "Machine Learning",
        "NLP": "Natural Language Processing",
    })
    resolved = resolver.resolve("ML and NLP are subfields of AI")

    disambiguator = EntityDisambiguator()
    result = disambiguator.disambiguate(
        "Apple",
        context="Steve Jobs founded Apple in Cupertino in 1976",
    )
    # → {"entity": "Apple Inc.", "type": "Organization", "confidence": 0.96}

    handler   = NameVariantHandler()
    canonical = handler.normalize("Dr. JOHN P. SMITH Jr.")  # → "John P. Smith"
    ```
  </Tab>
  <Tab title="DateNormalizer">
    Parses any date format and outputs ISO 8601 strings. Handles relative expressions, timezones, and date ranges:

    ```python
    from semantica.normalize import DateNormalizer

    normalizer = DateNormalizer(
        target_timezone="UTC",
        output_format="%Y-%m-%d",
    )

    dates = [
        "January 1st, 2020",
        "01/01/2020",
        "2020-01-01T00:00:00Z",
        "yesterday",
        "3 weeks ago",
        "Q1 2024",
    ]
    normalized = [normalizer.normalize_date(d) for d in dates]
    ```

    **Sub-normalizers:**

    ```python
    from semantica.normalize import TimeZoneNormalizer, RelativeDateProcessor, TemporalExpressionParser
    from datetime import datetime

    tz_norm = TimeZoneNormalizer(target_tz="UTC")
    utc_dt  = tz_norm.normalize("2024-01-01 09:00", source_tz="America/New_York")
    # → datetime(2024, 1, 1, 14, 0, tzinfo=UTC)

    processor = RelativeDateProcessor(reference_date=datetime(2025, 1, 15))
    result    = processor.process("3 days ago")    # → datetime(2025, 1, 12)
    result    = processor.process("next quarter")  # → {"start": "2025-04-01", "end": "2025-06-30"}

    parser = TemporalExpressionParser()
    result = parser.parse("from January 2020 to March 2021")
    # → {"start": "2020-01-01", "end": "2021-03-31", "type": "range"}

    result = parser.parse("Q2 2023")
    # → {"start": "2023-04-01", "end": "2023-06-30", "type": "quarter"}
    ```
  </Tab>
  <Tab title="NumberNormalizer">
    Converts number strings with units, currencies, and abbreviations to `float`:

    ```python
    from semantica.normalize import NumberNormalizer

    normalizer = NumberNormalizer()

    normalizer.normalize_number("$1,234.56")   # → 1234.56
    normalizer.normalize_number("€42K")         # → 42000.0
    normalizer.normalize_number("$1.2B")        # → 1200000000.0
    normalizer.normalize_number("3.14e-2")      # → 0.0314
    normalizer.normalize_number("42%")          # → 0.42
    normalizer.normalize_number("−7")           # → -7.0  (minus sign, not hyphen)
    ```

    **Unit and currency conversion:**

    ```python
    from semantica.normalize import UnitConverter, CurrencyNormalizer

    converter = UnitConverter()
    result    = converter.convert(100, from_unit="km/h", to_unit="m/s")
    # → 27.78

    categories = converter.list_categories()
    # → ["length", "weight", "volume", "temperature", "speed", "area", "pressure", "energy"]

    currency_norm = CurrencyNormalizer()
    result = currency_norm.normalize("$42.50")
    # → {"amount": 42.50, "currency": "USD", "raw": "$42.50"}
    ```
  </Tab>
  <Tab title="Language & Encoding">
    ### LanguageDetector

    Identify the language of a text string. Used internally by the sentence splitter and chunker:

    ```python
    from semantica.normalize import LanguageDetector

    detector = LanguageDetector()

    lang  = detector.detect("Bonjour le monde")
    # → {"language": "fr", "confidence": 0.98}

    langs = detector.detect_top_n("This might be mixed", n=3)
    # → [{"language": "en", "probability": 0.85}, ...]

    results   = detector.detect_batch(["Hello", "Hola", "Bonjour", "Ciao"])
    supported = detector.list_supported_languages()
    ```

    Supports 50+ languages: `en`, `de`, `fr`, `es`, `it`, `pt`, `nl`, `ru`, `zh`, `ja`, `ko`, `ar`, `hi`, `tr`, `pl`, `sv`, `da`, `no`, `fi`, and more.

    ### EncodingHandler

    Detect and repair character encoding issues:

    ```python
    from semantica.normalize import EncodingHandler

    handler = EncodingHandler()

    encoding  = handler.detect_encoding(raw_bytes)
    # → {"encoding": "windows-1252", "confidence": 0.73}

    utf8_text = handler.to_utf8(raw_bytes)
    clean     = handler.remove_bom(text_with_bom)
    repaired  = handler.repair_encoding(garbled_text, source_encoding="cp1252")
    ```

    **Key behaviours:**
    - Encoding detection uses `chardet` internally — accuracy improves with longer input
    - `to_utf8()` attempts cp1252 repair automatically when it detects mojibake patterns
    - Always run `EncodingHandler` first — broken bytes cause cascading failures in every downstream normalizer
  </Tab>
</Tabs>

## DataCleaner

Cleans structured record sets — useful before loading into a vector store or graph:

```python
from semantica.normalize import DataCleaner, DataValidator

cleaner = DataCleaner()

deduped = cleaner.remove_duplicates(records, similarity_threshold=0.9)

filled = cleaner.fill_missing(
    records,
    strategy="mean",      # "mean" | "median" | "mode" | "remove" | "constant"
    constant_value=None,
)

validator = DataValidator()
result = validator.validate(records, schema={"name": str, "age": int, "active": bool})
print(f"Valid:   {result.valid_count}")
print(f"Invalid: {result.error_count}")
```

## Pipeline Integration

```python
from semantica.pipeline import PipelineBuilder, ExecutionEngine
from semantica.ingest import FileIngestor
from semantica.normalize import TextNormalizer
from semantica.semantic_extract import NERExtractor
from semantica.llms import Groq
import os

llm       = Groq(model="llama-3.3-70b-versatile", api_key=os.getenv("GROQ_API_KEY"))
ingestor  = FileIngestor()
normalizer = TextNormalizer(strip_html=True, normalize_unicode=True)
extractor = NERExtractor(method="llm", llm_provider=llm)

builder = PipelineBuilder()
builder.add_step("ingest",    "file_ingest",    handler=ingestor.ingest)
builder.add_step("normalize", "text_normalize", handler=normalizer.normalize)
builder.add_step("extract",   "ner_extract",    handler=extractor.extract)
builder.connect_steps("ingest",    "normalize")
builder.connect_steps("normalize", "extract")

pipeline = builder.build("normalize_pipeline")
result   = ExecutionEngine().execute_pipeline(pipeline, data="data/documents/")
```

## Tips and Common Pitfalls

<Warning>
  **Run encoding repair before anything else.** A single cp1252 character in a UTF-8 stream silently corrupts the surrounding text. Run `EncodingHandler` or set `fix_encoding=True` on `TextNormalizer` first.
</Warning>

<Warning>
  **Don't lowercase before NER.** `normalize_text(lowercase=True)` before entity extraction destroys capitalization signals that NER relies on. Apply case normalization only after extraction if needed.
</Warning>

<Tip>
  **AliasResolver is order-sensitive.** If you register overlapping aliases (`"ML"` and `"ML model"`), the longer match wins. Sort aliases by length descending for predictable behaviour.
</Tip>

<Warning>
  **DateNormalizer and timezone.** Without `target_timezone`, dates without timezone information are returned as naive datetime strings. In regulated pipelines (HIPAA, SOX), always set `target_timezone="UTC"` for unambiguous timestamps.
</Warning>

<Tip>
  **`DataCleaner.remove_duplicates()` is not the same as `DuplicateDetector`.** `DataCleaner` operates on flat records (dicts/rows) by field-level Jaccard similarity. `DuplicateDetector` in the Deduplication module operates on graph entities with embedding-based matching. Use the latter for entity resolution.
</Tip>

<CardGroup cols={2}>
  <Card title="Parse" icon="file-lines" href="parse">
    Parse documents before normalization.
  </Card>
  <Card title="Split" icon="scissors" href="split">
    Chunk normalized text for embedding.
  </Card>
  <Card title="Deduplication" icon="copy" href="deduplication">
    Resolve duplicate entities after normalization.
  </Card>
  <Card title="Pipeline" icon="gear" href="pipeline">
    Include normalization as a named pipeline step.
  </Card>
</CardGroup>
