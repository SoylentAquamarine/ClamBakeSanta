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


# Words where CMU dict / the heuristic diverge from dictionary-standard
# (Merriam-Webster / howmanysyllables.com) syllable counts, checked before
# either. Add entries here as they're discovered rather than patching the
# general logic with a pattern rule — a blanket rule for one word's shape
# (e.g. silent "-gue", or "diphthong+r collapses to 1 syllable") can silently
# break other words that were already correct (verified 2026-08-17: a
# "-gue/-que ending" rule fixes "meringue" but breaks "dialogue"; a blanket
# "diphthong+er = 1 syllable" rule would wrongly collapse "flower"/"power"/
# "tower"/"higher"/"liar", which are genuinely 2 syllables each).
#
# CMU's ARPABET phones split "fire"-type words (diphthong + schwa-r, no
# intervening consonant) into 2 phonetic units, but dictionaries and common
# speech treat them as 1 syllable. Confirmed word-by-word against
# howmanysyllables.com 2026-08-17 — don't extend this list by pattern-
# matching new words, look each one up.
_SYLLABLE_EXCEPTIONS: dict[str, int] = {
    "meringue": 2,   # muh-RANG — not in CMU dict, heuristic overcounts as 3
    "fire": 1, "fires": 1, "fired": 1,
    "hour": 1, "hours": 1,
    "tire": 1, "tires": 1, "tired": 1,
    "hire": 1, "hires": 1, "hired": 1,
    "sour": 1, "sours": 1,
    "our": 1,
    "flour": 1, "flours": 1,
    "desire": 2, "desires": 2,
    "firefly": 2, "fireflies": 2,  # fire-fly — compound word, own CMU entry (3), not derived from "fire"
}


def count_syllables(word: str) -> int:
    """Count syllables in a single word using CMU dict with heuristic fallback."""
    word_clean = re.sub(r"[^a-zA-Z]", "", word)
    if not word_clean:
        return 0

    override = _SYLLABLE_EXCEPTIONS.get(word_clean.lower())
    if override is not None:
        return override

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
