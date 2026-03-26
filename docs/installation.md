# Installation

Get Semantica installed in under a minute.

!!! success "Available on PyPI"
    `pip install semantica` — that's it.

!!! note "Requirements"
    Python 3.8 or higher. Python 3.11+ recommended.

---

## Basic Installation

```bash
pip install semantica
```

With all optional dependencies:

```bash
pip install semantica[all]
```

### Verify

```bash
python -c "import semantica; print(semantica.__version__)"
```

---

## Virtual Environment (Recommended)

=== "venv"

    ```bash
    python -m venv venv
    source venv/bin/activate      # Linux / Mac
    venv\Scripts\activate         # Windows
    pip install semantica
    ```

=== "conda"

    ```bash
    conda create -n semantica python=3.11
    conda activate semantica
    pip install semantica
    ```

---

## Optional Dependencies

Install only what you need:

=== "GPU"

    ```bash
    pip install semantica[gpu]
    ```
    Includes PyTorch with CUDA, FAISS GPU, CuPy.

=== "Visualization"

    ```bash
    pip install semantica[viz]
    ```
    Includes PyVis, Graphviz, UMAP.

=== "LLM Providers"

    ```bash
    pip install semantica[llm-all]          # all providers

    pip install semantica[llm-openai]       # OpenAI
    pip install semantica[llm-anthropic]    # Anthropic
    pip install semantica[llm-gemini]       # Google Gemini
    pip install semantica[llm-groq]         # Groq
    pip install semantica[llm-ollama]       # Ollama (local)
    ```

=== "Cloud"

    ```bash
    pip install semantica[cloud]
    ```
    Includes AWS S3, Azure Blob, Google Cloud Storage.

---

## Install from Source

For the latest development version or to contribute:

```bash
git clone https://github.com/Hawksight-AI/semantica.git
cd semantica

pip install -e .          # core only
pip install -e ".[all]"   # all extras
pip install -e ".[dev]"   # dev tools (pytest, black, etc.)
```

If you encounter issues with the PyPI release, install directly from the main branch:

```bash
pip install git+https://github.com/Hawksight-AI/semantica.git@main
```

---

## Troubleshooting

### ModuleNotFoundError

Check you have the right environment active:

```bash
pip list | grep semantica
pip install --upgrade semantica
```

### Installation fails with dependency errors

```bash
pip install --upgrade pip
pip install build wheel
pip install semantica --no-deps   # install without optional deps first
```

### GPU dependencies fail

Install CPU-only first, then add GPU support:

```bash
pip install semantica
pip install semantica[gpu]
```

### Permission denied

```bash
pip install --user semantica      # or use a virtual environment
```

### Windows PyTorch DLL errors

Install the [Microsoft Visual C++ Redistributable](https://aka.ms/vs/17/release/vc_redist.x64.exe). This is a Windows system dependency, not a Semantica bug.

---

## System Requirements

| Component | Minimum | Recommended |
|-----------|---------|-------------|
| Python | 3.8 | 3.11+ |
| OS | Windows / Linux / Mac | Linux / Mac |
| RAM | 4 GB | 16 GB+ |
| Storage | 2 GB | 20 GB+ (for models and data) |

---

## Next Steps

- [Getting Started](getting-started.md) — build your first knowledge graph
- [Quickstart Tutorial](quickstart.md) — full step-by-step pipeline
- [Cookbook](cookbook.md) — interactive Jupyter notebook tutorials
