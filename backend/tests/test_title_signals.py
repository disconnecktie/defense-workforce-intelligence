"""Deterministic title-only extractor tests.

The extractor does not inspect descriptions, infer unadvertised skills,
or rely on live employer data.
"""

import pytest

from app.analytics.title_signals import (
    CANONICAL_TERMS, RULE_VERSION, extract_title_signals,
)


@pytest.mark.parametrize(("title", "expected"), [
    ("Senior Python Engineer", ("Python",)),
    ("PYTHON / python Developer", ("Python",)),
    ("Senior K8s Platform Engineer", ("Kubernetes",)),
    ("Kubernetes Site Reliability Engineer", ("Kubernetes",)),
    ("AWS Cloud Engineer", ("AWS",)),
    ("Amazon Web Services Developer", ("AWS",)),
    ("Azure Cloud Architect", ("Azure",)),
    ("Microsoft Azure Integration Developer", ("Azure",)),
    ("Docker Infrastructure Specialist", ("Docker",)),
    ("Postgres Database Administrator", ("PostgreSQL",)),
    ("PostgreSQL DBA", ("PostgreSQL",)),
    ("React.js Frontend Engineer", ("React",)),
    ("ReactJS UI Developer", ("React",)),
    ("React Frontend Lead", ("React",)),
    ("Python & AWS & Kubernetes Specialist", ("Python", "Kubernetes", "AWS")),
    ("Systems Engineer", ()),
    ("Reactivate System Support", ()),
    ("Awesome Test Technician", ()),
    ("Postgraduate Research Associate", ()),
    ("Azureline Support", ()),
    ("Dockerized Deployment", ()),
    ("Pythonista", ()),
    ("K8stack Developer", ()),
    ("reactivity Researcher", ()),
])
def test_explicit_bounded_title_keyword_matches(title, expected):
    signals = extract_title_signals(title)
    assert tuple(item.term for item in signals) == expected
    for item in signals:
        assert title[item.start:item.end] == item.evidence
        assert item.rule_version == RULE_VERSION
        assert item.start < item.end
    assert len({item.term for item in signals}) == len(signals)


def test_alias_repetition_counts_once_per_canonical_term():
    title = "Python/PYTHON and AWS, Amazon Web Services"
    signals = extract_title_signals(title)
    assert tuple(item.term for item in signals) == ("Python", "AWS")
    assert [item.evidence for item in signals] == ["Python", "AWS"]


def test_extractor_has_stable_controlled_dictionary():
    assert CANONICAL_TERMS == (
        "Python", "Kubernetes", "AWS", "Azure",
        "Docker", "PostgreSQL", "React",
    )


def test_requires_text_without_coercing_nonstring_input():
    with pytest.raises(TypeError, match="title must be a string"):
        extract_title_signals(None)
