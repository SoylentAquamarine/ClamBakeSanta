"""
clambakesanta — Engine plugin. Example implementation of the framework.

This engine is a whimsical daily haiku generator. It is one example of
what an Engine can do. It can be replaced with any other engine
(system monitor, report generator, newsletter writer) without touching
the framework.

AI backend: GitHub Models (GPT-4o-mini) via GITHUB_TOKEN
  - Free — no billing, no credit card
  - GITHUB_TOKEN is auto-injected in every GitHub Actions run
  - Swappable: set CBS_AI_BASE_URL + CBS_AI_KEY for any OpenAI-compatible API
    (e.g. Anthropic, Ollama, Azure OpenAI)

Safety design:
  - YOU control subjects via the data files (no AI picking topics)
  - System prompt instructs the model to stay positive and neutral
  - Hashtag formatting is deterministic (not AI-generated)
"""
from __future__ import annotations
import html
import logging
import os
import re

_log = logging.getLogger(__name__)
_MAX_RETRIES = 5

from framework.registry import register
from framework.engines.base import BaseEngine
from framework.models import Event, Result
from framework.validation import register_metadata_validator

# ── Metadata schema validator ────────────────────────────────────────────────
# This runs automatically inside the runner after process() returns.
# It describes exactly what this engine promises to put in Result.metadata
# and loudly rejects any Result that doesn't match — catching bugs before
# they silently reach any publishing adapter.
@register_metadata_validator("clambakesanta")
def _validate_metadata(metadata: dict) -> list[str]:
    """
    Every ClamBakeSanta Result must have:
      metadata["haikus"]  — list of dicts, each with str fields theme/haiku/tag
      metadata["themes"]  — list of strings (the raw theme names)
      metadata["date"]    — YYYY-MM-DD string matching the run date
    """
    errors: list[str] = []

    # ── haikus list ───────────────────────────────────────────────────────────
    haikus = metadata.get("haikus")
    if not isinstance(haikus, list):
        errors.append("metadata['haikus'] must be a list")
    else:
        for i, rec in enumerate(haikus):
            if not isinstance(rec, dict):
                errors.append(f"haikus[{i}] must be a dict, got {type(rec).__name__}")
                continue
            for key in ("theme", "haiku", "tag"):
                if not isinstance(rec.get(key), str):
                    errors.append(
                        f"haikus[{i}]['{key}'] must be a str, "
                        f"got {type(rec.get(key)).__name__}"
                    )
            # Each haiku should have at least 2 non-empty lines (poem + hashtag)
            lines = [ln for ln in rec.get("haiku", "").split("\n") if ln.strip()]
            if len(lines) < 2:
                errors.append(
                    f"haikus[{i}]['haiku'] must have at least 2 lines, got {len(lines)}"
                )

    # ── themes list ───────────────────────────────────────────────────────────
    themes = metadata.get("themes")
    if not isinstance(themes, list):
        errors.append("metadata['themes'] must be a list")
    elif any(not isinstance(t, str) for t in themes):
        errors.append("every entry in metadata['themes'] must be a string")

    # ── date string ───────────────────────────────────────────────────────────
    date_val = metadata.get("date")
    if not date_val or not re.match(r"^\d{4}-\d{2}-\d{2}$", str(date_val)):
        errors.append(f"metadata['date'] must match YYYY-MM-DD, got {date_val!r}")

    return errors


# ── Safety system prompt ────────────────────────────────────────────────────
# This travels with every single API call. Adjust here if needed.
SYSTEM_PROMPT = (
    "You are ClamBakeSanta, a warm and whimsical seasonal poetry bot. "
    "Write celebratory haikus with vivid sensory imagery. "
    "Keep all content joyful, inclusive, and appropriate for all audiences. "
    "Never reference politics, religion, controversy, or anything divisive. "
    "Focus on achievements, warmth, nature, and the spirit of the occasion."
)


def _hashtag(theme: str) -> str:
    """Convert a theme string to a clean CamelCase hashtag."""
    if theme.lower().startswith("birthday "):
        name = re.sub(r"[^A-Za-z0-9]", "", theme[9:])
        return f"HappyBirthday{name}"
    words = re.findall(r"[A-Za-z0-9]+", theme)
    return "".join(w.capitalize() for w in words)


def _make_prompt(theme: str, avoid_phrases: list[str] | None = None) -> str:
    tag = _hashtag(theme)
    is_birthday = theme.lower().startswith("birthday ")
    closing = (
        f"#{tag} from @ClamBakeSanta"
        if is_birthday
        else f"Happy #{tag} from @ClamBakeSanta"
    )
    avoid_block = ""
    if avoid_phrases:
        # Show up to 14 recent openers so the model picks genuinely fresh imagery
        listed = ", ".join(f'"{p}"' for p in avoid_phrases[:14])
        avoid_block = (
            f"\nFor variety, avoid starting with opening words or images similar to: {listed}."
        )
    return (
        f'Write a single three-line haiku with EXACTLY 5-7-5 syllables.\n'
        f'Theme: "{theme}"\n'
        f"Count every syllable carefully before finalizing each line. "
        f"Prefer short, common words with unambiguous syllable counts. "
        f"Avoid contractions, hyphenated words, or words with irregular pronunciation. "
        f"Use sensory detail and vivid imagery. Keep it warm and celebratory.{avoid_block}\n"
        f'End with exactly this line: "{closing}"\n'
        f"Output only the 4 lines, nothing else."
    )


class WritersBlock(Exception):
    """Raised when the AI cannot produce a valid 5-7-5 after all retries."""
    def __init__(self, theme: str, tag: str, attempts: list[dict]):
        self.theme    = theme
        self.tag      = tag
        self.attempts = attempts  # [{"text": str, "counts": list[int]}, ...]
        super().__init__(
            f"Writer's block on {theme!r} — no valid 5-7-5 after {len(attempts)} attempt(s)"
        )


@register("engines", "clambakesanta")
class ClamBakeSantaEngine(BaseEngine):
    """
    Generates one haiku per theme using an AI language model.

    Result.content     : all haikus joined by double newline (ready to post)
    Result.metadata    : {"haikus": [{"theme": str, "haiku": str, "tag": str,
                                      "syllable_counts": [int,int,int],
                                      "valid_syllables": bool}],
                          "themes": [str],
                          "writers_block": [{"theme": str, "tag": str, "attempts": int}],
                          "date": str}
    """

    def process(self, event: Event) -> Result:
        themes: list[str] = event.payload.get("themes", [])

        if not themes:
            return Result(
                event=event,
                engine_id="clambakesanta",
                content=f"No holidays found for {event.date_str}. Check your data files.",
                metadata={"haikus": [], "themes": [], "writers_block": [], "date": event.date_str},
            )

        # Load recent opening phrases to guide the model toward fresh imagery
        avoid = self._recent_openers()
        if avoid:
            _log.info("Anti-repetition: avoiding %d recent phrase(s)", len(avoid))

        from framework.haiku_validator import validate_haiku
        from framework import writers_block_log

        haiku_records: list[dict]     = []
        writers_block_themes: list[dict] = []

        for theme in themes:
            tag = _hashtag(theme)
            try:
                haiku_text, counts = self._generate(theme, avoid)
                valid = counts == [5, 7, 5]
                haiku_records.append({
                    "theme":           theme,
                    "haiku":           haiku_text,
                    "tag":             tag,
                    "syllable_counts": counts,
                    "valid_syllables": valid,
                })
                syllable_str = "-".join(str(c) for c in counts)
                if valid:
                    _log.info("Haiku OK  [5-7-5] theme=%r", theme)
                else:
                    _log.warning("Haiku posted with syllable mismatch [%s] theme=%r",
                                 syllable_str, theme)

            except WritersBlock as wb:
                _log.warning("Writer's block — skipping theme=%r after %d attempt(s)",
                             theme, len(wb.attempts))
                writers_block_themes.append({"theme": theme, "tag": tag,
                                             "attempts": len(wb.attempts)})
                writers_block_log.append(
                    self.config, event.date_str, theme, tag, wb.attempts
                )

        if not haiku_records:
            _log.warning("Writer's block on ALL themes — generating fallback haiku.")
            haiku_records = self._generate_fallback(
                event.date_str, avoid, writers_block_themes, writers_block_log
            )

        _log.info("Generated %d/%d haiku(s) — %d writer's block",
                  len(haiku_records), len(themes), len(writers_block_themes))

        content = "\n\n".join(r["haiku"] for r in haiku_records)

        return Result(
            event=event,
            engine_id="clambakesanta",
            content=content,
            metadata={
                "haikus":        haiku_records,
                "themes":        themes,
                "writers_block": writers_block_themes,
                "date":          event.date_str,
            },
        )

    # Fallback themes used when every scheduled theme hits writer's block.
    # Override via config.yml key "fallback_themes".
    _FALLBACK_THEMES = [
        "The Beauty of Each Day",
        "Simple Joys",
        "Nature's Wonder",
        "A Moment of Peace",
        "The Changing Seasons",
        "Gratitude",
        "Small Miracles",
    ]

    def _generate_fallback(
        self,
        date_str: str,
        avoid: list[str],
        writers_block_themes: list[dict],
        wb_log,
    ) -> list[dict]:
        """
        Generate one haiku from a random fallback theme.

        Called only when every scheduled theme hit writer's block.
        If the fallback also hits writer's block, use the last raw attempt
        rather than going completely silent.
        """
        import random
        fallback_pool = self.config.get("fallback_themes", self._FALLBACK_THEMES)
        theme = random.choice(fallback_pool)
        tag   = _hashtag(theme)
        _log.info("Fallback theme selected: %r", theme)

        try:
            haiku_text, counts = self._generate(theme, avoid)
            _log.info("Fallback haiku OK [5-7-5] theme=%r", theme)
            return [{
                "theme":           theme,
                "haiku":           haiku_text,
                "tag":             tag,
                "syllable_counts": counts,
                "valid_syllables": True,
                "fallback":        True,
            }]
        except WritersBlock as wb:
            # Extremely unlikely — log it and use the last raw attempt.
            _log.error("Fallback theme also hit writer's block — using last raw attempt.")
            writers_block_themes.append({"theme": theme, "tag": tag,
                                         "attempts": len(wb.attempts), "fallback": True})
            wb_log.append(self.config, date_str, theme, tag, wb.attempts)

            if wb.attempts:
                last_text   = wb.attempts[-1]["text"]
                last_counts = wb.attempts[-1]["counts"]
                return [{
                    "theme":           theme,
                    "haiku":           last_text,
                    "tag":             tag,
                    "syllable_counts": last_counts,
                    "valid_syllables": False,
                    "fallback":        True,
                }]
            # Nothing at all — return empty and let the runner handle it.
            _log.error("No fallback haiku available — run will commit with no content.")
            return []

    def _recent_openers(self) -> list[str]:
        """Return opening lines from the last 7 days of haiku history."""
        try:
            from framework.haiku_log import opening_phrases
            return opening_phrases(self.config, days=7)
        except Exception:
            return []

    def _generate(
        self, theme: str, avoid_phrases: list[str] | None = None
    ) -> tuple[str, list[int]]:
        """
        Call the AI API and return (haiku_text, syllable_counts).

        Retries up to _MAX_RETRIES times on syllable mismatches.  Every attempt
        that gets a response is recorded (text + counts) for the writer's block log.
        Raises WritersBlock if no valid 5-7-5 is produced after all retries.
        """
        try:
            from openai import OpenAI
        except ImportError:
            fallback = (
                f"(openai package missing — run: pip install openai)\n"
                f"{theme}\n"
                f"Happy #{_hashtag(theme)} from @ClamBakeSanta"
            )
            return fallback, []

        from framework.haiku_validator import validate_haiku

        # GitHub Models endpoint — free with GITHUB_TOKEN (auto-injected in Actions)
        # Override with CBS_AI_BASE_URL / CBS_AI_KEY to use any other provider
        base_url = os.environ.get(
            "CBS_AI_BASE_URL", "https://models.inference.ai.azure.com"
        )
        api_key = (
            os.environ.get("CBS_AI_KEY")
            or os.environ.get("GITHUB_TOKEN", "")
        )
        model  = self.config.get("ai", {}).get("model", "gpt-4o-mini")
        client = OpenAI(base_url=base_url, api_key=api_key)

        attempts: list[dict] = []  # recorded for writers_block_log if all retries fail

        for attempt in range(1, _MAX_RETRIES + 1):
            try:
                resp = client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user",   "content": _make_prompt(theme, avoid_phrases)},
                    ],
                    temperature=0.85,
                    max_tokens=120,
                )
                raw   = resp.choices[0].message.content.strip()
                lines = [ln.rstrip() for ln in raw.splitlines() if ln.strip()]
                haiku_text = "\n".join(lines[:4])

                valid, counts = validate_haiku(haiku_text)
                attempts.append({"text": haiku_text, "counts": counts})

                if valid:
                    if attempt > 1:
                        _log.info("Valid haiku on attempt %d/%d | theme=%r",
                                  attempt, _MAX_RETRIES, theme)
                    return haiku_text, counts

                got = "-".join(str(c) for c in counts) if counts else "unknown"
                _log.warning(
                    "Syllable mismatch (attempt %d/%d): expected 5-7-5, got %s | theme=%r",
                    attempt, _MAX_RETRIES, got, theme,
                )
            except Exception as exc:
                _log.error("API error (attempt %d/%d) | theme=%r: %s",
                           attempt, _MAX_RETRIES, theme, exc)
                # No haiku_text to record — API didn't respond

        # All retries exhausted — caller decides what to do (writer's block)
        raise WritersBlock(theme, _hashtag(theme), attempts)
