---
title: "Normalize Module"
description: "Text cleaning, entity canonicalization, date normalization, number/unit conversion, language detection, and encoding repair."
icon: "broom"
---

`semantica.normalize` standardizes raw data before extraction and graph construction — fixing encodings, canonicalizing entity names, normalizing dates, and detecting languages. All normalizers expose both convenience functions and stateful class instances.

## What You Get

- **`TextNormalizer`** — Unicode, whitespace, HTML stripping, smart-quote/dash replacement
- **`EntityNormalizer`** — alias resolution, disambiguation, name variant handling
- **`DateNormalizer`** — ISO 8601 output, timezone conversion, relative date parsing
- **`NumberNormalizer`** — currency, unit conversion, scientific notation, percentages
- **`DataCleaner`** — duplicate detection, schema validation, missing value handling
- **`LanguageDetector`** — 50+ language detection with confidence scoring
- **`EncodingHandler`** — UTF-8 conversion, BOM removal, encoding detection

<Note>
  **v0.5.0 fix:** Encoding repair now handles cp1252/latin-1 characters that previously caused crashes on Windows when processing documents with non-ASCII content.
</Note>

## Convenience Functions

The fastest path — dispatch via function with a `method` parameter:

```python
from semantica.normalize import (
    normalize_text, normalize_entity, normalize_date,
    normalize_number, clean_data, detect_language, handle_encoding
)

clean  = normalize_text("  Hello,   World!!  \n\n")
# → "Hello, World!!"

entity = normalize_entity("Apple Computer Inc.", entity_type="Organization")
# → "Apple Inc."

date   = normalize_date("Jan 1st, 2020")
# → "2020-01-01"

num    = normalize_number("$1,234.56")
# → 1234.56

lang   = detect_language("Bonjour le monde")
# → {"language": "fr", "confidence": 0.98}
```

## TextNormalizer

```python
from semantica.normalize import TextNormalizer

normalizer = TextNormalizer()

normalized = normalizer.normalize_text(
    raw_text,
    lowercase=False,
    remove_punctuation=False,
    remove_extra_whitespace=True,
    strip_html=True,             # remove HTML tags
    normalize_unicode=True,      # NFC normalization
)
```

Sub-normalizers for fine-grained control:

```python
from semantica.normalize import UnicodeNormalizer, WhitespaceNormalizer, SpecialCharacterProcessor

# Unicode normalization forms: NFC | NFD | NFKC | NFKD
unicode_norm = UnicodeNormalizer(form="NFC")
text = unicode_norm.normalize("café")

# Collapse tabs, line breaks, and extra spaces
ws_norm = WhitespaceNormalizer()
text = ws_norm.normalize("Hello   World\t\n")  # → "Hello World"

# Replace smart quotes, em-dashes, and ellipsis characters
processor = SpecialCharacterProcessor()
text = processor.process("‘Hello’")  # '' → ''
```

## EntityNormalizer

Canonicalize entity names — handles corporate suffixes, punctuation, case, and honorifics:

```python
from semantica.normalize import EntityNormalizer

normalizer = EntityNormalizer()

# Company name normalization
companies = ["Apple Computer, Inc.", "Apple Inc", "APPLE INC."]
normalized = [normalizer.normalize_entity(c) for c in companies]
# All → "Apple Inc."

# Person name normalization
name = normalizer.normalize_entity("JOBS, STEVE", entity_type="Person")
# → "Steve Jobs"
```

Sub-normalizers for entity-specific use cases:

```python
from semantica.normalize import AliasResolver, EntityDisambiguator, NameVariantHandler

# Dictionary-based alias expansion
resolver = AliasResolver(aliases={
    "ML": "Machine Learning",
    "AI": "Artificial Intelligence",
    "DL": "Deep Learning",
})
resolved = resolver.resolve("ML and DL are subsets of AI")
# → "Machine Learning and Deep Learning are subsets of Artificial Intelligence"

# Context-aware disambiguation
disambiguator = EntityDisambiguator()
result = disambiguator.disambiguate(
    "Apple", context="Steve Jobs founded Apple in Cupertino"
)
# → {"entity": "Apple Inc.", "type": "Organization", "confidence": 0.96}

# Honorifics, titles, and cultural name variants
handler = NameVariantHandler()
canonical = handler.normalize("Dr. JOHN P. SMITH Jr.")
# → "John P. Smith"
```

## DateNormalizer

Parse and normalize dates from any format to ISO 8601:

```python
from semantica.normalize import DateNormalizer

normalizer = DateNormalizer()

dates = [
    "January 1st, 2020",
    "01/01/2020",
    "2020-01-01T00:00:00Z",
    "yesterday",
    "3 weeks ago",
]
normalized = [normalizer.normalize_date(d) for d in dates]
# All → ISO 8601 strings

# With automatic UTC conversion
normalizer_utc = DateNormalizer(target_timezone="UTC")
utc_date = normalizer_utc.normalize_date("2024-01-01 09:00 EST")
```

Sub-normalizers for advanced date handling:

```python
from semantica.normalize import (
    TimeZoneNormalizer, RelativeDateProcessor, TemporalExpressionParser
)

# Timezone conversion
tz_norm = TimeZoneNormalizer(target_tz="UTC")
utc_dt = tz_norm.normalize("2024-01-01 09:00", source_tz="America/New_York")

# Relative date resolution
from datetime import datetime
processor = RelativeDateProcessor(reference_date=datetime(2025, 1, 15))
result = processor.process("3 days ago")
# → datetime(2025, 1, 12)

# Date range parsing
parser = TemporalExpressionParser()
result = parser.parse("from January 2020 to March 2021")
# → {"start": "2020-01-01", "end": "2021-03-31", "type": "range"}
```

## NumberNormalizer

```python
from semantica.normalize import NumberNormalizer

normalizer = NumberNormalizer()

normalizer.normalize_number("$1,234.56")   # → 1234.56
normalizer.normalize_number("€42K")         # → 42000.0
normalizer.normalize_number("$1.2B")        # → 1200000000.0
normalizer.normalize_number("3.14e-2")      # → 0.0314
normalizer.normalize_number("42%")          # → 0.42
```

Unit and currency conversion:

```python
from semantica.normalize import UnitConverter, CurrencyNormalizer

converter = UnitConverter()
result = converter.convert(100, from_unit="km/h", to_unit="m/s")
# → 27.78

# Supported categories: length, weight, volume, temperature, speed, area
categories = converter.list_categories()

currency_norm = CurrencyNormalizer()
result = currency_norm.normalize("$42.50")
# → {"amount": 42.50, "currency": "USD", "raw": "$42.50"}
```

## DataCleaner

```python
from semantica.normalize import DataCleaner, DataValidator

cleaner = DataCleaner()

# Remove near-duplicate records
deduped = cleaner.remove_duplicates(records, similarity_threshold=0.9)

# Fill missing values
filled = cleaner.fill_missing(records, strategy="mean")
# strategy options: "mean" | "median" | "mode" | "remove"

# Validate schema
validator = DataValidator()
result = validator.validate(records, schema={"name": str, "age": int})
print(result.valid_count, result.errors)
```

## LanguageDetector

```python
from semantica.normalize import LanguageDetector

detector = LanguageDetector()

lang = detector.detect("Bonjour le monde")
# → {"language": "fr", "confidence": 0.98}

# Top N languages for mixed-language text
langs = detector.detect_top_n("This might be mixed", n=3)
# → [{"language": "en", "probability": 0.85}, ...]

# Batch detection
results = detector.detect_batch(["Hello", "Hola", "Bonjour"])
```

## EncodingHandler

```python
from semantica.normalize import EncodingHandler

handler = EncodingHandler()

encoding = handler.detect_encoding(raw_bytes)
# → {"encoding": "windows-1252", "confidence": 0.73}

utf8_text = handler.to_utf8(raw_bytes)
clean     = handler.remove_bom(text_with_bom)
```

## Pipeline Integration

For large datasets, use the pipeline instead of per-item normalization:

```python
from semantica.pipeline import Pipeline
from semantica.normalize import TextNormalizer

pipeline = Pipeline()
pipeline.add_step("normalize", TextNormalizer())
result = pipeline.run(documents)
```

<CardGroup cols={2}>
  <Card title="Parse" icon="file-lines" href="parse">
    Parse documents before normalization.
  </Card>
  <Card title="Split" icon="scissors" href="split">
    Chunk normalized text for embedding.
  </Card>
  <Card title="Deduplication" icon="copy" href="deduplication">
    Resolve duplicate entities post-normalization.
  </Card>
  <Card title="Pipeline" icon="gear" href="pipeline">
    Include normalization as a pipeline step.
  </Card>
</CardGroup>
