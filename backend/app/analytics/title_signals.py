"""Conservative title-keyword signals, not job-description skill requirements.

Rule-set v1 matches only explicit, bounded technology names within a title.
It does not infer proficiency, required qualifications, or demand from a title.
Every signal has the original title substring as auditable evidence.
"""

from dataclasses import dataclass
import re

RULE_VERSION = "title_keywords_v1"

# Pattern order is priority order for the evidence selected within a term;
# all labels are counted at most once per distinct current posting.
_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("Python", re.compile(r"(?<![A-Za-z0-9])python(?![A-Za-z0-9])", re.IGNORECASE)),
    ("Kubernetes", re.compile(r"(?<![A-Za-z0-9])(?:kubernetes|k8s)(?![A-Za-z0-9])", re.IGNORECASE)),
    ("AWS", re.compile(r"(?<![A-Za-z0-9])(?:aws|amazon[ \t]+web[ \t]+services)(?![A-Za-z0-9])", re.IGNORECASE)),
    ("Azure", re.compile(r"(?<![A-Za-z0-9])(?:microsoft[ \t]+azure|azure)(?![A-Za-z0-9])", re.IGNORECASE)),
    ("Docker", re.compile(r"(?<![A-Za-z0-9])docker(?![A-Za-z0-9])", re.IGNORECASE)),
    ("PostgreSQL", re.compile(r"(?<![A-Za-z0-9])(?:postgresql|postgres)(?![A-Za-z0-9])", re.IGNORECASE)),
    ("React", re.compile(r"(?<![A-Za-z0-9])(?:react(?:\.js|js)?)(?![A-Za-z0-9])", re.IGNORECASE)),
)

CANONICAL_TERMS = tuple(label for label, _ in _PATTERNS)


@dataclass(frozen=True)
class TitleSignal:
    term: str
    evidence: str
    start: int
    end: int
    rule_version: str = RULE_VERSION


def extract_title_signals(title: str) -> tuple[TitleSignal, ...]:
    """Find explicit standalone technology mentions in a raw title.

    Retains the actual matched substring and offsets for review. A posting
    contributes at most one mention to each canonical term count, even when
    the title repeats the alias.
    """
    if not isinstance(title, str):
        raise TypeError("title must be a string")
    findings = []
    for term, pattern in _PATTERNS:
        match = pattern.search(title)
        if match is not None:
            findings.append(TitleSignal(
                term=term,
                evidence=match.group(0),
                start=match.start(),
                end=match.end(),
            ))
    return tuple(findings)
