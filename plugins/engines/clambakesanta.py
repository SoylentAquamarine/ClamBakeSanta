"""
clambakesanta — Engine plugin. Example implementation of the framework.

This engine is a whimsical daily haiku generator. It is one example of
what an Engine can do. It can be replaced with any other engine
(system monitor, report generator, newsletter writer) without touching
the framework.

AI backend: Groq's free tier via CBS_AI_KEY (a Groq API key from
  https://console.groq.com/keys), called through Groq's OpenAI-compatible
  endpoint. Model is openai/gpt-oss-20b with reasoning_effort="low" — Groq's
  classic non-reasoning Llama models (llama-3.1-8b-instant,
  llama-3.3-70b-versatile) deprecate 2026-08-16, so gpt-oss is the
  actively-maintained path. gpt-oss is a reasoning model and will burn its
  token budget on hidden chain-of-thought at default effort (confirmed via
  OpenRouter on 2026-08-09 — returned empty content every time); passing
  reasoning_effort="low" keeps that overhead small enough to leave room for
  the actual haiku.
  - Free — no billing, no credit card. Quota is per-key (yours alone), not a
    shared pool.
  - GitHub Models (the original free backend) was fully retired 2026-07-30 —
    do not point this back at models.inference.ai.azure.com, it is gone for good.
  - Also ruled out 2026-08-09: OpenRouter's ":free" models (lineup churns
    with no warning, one candidate 429'd on a congested shared pool within
    minutes) and Gemini free tier (returns quota limit:0 unless you link a
    billing account — defeats the point).
  - Swappable: set CBS_AI_BASE_URL + CBS_AI_KEY for any OpenAI-compatible API
    (e.g. OpenAI, Anthropic, Ollama, Azure OpenAI, OpenRouter, Mistral).

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


_PERMANENT_FAILURE_MARKERS = (
    "error code: 400", "error code: 401", "error code: 404", "error code: 402",
    "unauthorized", "invalid_api_key", "invalid api key",
    "model_not_found", "does not exist", "unavailable for free",
    "not supported by any provider",
    # Balance/payment issues won't resolve within a few rapid retries either.
    "insufficient", "credit_limit", "payment_required", "payment required",
    "insufficient_quota", "balance",
    # A hard zero quota (e.g. Gemini's free tier before billing is linked)
    # is structurally different from an ordinary rate limit — "retry in Ns"
    # will never help because the limit itself is 0, not just used up.
    "limit: 0,",
)


def _is_permanent_failure(exc: Exception) -> bool:
    """
    True if an API error looks like a config problem (bad key, wrong model
    id) rather than something a retry could fix (rate limit, timeout, 5xx).
    Used to skip a misconfigured provider's remaining retries and move on
    to the next one instead of burning all _MAX_RETRIES attempts on it.
    """
    text = str(exc).lower()
    return any(marker in text for marker in _PERMANENT_FAILURE_MARKERS)


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

        providers = self._providers()
        attempts: list[dict] = []  # recorded for writers_block_log if every provider fails

        for provider in providers:
            if not provider["api_key"] and not provider.get("optional_key"):
                _log.info("Skipping provider %r — no API key set (%s)",
                          provider["name"], provider.get("key_env", "CBS_AI_KEY"))
                continue

            client = OpenAI(base_url=provider["base_url"], api_key=provider["api_key"])

            # Only reasoning-model providers need this — Mistral and Cohere
            # both reject an unrecognized/unsupported reasoning_effort value
            # outright with a 400/422 (confirmed 2026-08-09), so this must be
            # opt-in per provider, not sent to everyone.
            extra_body = {"reasoning_effort": provider["reasoning_effort"]} \
                if provider.get("reasoning_effort") else None

            for attempt in range(1, _MAX_RETRIES + 1):
                try:
                    resp = client.chat.completions.create(
                        model=provider["model"],
                        messages=[
                            {"role": "system", "content": SYSTEM_PROMPT},
                            {"role": "user",   "content": _make_prompt(theme, avoid_phrases)},
                        ],
                        temperature=0.85,
                        max_tokens=300,
                        **({"extra_body": extra_body} if extra_body else {}),
                    )
                    raw = (resp.choices[0].message.content or "").strip()
                    if not raw:
                        raise ValueError(
                            f"Empty content (finish_reason={resp.choices[0].finish_reason!r}) "
                            "— model likely spent the token budget on hidden reasoning"
                        )
                    lines = [ln.rstrip() for ln in raw.splitlines() if ln.strip()]
                    haiku_text = "\n".join(lines[:4])

                    valid, counts = validate_haiku(haiku_text)
                    attempts.append({"text": haiku_text, "counts": counts})

                    if valid:
                        if attempt > 1 or provider is not providers[0]:
                            _log.info("Valid haiku via %r on attempt %d/%d | theme=%r",
                                      provider["name"], attempt, _MAX_RETRIES, theme)
                        return haiku_text, counts

                    got = "-".join(str(c) for c in counts) if counts else "unknown"
                    _log.warning(
                        "Syllable mismatch via %r (attempt %d/%d): expected 5-7-5, got %s | theme=%r",
                        provider["name"], attempt, _MAX_RETRIES, got, theme,
                    )
                except Exception as exc:
                    _log.error("API error via %r (attempt %d/%d) | theme=%r: %s",
                               provider["name"], attempt, _MAX_RETRIES, theme, exc)
                    # No haiku_text to record — API didn't respond
                    if _is_permanent_failure(exc):
                        _log.warning(
                            "Provider %r failure looks permanent (bad key/model, not "
                            "transient) — skipping remaining retries, trying next provider",
                            provider["name"],
                        )
                        break
            else:
                _log.warning("Provider %r exhausted after %d attempt(s) — trying next provider",
                             provider["name"], _MAX_RETRIES)

        # Every configured provider exhausted — caller decides what to do (writer's block)
        raise WritersBlock(theme, _hashtag(theme), attempts)

    def _providers(self) -> list[dict]:
        """
        Build the ordered list of AI providers to try for this run.

        Primary provider comes from CBS_AI_BASE_URL / CBS_AI_KEY / CBS_AI_MODEL
        env vars (or config.yml ai.model), defaulting to Groq's free tier.
        Additional fallback providers come from config.yml ai.fallback — a list
        of {name, base_url, key_env, model} — tried in order only if the
        primary exhausts all retries without a valid haiku. Each fallback's key
        comes from its own named env var (a GitHub secret), so multiple
        providers can be configured at once without code changes.
        """
        ai_config = self.config.get("ai", {})
        providers = [{
            "name":             "primary",
            "base_url":         os.environ.get("CBS_AI_BASE_URL") or "https://api.groq.com/openai/v1",
            "api_key":          os.environ.get("CBS_AI_KEY") or "",
            "key_env":          "CBS_AI_KEY",
            "model":            os.environ.get("CBS_AI_MODEL") or ai_config.get("model", "openai/gpt-oss-20b"),
            # gpt-oss is a reasoning model — see the extra_body comment above.
            "reasoning_effort": ai_config.get("reasoning_effort", "low"),
        }]
        for fb in ai_config.get("fallback", []):
            providers.append({
                "name":             fb.get("name", fb.get("key_env", "fallback")),
                "base_url":         fb["base_url"],
                "api_key":          os.environ.get(fb["key_env"]) or "",
                "key_env":          fb["key_env"],
                "model":            fb["model"],
                "reasoning_effort": fb.get("reasoning_effort"),
                # Providers that work anonymously (e.g. Pollinations) — don't
                # skip them just because no key is configured.
                "optional_key":     fb.get("optional_key", False),
            })
        return providers
