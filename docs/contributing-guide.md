---
title: "Contributing"
description: "How to contribute code, documentation, tests, and community support to Semantica."
icon: "code-pull-request"
---

Contributions of all kinds are welcome — code, documentation, tests, and community support. Every contribution is recognized in release notes and the GitHub contributors list.

## Quick Start

```bash
# Fork the repo on GitHub, then:
git clone https://github.com/your-username/semantica.git
cd semantica
pip install -e ".[dev]"
pytest
```

New to the project? Start with [`good-first-issue`](https://github.com/semantica-agi/semantica/labels/good-first-issue) labeled tickets — they're scoped to be completable in a few hours without deep codebase knowledge.

## Ways to Contribute

### Code

- Fix bugs and resolve open issues
- Implement new features or integrations
- Optimize performance or refactor existing modules
- Add new ingestors, parsers, or exporters using the plugin registry

### Documentation

- Fix typos, improve clarity, and add missing examples
- Write tutorials or domain-specific cookbook notebooks
- Keep the API reference accurate as modules evolve

### Testing

- Add test coverage for untested modules or edge cases
- Reproduce and confirm reported bugs with a minimal repro
- Improve test reliability across Python versions and platforms

### Community

- Answer questions in GitHub Issues and Discussions
- Review open pull requests with constructive feedback
- Share Semantica in blog posts, talks, or conference demos

## Development Setup

```bash
git clone https://github.com/your-username/semantica.git
cd semantica
pip install -e ".[dev]"
```

**Code style tools:**

```bash
pytest                      # full test suite
black semantica/ tests/     # auto-format
isort semantica/ tests/     # sort imports
flake8 semantica/           # lint
```

Style conventions: **Black** for formatting, **isort** for imports, **flake8** for linting. All three run in CI.

## Reporting Issues

**Bug reports** should include:

- What happened vs. what you expected
- Minimal steps to reproduce
- Your environment: Python version, OS, Semantica version (`python -c "import semantica; print(semantica.__version__)"`)

**Feature requests** should include:

- Your concrete use case
- What you'd like Semantica to do
- Why it benefits a broad set of users, not just your specific workflow

## Pull Request Checklist

Before submitting a PR, confirm:

- [ ] Tests pass locally — `pytest`
- [ ] New features include documentation with working code examples
- [ ] Code follows project style — Black, isort, flake8
- [ ] Commit messages are clear and describe the *why*, not just the *what*
- [ ] No unresolved merge conflicts

## Code of Conduct

All contributors are expected to follow the [Contributor Covenant Code of Conduct](https://github.com/semantica-agi/semantica/blob/main/CODE_OF_CONDUCT.md). Be respectful, patient, and constructive — especially toward newcomers. Report violations by opening an issue with the `[CoC]` prefix.

## Help

- [GitHub Issues](https://github.com/semantica-agi/semantica/issues)
- [GitHub Discussions](https://github.com/semantica-agi/semantica/discussions)
- [Discord](https://discord.gg/sV34vps5hH)

<CardGroup cols={2}>
  <Card title="Community" icon="users" href="community">
    Community guidelines and values.
  </Card>
  <Card title="Governance" icon="scale-balanced" href="governance">
    How decisions are made and the project is run.
  </Card>
</CardGroup>
