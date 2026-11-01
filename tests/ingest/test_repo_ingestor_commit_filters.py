"""Regression tests for ``RepoIngestor.analyze_commits`` filters.

``analyze_commits`` used to build its filters as bare ``git log`` flags
(``-N``, ``--since=...``) and pass them positionally to
``Repo.iter_commits``, which treats positional arguments as the revision and
paths. ``git rev-list`` then failed with its usage text (exit code 129), the
error was swallowed, and every filtered call returned an empty list, so
``ingest_repository(..., commit_filters={"max_commits": N})`` silently lost
the whole commit history.

These tests run against a real throwaway repository, so they are skipped when
GitPython (``semantica[ingest-git]``) or the ``git`` binary is unavailable.
"""

from __future__ import annotations

import shutil

import pytest

git = pytest.importorskip("git")

from semantica.ingest.repo_ingestor import RepoIngestor  # noqa: E402

pytestmark = pytest.mark.skipif(
    shutil.which("git") is None, reason="git binary is not installed"
)


@pytest.fixture
def history_repo(tmp_path):
    """A repository with three commits by two authors on three distinct days."""
    repo = git.Repo.init(tmp_path)
    alice = git.Actor("Alice", "alice@example.com")
    bob = git.Actor("Bob", "bob@example.com")
    commits = [
        ("first.txt", "first", alice, "2024-01-01T10:00:00+0000"),
        ("second.txt", "second", bob, "2024-01-02T10:00:00+0000"),
        ("third.txt", "third", alice, "2024-01-03T10:00:00+0000"),
    ]
    for filename, message, actor, stamp in commits:
        (tmp_path / filename).write_text(f"{message}\n", encoding="utf-8")
        repo.index.add([filename])
        repo.index.commit(
            message,
            author=actor,
            committer=actor,
            author_date=stamp,
            commit_date=stamp,
        )
    return tmp_path


def test_analyze_commits_without_filters_returns_full_history(history_repo):
    commits = RepoIngestor().analyze_commits(history_repo)

    assert [c.message for c in commits] == ["third", "second", "first"]
    assert commits[0].files_changed == ["third.txt"]
    assert commits[0].additions == 1


def test_max_commits_limits_the_newest_commits(history_repo):
    commits = RepoIngestor().analyze_commits(history_repo, max_commits=2)

    assert [c.message for c in commits] == ["third", "second"]


def test_since_and_until_bound_the_history(history_repo):
    ingestor = RepoIngestor()

    since = ingestor.analyze_commits(history_repo, since="2024-01-02T00:00:00+0000")
    assert [c.message for c in since] == ["third", "second"]

    until = ingestor.analyze_commits(history_repo, until="2024-01-02T23:59:59+0000")
    assert [c.message for c in until] == ["second", "first"]


def test_author_filter_keeps_only_that_author(history_repo):
    commits = RepoIngestor().analyze_commits(history_repo, author="Bob")

    assert [c.message for c in commits] == ["second"]
    assert commits[0].author.startswith("Bob")


def test_filters_combine(history_repo):
    commits = RepoIngestor().analyze_commits(
        history_repo, author="Alice", max_commits=1
    )

    assert [c.message for c in commits] == ["third"]


def test_ingest_repository_forwards_commit_filters(history_repo):
    ingestor = RepoIngestor()
    try:
        result = ingestor.ingest_repository(
            str(history_repo),
            include_history=True,
            commit_filters={"max_commits": 2},
        )
    finally:
        ingestor.cleanup()

    assert [c["message"] for c in result["commits"]] == ["third", "second"]
