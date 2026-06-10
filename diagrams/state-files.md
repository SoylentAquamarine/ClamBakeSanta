# State File Map

What lives in `state/`, what creates each file, and how long it is retained.

```mermaid
flowchart LR
    subgraph DAILY["daily.yml run"]
        RUN["framework.runner"]
        ENG["clambakesanta engine"]
        ADP["Adapter plugins"]
    end

    subgraph ENGAGEMENT["check_engagement.yml run"]
        CHK["check_engagement.py"]
    end

    subgraph SUBS["check_subscriptions.yml run"]
        SUB["check_subscriptions.py\ncurrent implementation is placeholder"]
    end

    subgraph STATE["state/"]
        HC["haiku_cache.json\nToday's haikus shared by all adapters\nOverwritten by new generation"]
        HL["haiku_log/YYYY-MM-DD.json\nDaily generated haikus\nRetained forever"]
        HR["haiku_log/recent.json\nRolling 7-day summary\nAnti-repetition input"]
        RL["run_log/YYYY-MM-DD.json\nRun summary\n30-day rolling retention"]
        WB["writers_block/YYYY-MM-DD.json\nFailed AI attempts\n30-day rolling retention"]
        PI["post_ids/YYYY-MM-DD.json\nPer-platform post IDs and URLs\nRetained forever"]
        PS["post_ids/summary.json\nRolling 7-day post ID index\nRebuilt by post_store"]
        EN["engagement/YYYY-MM-DD.json\nEngagement metrics per post\nRetained forever"]
        ES["engagement/summary.json\nRolling 7-day engagement summary\nRebuilt by engagement_store"]
        SB["subscribers.json\nIntended email subscriber list\nSubscription automation not complete"]
    end

    RUN -->|"cache + logs"| HC & HL & HR & RL
    ENG -->|"writer's block attempts"| WB
    ADP -->|"post IDs when supported"| PI & PS
    CHK -->|"engagement snapshots"| EN & ES
    SUB -. planned .-> SB

    style STATE fill:#1d3557,color:#fff
    style SUB fill:#7f5539,color:#fff
    style SB fill:#7f5539,color:#fff
```

## Current notes

- `state/subscribers.json` is the intended subscriber list location.
- The daily `email_list` adapter reads `state/subscribers.json` and sends the digest to listed addresses.
- The scheduled `check_subscriptions.yml` workflow exists, but the current `check_subscriptions.py` implementation is placeholder/demo code and does not yet poll Gmail, process real SUBSCRIBE/UNSUBSCRIBE mail, or maintain `state/subscribers.json`.

## Retention policy

| Path | Created or maintained by | Retention |
|---|---|---|
| `state/haiku_cache.json` | `framework.runner` | Overwritten by fresh generation |
| `state/haiku_log/YYYY-MM-DD.json` | `framework/haiku_log.py` | Forever |
| `state/haiku_log/recent.json` | `framework/haiku_log.py` | Rolling 7-day rebuild |
| `state/run_log/YYYY-MM-DD.json` | `framework/run_log.py` | 30-day auto-prune |
| `state/writers_block/YYYY-MM-DD.json` | `framework/writers_block_log.py` | 30-day auto-prune |
| `state/post_ids/YYYY-MM-DD.json` | Publishing adapters | Forever |
| `state/post_ids/summary.json` | `framework/post_store.py` | Rolling 7-day rebuild |
| `state/engagement/YYYY-MM-DD.json` | `check_engagement.py` | Forever |
| `state/engagement/summary.json` | `framework/engagement_store.py` | Rolling 7-day rebuild |
| `state/subscribers.json` | Planned subscription management subsystem; read by `email_list` | Live list; not pruned |
