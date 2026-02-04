# Documentation

> **Complete documentation for Semantica - organized for contributors and users.**

This directory contains all Semantica documentation, organized into logical sections for different user types and purposes.

## 📁 Documentation Structure

```
docs/
├── README.md               # This file - documentation overview
├── mkdocs.yml              # MkDocs configuration file
├── index.md                # Main landing page
├── user-guide/             # 📖 User documentation
│   ├── README.md           # User guide overview
│   ├── getting-started.md  # Installation and first steps
│   ├── concepts.md         # Core concepts and terminology
│   ├── modules.md          # Module overview and architecture
│   ├── deep-dive.md        # Technical deep dive
│   ├── examples.md         # Practical code examples
│   ├── cookbook.md         # Interactive tutorials
│   ├── use-cases.md        # Real-world applications
│   ├── faq.md              # Frequently asked questions
│   └── glossary.md         # Comprehensive terminology
├── developer/              # 👨‍💻 Developer resources
│   ├── README.md           # Developer overview and setup
│   └── contributing.md      # How to contribute
├── community/              # 👥 Community resources
│   ├── README.md           # Community overview
│   ├── community.md        # Community guidelines
│   ├── projects.md         # Community projects
│   └── governance.md       # Project governance
├── legal/                  # ⚖️ Legal information
│   ├── README.md           # Legal overview
│   ├── license.md          # MIT License
│   └── citation.md         # Academic citation guidelines
├── api/                    # 📚 API documentation
│   ├── README.md           # API overview and navigation
│   ├── change_management.md # Change management API
│   ├── conflicts.md         # Conflict detection API
│   ├── context.md           # Context management API
│   ├── core.md              # Core framework API
│   ├── deduplication.md     # Deduplication API
│   ├── embeddings.md        # Embeddings API
│   ├── evals.md             # Evaluation API
│   ├── export.md            # Export API
│   ├── graph_store.md       # Graph store API
│   ├── ingest.md            # Data ingestion API
│   ├── kg.md                # Knowledge graph API
│   ├── llms.md              # LLM integration API
│   ├── normalize.md          # Data normalization API
│   ├── ontology.md          # Ontology API
│   ├── parse.md             # Document parsing API
│   ├── pipeline.md          # Pipeline API
│   ├── provenance.md        # Provenance tracking API
│   ├── reasoning.md          # Reasoning API
│   ├── seed.md              # Seed data API
│   ├── semantic_extract.md   # Semantic extraction API
│   ├── split.md             # Text splitting API
│   ├── triplet_store.md      # Triplet store API
│   ├── utils.md              # Utility functions API
│   ├── vector_store.md      # Vector store API
│   └── visualization.md     # Visualization API
├── integrations/           # 🔌 Integration guides
│   ├── docling.md           # Docling integration
│   └── snowflake_ingestion.md # Snowflake integration
├── assets/                 # 🎨 Static assets
│   ├── css/                 # Custom CSS styles
│   └── js/                  # Custom JavaScript
└── netlify.toml            # Netlify deployment config
```

## 🚀 Getting Started

### For Users
1. **Start Here**: Read the [main landing page](index.md)
2. **Learn Basics**: Check [Getting Started](user-guide/getting-started.md)
3. **Understand Concepts**: Read [Core Concepts](user-guide/concepts.md)
4. **Explore Modules**: See [Modules & Architecture](user-guide/modules.md)
5. **Try Examples**: Follow [Examples](user-guide/examples.md)

### For Developers
1. **Setup**: Read [Developer Guide](developer/README.md)
2. **Contribute**: Follow [Contributing Guide](developer/contributing.md)
3. **API Reference**: Check [API Documentation](api/README.md)
4. **Configuration**: Edit [mkdocs.yml](mkdocs.yml)

### For Community Members
1. **Join**: Read [Community Overview](community/README.md)
2. **Participate**: Follow [Community Guidelines](community/community.md)
3. **Share Projects**: Add to [Community Projects](community/projects.md)

## 🛠️ Working with Documentation

### Local Development

#### Install Dependencies
```bash
pip install mkdocs-material
pip install mkdocs-jupyter
pip install mkdocstrings[python]
```

#### Serve Documentation Locally

**Option 1: From Project Root (Traditional)**
```bash
# From project root directory
mkdocs serve
```

**Option 2: From Docs Folder (New - Recommended)**
```bash
# Navigate to docs folder
cd docs

# Run documentation server
mkdocs serve

# Or build for production
mkdocs build
```

#### Why the New Structure?
- **Self-Contained**: All documentation files in one location
- **Independent**: Can work on docs without touching source code
- **Clear Organization**: Logical grouping by user type and purpose
- **Contributor-Friendly**: Easier for new contributors to understand

### Configuration

#### MkDocs Configuration
The documentation is configured using [mkdocs.yml](mkdocs.yml):

- **Theme**: Material for MkDocs
- **Navigation**: Organized by user type and purpose
- **Extensions**: Markdown extensions for enhanced formatting
- **Plugins**: Search, syntax highlighting, API docs

#### Adding New Documentation
1. **Choose Location**: Add to appropriate folder (user-guide/, developer/, community/, legal/, api/)
2. **Update Navigation**: Edit [mkdocs.yml](mkdocs.yml) to include new pages
3. **Add Links**: Update cross-references in related files
4. **Test Locally**: Run `mkdocs serve` to preview changes

#### Navigation Structure
```yaml
nav:
  - Home: index.md
  - User Guide:
    - Overview: user-guide/README.md
    - Getting Started: user-guide/getting-started.md
    # ... more user-guide pages
  - Developer Guide:
    - Overview: developer/README.md
    - Contributing: developer/contributing.md
    - API Reference: api/
  - Community:
    - Overview: community/README.md
    # ... more community pages
  - Legal:
    - Overview: legal/README.md
    # ... more legal pages
```

### Content Guidelines

#### Writing Style
- **Clear Language**: Use simple, clear language
- **Consistent Formatting**: Follow established patterns
- **Working Examples**: Include tested code examples
- **Cross-References**: Link to related documentation

#### Markdown Features
- **Admonitions**: Use `!!! note`, `!!! tip`, `!!! warning` for callouts
- **Code Blocks**: Use proper syntax highlighting
- **Tables**: Use markdown tables for structured data
- **Links**: Use relative links for internal references

#### File Organization
- **One Topic Per File**: Each file should focus on one main topic
- **Logical Naming**: Use descriptive, lowercase filenames
- **Proper Headers**: Use appropriate heading levels (H1, H2, H3)
- **Table of Contents**: Include TOC for longer pages

## 📚 Documentation Types

### User Documentation (`user-guide/`)
- **Getting Started**: Installation and first steps
- **Concepts**: Fundamental ideas and terminology
- **Modules**: System components and architecture
- **Examples**: Practical code examples
- **FAQ**: Common questions and answers

### Developer Documentation (`developer/`)
- **Contributing**: How to contribute to the project
- **Setup**: Development environment configuration
- **API Reference**: Complete technical documentation

### Community Documentation (`community/`)
- **Guidelines**: Community participation rules
- **Projects**: Community-built projects
- **Governance**: Project decision-making

### Legal Documentation (`legal/`)
- **License**: MIT License information
- **Citation**: Academic citation guidelines
- **Compliance**: Legal and regulatory information

### API Documentation (`api/`)
- **Module APIs**: Complete API reference for all modules
- **Code Examples**: Working code examples
- **Configuration**: Setup and usage instructions

## 🔧 Customization

### Styling
- **CSS**: Custom styles in `assets/css/`
- **JavaScript**: Interactive features in `assets/js/`
- **Theme**: Material for MkDocs with customizations

### Plugins
- **Search**: Full-text search functionality
- **Code Highlighting**: Syntax highlighting for code blocks
- **API Docs**: Automatic API documentation generation
- **Jupyter**: Interactive notebook support

## 🚀 Deployment

### Local Preview
```bash
mkdocs serve
```

### Production Build
```bash
mkdocs build
```

### Netlify Deployment
- **Configuration**: `netlify.toml`
- **Automatic**: Deploy on push to main branch
- **Preview**: Preview builds for pull requests

## 🤝 Contributing to Documentation

### How to Contribute
1. **Fork Repository**: Create your own fork
2. **Make Changes**: Edit documentation files
3. **Test Locally**: Run `mkdocs serve` to preview
4. **Submit PR**: Create pull request with changes

### What to Contribute
- **Fix Errors**: Correct typos and inaccuracies
- **Add Examples**: Provide practical code examples
- **Improve Clarity**: Make explanations clearer
- **Add Content**: Cover missing topics
- **Update Links**: Fix broken references

### Review Process
- **Technical Review**: Ensure accuracy of technical content
- **Style Review**: Check formatting and consistency
- **Link Review**: Verify all links work correctly
- **User Testing**: Ensure documentation is user-friendly

---

!!! tip "Quick Start"
    To start contributing to documentation:
    1. Read the [Contributing Guide](developer/contributing.md)
    2. Set up local development environment
    3. Make your changes
    4. Test with `mkdocs serve`
    5. Submit a pull request

!!! success "Welcome Contributors!"
    We welcome all contributions to Semantica's documentation. Whether you're fixing a typo, adding an example, or writing a complete guide, your contribution helps make Semantica better for everyone!
