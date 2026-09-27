# AI Backend — Multi-Provider Fallback Chain

How haiku generation actually calls an AI, why it's not just one provider, and
how to test/extend it without risking a live post to real subscribers/socials.

## Why this exists

GitHub Models (the original free AI backend) was fully retired 2026-07-30 with
no warning, which silently zeroed out haiku generation for 10 days before
anyone noticed (see `state/run_log/` history around 2026-07-31). The fix
wasn't "pick a new provider" — free AI provider tiers turned out to be
individually unreliable (deprecated models, shared-pool rate limits, quota
quirks). The real fix was: **never depend on just one provider again**, plus
an immediate email alert if a day still produces zero haikus despite that.

## The cascade

```mermaid
flowchart TD
    THEME(["One theme, e.g.\n'National Rice Pudding Day'"])
    THEME --> P1

    subgraph P1["Provider 1: primary (Groq)"]
        P1A["Attempt 1..5\ntemperature=0.85"] --> P1CHECK{Valid 5-7-5\nor still trying?}
        P1CHECK -- "valid" --> DONE
        P1CHECK -- "permanent error\n(bad key/model, 401/404/402...)" --> P1SKIP["Skip remaining\nattempts for this provider"]
        P1CHECK -- "transient error or\nsyllable mismatch,\nattempts left" --> P1A
    end

    P1SKIP --> P2
    P1CHECK -- "5 attempts exhausted,\nstill no valid haiku" --> P2

    subgraph P2["Provider 2: mistral"]
        P2A["Same 5-attempt loop"]
    end
    P2 --> P3["Provider 3: cohere\n(same loop)"]
    P3 --> PN["... down through\nconfig.yml ai.fallback,\nin order"]
    PN --> LAST["Last provider\n(huggingface)"]

    LAST -- "also exhausted" --> WB(["Raise WritersBlock\nfor this theme only"])
    DONE(["Return haiku_text, counts\nto process() for this theme"])

    style DONE fill:#2d6a4f,color:#fff
    style WB fill:#c1121f,color:#fff
    style P1SKIP fill:#e76f51,color:#fff
```

This whole cascade runs **once per theme**, independently. A theme that
succeeds on the primary provider never touches the fallback chain. A theme
that fails on the primary tries every fallback in order before it's marked
writer's block — see [Writer's Block Handling](writers-block.md) for what
happens after that (fallback theme, `state/writers_block/` logging, etc).

Code: `_generate()` in `plugins/engines/clambakesanta.py` runs the cascade;
`_providers()` in the same file builds the ordered list from config + env vars.

## Current provider chain

Ordered by confidence, in `config.yml` under `ai.fallback` (primary is set by
`ai.model` + `CBS_AI_KEY`/`CBS_AI_BASE_URL` env vars, not the fallback list).

| # | Provider | Status (as of 2026-09-27) | Model | Notes |
|---|---|---|---|---|
| 1 | **Groq** (primary) | ✅ Working | `openai/gpt-oss-20b` | Reasoning model — needs `reasoning_effort: low`. Re-verified clean 3/3 |
| 2 | **Mistral** | ❌ Now failing | `mistral-small-latest` | Was working as of 2026-08-10. Every request across 4 separate test runs (~60 calls) on 2026-09-27 got an immediate `429 rate_limited` (code 1300), even on the very first attempt of a run — looks like account-level quota exhaustion (free tier is 500k tokens/month, 1 req/s), not the burst congestion OpenRouter has. Not fixable via config — check the Mistral console for remaining quota/plan status |
| 3 | **Cohere** | ⚠️ Degraded | `command-r7b-12-2024` | API itself is healthy (HTTP 200 on every call), but on 2026-09-27 it failed syllable validation on **all ~20 test attempts** across 4 runs — mostly "got unknown" (response didn't parse into countable lines at all). Was clean 5-7-5 output as of 2026-08-10. Looks like a model-quality regression, not a config bug — no config fix applied, needs a closer look at raw responses before swapping models |
| 4 | **Cerebras** | ❌ Now blocked | `gpt-oss-120b` | Was working as of 2026-08-10. Every call now returns `402 payment_required`. Confirmed via web research: Cerebras killed its no-card free tier on 2026-08-17 — accounts now need a payment method on file for $5/mo trial credits. Same shape as the SambaNova removal. Not fixable via config; kept in the chain as a harmless no-cost skip unless/until a card is added |
| 5 | **OpenRouter** | ⚠️ Unreliable | `google/gemma-4-31b-it:free` | Unchanged — `:free` models route through a shared pool, still repeatedly 429s on congestion (also hit the per-minute free-models cap directly once this run). Not fixable by retrying |
| 6 | **Pollinations** | ✅ Working (anonymous) | `openai` | Unchanged — succeeded immediately on most themes across all runs; occasionally needs its full 5 retries on one theme, still within normal variance |
| 7 | **Gemini** | ⚠️ Reachable, unreliable | `gemini-3.8-flash` | **Fixed 2026-09-27**: old id `gemini-2.0-flash` was fully retired (404, Google's error named `gemini-3.8-flash` as the replacement, GA'd 2026-09-02) — confirmed via live search, model id updated. The old "blocked, quota limit:0" billing issue is also gone (no more quota-zero error). But the Flash tier's free quota is very tight — hit `RESOURCE_EXHAUSTED` at "limit: 5" requests/minute during testing — and even un-throttled responses mostly failed syllable parsing ("got unknown"). Recommend evaluating `gemini-3.5-flash-lite` (500 free requests/day vs Flash's ~20/day, per current docs) as a follow-up — not applied here since it needs its own verification pass |
| 8 | **Fireworks** | ✅ Fixed | `accounts/fireworks/models/gpt-oss-120b` | **Fixed 2026-09-27**: `gpt-oss-20b` was dropped from Fireworks' serverless catalog in their September 2026 update (confirmed via live docs — 404 "Model not found, inaccessible, and/or not deployed"). Swapped to `gpt-oss-120b`, their current flagship low-cost serverless model, same `reasoning_effort: low` handling. Re-verified 3/3 haikus |
| 9 | **HuggingFace** | ✅ Working (capped) | `meta-llama/Llama-3.1-8B-Instruct` | Unchanged — router auto-selects a provider by default. Runs out of free monthly credits fast if over-tested |

Removed entirely (tried, deliberately dropped — see git log for
`config.yml` around 2026-08-09/10 for the full reasoning):

- **OpenAI** — worked once the key was rotated, but $0 billing credits; not worth funding as a backstop when 6+ other providers already work for free
- **Together** — free credits exhausted
- **DeepSeek** — no free tier at all, real balance required
- **SambaNova** — requires a payment method on file even at $0 spend

Not wired in at all:

- **Cloudflare Workers AI** — different request/response shape, not
  OpenAI-compatible, would need real code changes plus an account ID we don't
  pass around
- **Ollama** (local) — GitHub Actions runners can't reach a home machine
  without a public tunnel (ngrok/Cloudflare Tunnel), which would make the
  daily run depend on that machine being powered on and online every morning

## The rules (hard-won, 2026-08-09/10)

1. **`reasoning_effort` is provider-specific, never send it blindly.**
   Reasoning models (Groq/Cerebras `gpt-oss-*`) will silently burn their
   entire `max_tokens` budget on hidden chain-of-thought and return **empty
   content** at default effort — looks like a dead API, not a config issue,
   unless you know to check `finish_reason`. Setting `reasoning_effort: low`
   fixes it. But sending that same parameter to Mistral or Cohere gets a hard
   `400`/`422` — they don't support `"low"`/`"medium"` at all. Solution: set
   `reasoning_effort` per-provider in `config.yml` (only where needed), never
   as a blanket default. See `providers[i]["reasoning_effort"]` in
   `_providers()`.

2. **A `400`/`401`/`402`/`404` from a provider is a config problem, not a
   flaky API — don't retry it 5 times.** `_is_permanent_failure()` matches
   on these (plus balance/quota-zero phrases) and breaks out of that
   provider's retry loop immediately, moving to the next provider. Without
   this, a single misconfigured provider wastes ~5x its own latency on every
   theme, every run, forever.

3. **Model IDs go stale fast — verify against the provider's live docs, not
   memory.** Every provider we manually configured a model for got it wrong
   at least once (Cerebras twice). When a provider 404s with "model not
   found" or similar, don't just guess a different name — fetch that
   provider's actual current model list.

4. **Error text can be misleading.** HuggingFace's 400 said "not supported by
   any provider you have enabled" — reads like an account setting is missing.
   It isn't; HF's router auto-selects across all providers by default. The
   real issue was the model just isn't hosted anywhere on their router. Read
   docs before acting on an error message's implied fix.

5. **`optional_key: true` exists for providers that work anonymously**
   (Pollinations). Don't skip a provider just because no secret is
   configured for it if its own docs say auth is optional.

6. **Testing burns real, finite quota.** Several providers (HuggingFace,
   Together, Fireworks' $1 credit) have small enough free allowances that a
   single afternoon of manual testing can exhaust them for the rest of the
   month. Prefer `--engine-only` test runs (below) over repeated live
   `daily.yml` triggers, and don't re-test a provider that already passed
   just to double-check.

7. **A GitHub Actions run "succeeding" (`conclusion: success`) does NOT mean
   haikus posted.** The runner intentionally marks a zero-haiku day as
   "complete" to avoid retry-spam — so no Actions failure notification ever
   fires on its own. The `state/run_log/` entry's `haikus_posted` count is
   the only reliable signal, plus the failure-alert email described below.

8. **`ai_key_secret` in Test AI Backend must be the repo *secret name*, not
   the `CBS_AI_KEY` env var it maps to.** The workflow does
   `secrets[inputs.ai_key_secret]` — pass `ai_key_secret="CBS_AI_KEY"` and it
   silently resolves to nothing (repo has no secret literally named that),
   logged as "no API key set" and easy to mistake for primary being broken.
   Primary Groq's actual secret is `GROQ_API_KEY` (see `daily.yml`'s env
   block) — pass `ai_key_secret="GROQ_API_KEY"` to test it in isolation.

## How to test

**Never trigger `daily.yml` (the real "Daily Haiku Generation" workflow) just
to test a provider** — a successful run posts to Mastodon, Bluesky, Tumblr,
Telegram, WordPress, and emails every subscriber. Use one of these instead:

### 1. Test one specific provider (safe, no posting)

Actions → **Test AI Backend** → Run workflow, or:

```bash
gh workflow run "Test AI Backend" --ref main \
  -f ai_key_secret="CEREBRAS_API_KEY" \
  -f ai_base_url="https://api.cerebras.ai/v1" \
  -f ai_model="gpt-oss-120b"
```

Forces that provider as `primary` via `CBS_AI_KEY`/`CBS_AI_BASE_URL`/
`CBS_AI_MODEL`, runs `python run.py --force --regenerate --engine-only`
(engine only — every adapter is skipped, nothing is posted or emailed
anywhere), and logs pass/fail per theme.

### 2. Test the whole fallback chain for real

Same workflow, leave `ai_key_secret` blank:

```bash
gh workflow run "Test AI Backend" --ref main -f ai_key_secret=""
```

Every fallback secret is already wired into that workflow's env block, so
`config.yml`'s `ai.fallback` list runs exactly as it would on the real daily
run — except primary (Groq) is intentionally unset, so it skips straight to
the fallback chain. Useful for confirming the cascade order and catching a
newly-broken provider.

### 3. Test a provider that needs no key, fully locally

If a provider works anonymously (like Pollinations), you don't need GitHub
Actions at all:

```bash
python3 -c "
from openai import OpenAI
client = OpenAI(base_url='https://text.pollinations.ai/openai', api_key='')
resp = client.chat.completions.create(
    model='openai',
    messages=[{'role':'user','content':'Say OK'}],
    max_tokens=20,
)
print(resp.choices[0].message.content)
"
```

### Reading the results

```bash
gh run view <run-id> --log 2>&1 | grep -iE "Haiku OK|Run complete|API error via|Skipping provider|exhausted|permanent"
```

- `Haiku OK` — that theme succeeded, whichever provider is named in the
  preceding `Valid haiku via '<name>'` line
- `Skipping provider 'X' — no API key set` — that secret isn't configured
  (or is empty)
- `Provider 'X' failure looks permanent` — fast-skipped, see the rules above
- `Provider 'X' exhausted after 5 attempt(s)` — retried the full 5x, still
  no valid haiku (either persistent transient errors or repeated syllable
  mismatches)
- `Run complete | ... adapters_ok=[]` — confirms nothing was posted
  (`--engine-only` did its job)

## How to add a new provider

1. Get an API key (or confirm the provider works anonymously).
2. Find its OpenAI-compatible base URL and a plain (non-reasoning) model ID
   from its **current** docs — don't reuse an ID from memory or an old
   example.
3. Add a GitHub secret: `gh secret set YOUR_PROVIDER_API_KEY --repo SoylentAquamarine/clambakesanta`
4. Add an entry to `config.yml` → `ai.fallback`:
   ```yaml
   - name: yourprovider
     base_url: https://api.yourprovider.com/v1
     key_env: YOUR_PROVIDER_API_KEY
     model: some-plain-instruct-model
     # reasoning_effort: low   # only if it's a reasoning model
     # optional_key: true      # only if it works without a key
   ```
5. Wire the secret through as an env var in **both**
   `.github/workflows/daily.yml` and `.github/workflows/test_ai_backend.yml`
   (search for the existing `CEREBRAS_API_KEY` lines in each — copy the
   pattern).
6. Test it in isolation (method 1 above) before trusting it in the chain.

## Where things live

| What | File |
|---|---|
| Provider cascade + retry logic | `plugins/engines/clambakesanta.py` — `_generate()`, `_providers()`, `_is_permanent_failure()` |
| Provider chain config | `config.yml` — `ai.model` (primary), `ai.fallback` (rest) |
| Engine-only test mode | `run.py` — `--engine-only` flag |
| Safe provider testing workflow | `.github/workflows/test_ai_backend.yml` |
| Real daily run (has posting side effects) | `.github/workflows/daily.yml` |
| Zero-haiku failure alert | `framework/alerts.py`, called from `framework/runner.py` when `not haikus` |
