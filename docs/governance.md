---
title: "Governance"
description: "Project governance model — roles, decision process, release cadence, and code review guidelines."
icon: "scale-balanced"
---

> Semantica is maintained by Hawksight AI with community contributions under an open governance model.

---

## Roles

**Maintainers** (Hawksight AI team)
- Review and merge pull requests
- Manage releases and code quality
- Set project direction and community standards

**Contributors**
- Submit code, documentation, and bug reports
- Help with issues and reviews
- Recognized in [CONTRIBUTORS.md](https://github.com/semantica-agi/semantica/blob/main/CONTRIBUTORS.md)

**Community Members**
- Use Semantica and provide feedback
- Share use cases and participate in discussions

---

## Decision Process

### Code Changes

<Steps>
  <Step title="Proposal">Open a GitHub Issue describing the change.</Step>
  <Step title="Discussion">Community discussion on approach and scope.</Step>
  <Step title="Implementation">Submit a pull request with the change.</Step>
  <Step title="Review">At least one maintainer reviews the PR.</Step>
  <Step title="Merge">Merged after CI passes and maintainer approval.</Step>
</Steps>

### Major Decisions

- RFC posted in GitHub Issues
- Minimum 1-week community discussion period
- Maintainers decide based on community feedback and technical feasibility

---

## Releases

Semantica follows **Semantic Versioning** (`MAJOR.MINOR.PATCH`):

| Level | Trigger | Cadence |
|-------|---------|---------|
| MAJOR | Breaking changes | Quarterly or as needed |
| MINOR | New features (backward compatible) | Monthly or when ready |
| PATCH | Bug fixes (backward compatible) | As bugs are fixed |

---

## Code Review

**Review criteria:** functionality, code quality, tests, documentation, performance, security.

**Timeline:** initial review within 48 hours; follow-up within 7 days.

**Guidelines for reviewers:** be constructive, explain reasoning, suggest alternatives.

**Guidelines for contributors:** address comments promptly, ask questions when unclear, be open to feedback.

---

## Communication

- **GitHub Issues** — bug reports, feature requests, questions
- **GitHub PRs** — code contributions
- **GitHub Discussions** — community conversation
- **Security Advisories** — [report security issues privately](https://github.com/semantica-agi/semantica/security/advisories/new)

---

## Project Goals

1. **Usability** — Easy to use and understand
2. **Reliability** — Production-ready quality
3. **Performance** — Efficient and scalable
4. **Extensibility** — Easy to extend with plugins and custom modules
5. **Community** — Welcoming and inclusive

---

## License

MIT License — see [LICENSE](https://github.com/semantica-agi/semantica/blob/main/LICENSE) and the [License page](license).

---

## See Also

<CardGroup cols={2}>
  <Card title="Contributing" icon="code-pull-request" href="contributing-guide">
    How to submit changes.
  </Card>
  <Card title="Community" icon="users" href="community">
    Community guidelines and channels.
  </Card>
</CardGroup>
