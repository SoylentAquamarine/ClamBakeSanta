"""
Syllable validator for haiku 5-7-5 verification.

Uses the CMU Pronouncing Dictionary via the `pronouncing` package when available.
Falls back to a vowel-cluster heuristic for unknown words or missing package.
"""
from __future__ import annotations
import re

_pronouncing_available: bool | None = None


def _try_import_pronouncing() -> bool:
    global _pronouncing_available
    if _pronouncing_available is None:
        try:
            import pronouncing as _p  # noqa: F401
            _pronouncing_available = True
        except ImportError:
            _pronouncing_available = False
    return _pronouncing_available


def _heuristic_syllables(word: str) -> int:
    """Vowel-cluster heuristic — reasonable for common English words."""
    word = re.sub(r"[^a-z]", "", word.lower())
    if not word:
        return 0
    count = len(re.findall(r"[aeiou]+", word))
    # Silent terminal 'e': "cake", "rise", "time" — not "bee", "toe"
    if word.endswith("e") and len(word) > 2 and word[-2] not in "aeiou":
        count -= 1
    return max(1, count)


def count_syllables(word: str) -> int:
    """Count syllables in a single word using CMU dict with heuristic fallback."""
    word_clean = re.sub(r"[^a-zA-Z]", "", word)
    if not word_clean:
        return 0

    if _try_import_pronouncing():
        import pronouncing
        phones_list = pronouncing.phones_for_word(word_clean.lower())
        if phones_list:
            return pronouncing.syllable_count(phones_list[0])

    return _heuristic_syllables(word_clean)


def count_line_syllables(line: str) -> int:
    """Count total syllables across all words in a line."""
    return sum(count_syllables(w) for w in line.split())


def validate_haiku(haiku_text: str) -> tuple[bool, list[int]]:
    """
    Check whether haiku_text contains a valid 5-7-5 poem.

    The closing attribution line (containing '#' or '@') is excluded.
    Returns (valid, [line1, line2, line3]) or (False, []) if < 3 poem lines found.
    """
    lines = [ln.strip() for ln in haiku_text.split("\n") if ln.strip()]
    poem_lines = [
        ln for ln in lines
        if not ln.startswith("#") and "@" not in ln
    ][:3]

    if len(poem_lines) < 3:
        return False, []

    counts = [count_line_syllables(ln) for ln in poem_lines]
    return counts == [5, 7, 5], counts


# Known test cases used by scripts/validate_haiku.py --test
# Format: (line_text, expected_syllable_count)
TEST_CASES: list[tuple[str, int]] = [
    ("Flour clouds softly rise", 5),
    ("Golden biscuits crown the table", 8),
    ("Butter dreams melt slow", 5),
]
