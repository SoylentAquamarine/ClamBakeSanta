# State File Map

What lives in `state/`, what creates each file, and how long it's retained.

```mermaid
flowchart LR
    subgraph DAILY["daily.yml run"]
        RUN["runner.py"]
        ENG["clambakesanta engine"]
        ADP["Adapters"]
    end

    subgraph ENGAGEMENT["check_engagement.yml run"]
        CHK["check_engagement.py"]
    end

    subgraph SUBS["check_subscriptions.yml run"]
        SUB["check_subscriptions.py"]
    end

    subgraph STATE["state/"]
        HC["haiku_cache.json\nToday's haikus — shared by all adapters\nOverwritten daily"]
        HL["haiku_log/YYYY-MM-DD.json\nEvery haiku ever generated\nRetained forever"]
        HR["haiku_log/recent.json\nRolling 7-day summary\nRebuilt daily (anti-repetition input)"]
        RL["run_log/YYYY-MM-DD.json\nRun summary: themes, haikus posted,\nwriter's block, adapter results\n30-day rolling retention"]
        WB["writers_block/YYYY-MM-DD.json\nFailed haiku attempts\n(text + syllable counts per attempt)\n30-day rolling retention"]
        PI["post_ids/YYYY-MM-DD.json\nPer-platform post IDs + URLs\nRetained forever"]
        PS["post_ids/summary.json\nRolling 7-day index\nRebuilt daily"]
        EN["engagement/YYYY-MM-DD.json\nLikes · boosts · replies per post\nRetained forever"]
        ES["engagement/summary.json\nRolling 7-day summary\nRebuilt daily"]
        SB["subscribers.json\nEmail mailing list\nUpdated on every SUBSCRIBE/UNSUBSCRIBE"]
    end

    RUN -->|"cache + log"| HC & HL & HR & RL
    ENG -->|"writer's block log"| WB
    ADP -->|"post IDs"| PI & PS
    CHK -->|"engagement data"| EN & ES
    SUB -->|"subscriber list"| SB

    style STATE fill:#1d3557,color:#fff
```

### Retention policy

| Path | Created by | Retention |
|---|---|---|
| `state/haiku_cache.json` | `runner.py` | Overwritten daily |
| `state/haiku_log/YYYY-MM-DD.json` | `framework/haiku_log.py` | Forever |
| `state/haiku_log/recent.json` | `framework/haiku_log.py` | Rolling 7-day rebuild |
| `state/run_log/YYYY-MM-DD.json` | `framework/run_log.py` | 30-day auto-prune |
| `state/writers_block/YYYY-MM-DD.json` | `framework/writers_block_log.py` | 30-day auto-prune |
| `state/post_ids/YYYY-MM-DD.json` | Adapters (mastodon, bluesky, etc.) | Forever |
| `state/post_ids/summary.json` | `framework/post_store.py` | Rolling 7-day rebuild |
| `state/engagement/YYYY-MM-DD.json` | `check_engagement.py` | Forever |
| `state/engagement/summary.json` | `framework/engagement_store.py` | Rolling 7-day rebuild |
| `state/subscribers.json` | `check_subscriptions.py` | Live list — never pruned |
