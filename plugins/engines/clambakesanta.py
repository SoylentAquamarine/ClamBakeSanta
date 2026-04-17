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
import os
import re

from framework.registry import register
from framework.engines.base import BaseEngine
from framework.models import Event, Result

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
        f'Write a single three-line haiku in natural 5-7-5 syllable style.\n'
        f'Theme: "{theme}"\n'
        f"Use sensory detail and vivid imagery. Keep it warm and celebratory.{avoid_block}\n"
        f'End with exactly this line: "{closing}"\n'
        f"Output only the 4 lines, nothing else."
    )


@register("engines", "clambakesanta")
class ClamBakeSantaEngine(BaseEngine):
    """
    Generates one haiku per theme using an AI language model.

    Result.content     : all haikus joined by double newline (ready to post)
    Result.metadata    : {"haikus": [{"theme": str, "haiku": str, "tag": str}],
                          "themes": [str], "date": str}
    """

    def process(self, event: Event) -> Result:
        themes: list[str] = event.payload.get("themes", [])

        if not themes:
            return Result(
                event=event,
                engine_id="clambakesanta",
                content=f"No holidays found for {event.date_str}. Check your data files.",
                metadata={"haikus": [], "themes": [], "date": event.date_str},
            )

        # Load recent opening phrases to guide the model toward fresh imagery
        avoid = self._recent_openers()
        if avoid:
            import logging
            logging.getLogger(__name__).info(
                "Anti-repetition: avoiding %d recent phrase(s)", len(avoid)
            )

        haiku_records: list[dict] = []
        for theme in themes:
            haiku_text = self._generate(theme, avoid)
            haiku_records.append({
                "theme": theme,
                "haiku": haiku_text,
                "tag": _hashtag(theme),
            })

        content = "\n\n".join(r["haiku"] for r in haiku_records)

        return Result(
            event=event,
            engine_id="clambakesanta",
            content=content,
            metadata={
                "haikus": haiku_records,
                "themes": themes,
                "date": event.date_str,
            },
        )

    def _recent_openers(self) -> list[str]:
        """Return opening lines from the last 7 days of haiku history."""
        try:
            from framework.haiku_log import opening_phrases
            return opening_phrases(self.config, days=7)
        except Exception:
            return []

    def _generate(self, theme: str, avoid_phrases: list[str] | None = None) -> str:
        """Call the AI API and return 4 lines of haiku text."""
        try:
            from openai import OpenAI
        except ImportError:
            return (
                f"(openai package missing — run: pip install openai)\n"
                f"{theme}\n"
                f"Happy #{_hashtag(theme)} from @ClamBakeSanta"
            )

        # GitHub Models endpoint — free with GITHUB_TOKEN (auto-injected in Actions)
        # Override with CBS_AI_BASE_URL / CBS_AI_KEY to use any other provider
        base_url = os.environ.get(
            "CBS_AI_BASE_URL", "https://models.inference.ai.azure.com"
        )
        api_key = (
            os.environ.get("CBS_AI_KEY")
            or os.environ.get("GITHUB_TOKEN", "")
        )
        model = self.config.get("ai", {}).get("model", "gpt-4o-mini")

        client = OpenAI(base_url=base_url, api_key=api_key)
        try:
            resp = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": _make_prompt(theme, avoid_phrases)},
                ],
                temperature=0.85,
                max_tokens=120,
            )
            raw = resp.choices[0].message.content.strip()
            lines = [ln.rstrip() for ln in raw.splitlines() if ln.strip()]
            return "\n".join(lines[:4])
        except Exception as exc:
            # Graceful fallback — never crash the whole run over one haiku
            return (
                f"(generation error: {exc})\n"
                f"{theme}\n"
                f"Happy #{_hashtag(theme)} from @ClamBakeSanta"
            )
