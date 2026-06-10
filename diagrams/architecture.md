# System Architecture

High-level view of the current ClamBakeSanta implementation: GitHub Actions trigger Python entry points, `framework.runner` executes the plugin pipeline, adapters publish sequentially, and state is committed back to the repository.

```mermaid
flowchart TD
    subgraph ACTIONS["GitHub Actions"]
        MONTHLY["generate_monthly.yml\nmonthly generated data"]
        SUBWF["check_subscriptions.yml\ncurrent script is placeholder"]
        DAILY["daily.yml\npython run.py"]
        ENGWF["check_engagement.yml\npython check_engagement.py"]
        REPORT["weekly_report.yml\npython weekly_report.py"]
    end

    subgraph DATA["Data Layer"]
        FH["data/MONTH_randomholiday.txt\nfixed holidays"]
        EH["data/ephemeral/YYYY-MM.txt\nvariable-date holidays"]
        CB["data/MONTH_celebritybirthday.txt\ncelebrity birthdays"]
        CE["data/celestial/YYYY-MM.txt\nmoon phases, zodiac, meteor showers"]
        RULES["data/ephemeral_rules.txt\nhuman-maintained rules"]
    end

    subgraph PIPELINE["Daily Framework Pipeline"]
        RUNPY["run.py\nloads config.yml"]
        RUNNER["framework.runner\nsource → engine/cache → adapters → state"]
        SRC["daily_themes source\npriority + cap logic"]
        ENGINE["clambakesanta engine\nAI generation + 5-7-5 validation"]
        CACHE[("state/haiku_cache.json\nshared same-day result")]
    end

    subgraph ADAPTERS["Adapters run sequentially in config.yml order"]
        MA["mastodon"]
        BS["bluesky"]
        TU["tumblr"]
        TG["telegram"]
        EL["email_list\nreads subscribers.json"]
        RD["reddit"]
        WP["wordpress"]
        GP["github_pages\nHTML + RSS"]
        DC["discord"]
    end

    subgraph STATE["Repository State"]
        HL["state/haiku_log/"]
        RL["state/run_log/"]
        WB["state/writers_block/"]
        PI["state/post_ids/"]
        EN["state/engagement/"]
        SB["state/subscribers.json\nplanned subscription store"]
        DOCS["docs/\nGitHub Pages output"]
    end

    subgraph ANALYTICS["Analytics and Reporting"]
        CHECK["check_engagement.py"]
        WEEKLY["weekly_report.py"]
    end

    RULES --> MONTHLY
    MONTHLY --> EH & CE
    FH & EH & CB & CE --> SRC

    DAILY --> RUNPY --> RUNNER --> SRC
    SRC -->|"Event(themes)"| ENGINE
    ENGINE <-->|"cache hit/miss"| CACHE
    ENGINE -->|"Result"| RUNNER

    RUNNER -->|"for each adapter"| MA --> BS --> TU --> TG --> EL --> RD --> WP --> GP --> DC

    MA & BS & TU & TG & RD & WP --> PI
    GP --> DOCS
    EL -. reads .-> SB
    SUBWF -. planned future maintenance .-> SB

    RUNNER --> HL & RL & WB & CACHE
    PI --> CHECK
    ENGWF --> CHECK --> EN
    REPORT --> WEEKLY
    EN --> WEEKLY

    style SUBWF fill:#7f5539,color:#fff
    style SB fill:#7f5539,color:#fff
    style ADAPTERS fill:#1d3557,color:#fff
```

## Important implementation notes

- The pipeline is plugin-based, but the active haiku implementation is configured by `config.yml`.
- Adapters are independent but **not parallel**. `framework.runner` iterates through them sequentially in `config.yml` order.
- Missing adapter credentials generally cause that adapter to skip without stopping the run.
- The subscription workflow is scheduled, but the current `check_subscriptions.py` file is placeholder/demo code. The daily email adapter can send to addresses already present in `state/subscribers.json`; automated Gmail-based subscribe/unsubscribe processing is still pending.
- GitHub Actions schedules live in `.github/workflows/*.yml`, not in `config.yml`.
