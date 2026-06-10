# Daily Workflow Sequence

Step-by-step sequence of a full daily run, from the GitHub Actions trigger through framework execution, adapter publishing, state updates, and the final repository commit.

```mermaid
sequenceDiagram
    participant GHA as GitHub Actions daily.yml
    participant RunPy as run.py
    participant Runner as framework.runner
    participant Source as daily_themes source
    participant Engine as clambakesanta engine
    participant Cache as state/haiku_cache.json
    participant Adapter as Adapter plugin
    participant State as state/ files

    GHA->>RunPy: python run.py or python run.py --force
    RunPy->>Runner: run(config, force, regenerate=false)

    Runner->>Source: source.produce()
    Source->>Source: ensure monthly generated files exist
    Source->>Source: read fixed holidays
    Source->>Source: read ephemeral holidays
    Source->>Source: read celebrity birthdays
    Source->>Source: read celestial events if slots remain
    Source-->>Runner: Event(date, themes)

    Runner->>Runner: validate_event(event)
    Runner->>State: already_ran_today(date)?
    alt already ran and not forced
        Runner-->>RunPy: skipped summary
        RunPy-->>GHA: exit 0
    else continue
        Runner->>Cache: load cache for date
        alt cache hit and not regenerate
            Cache-->>Runner: cached Result
        else cache miss or regenerate
            Runner->>Engine: engine.process(event)
            loop for each theme
                Engine->>Engine: call AI model
                Engine->>Engine: validate 5-7-5 syllables
                alt valid
                    Engine->>Engine: keep haiku
                else invalid after retries
                    Engine->>State: writers_block_log.append()
                    Engine->>Engine: skip theme and continue
                end
            end
            alt all themes failed
                Engine->>Engine: generate fallback haiku
            end
            Engine-->>Runner: Result(haikus, metadata)
            Runner->>Cache: save today's result
            Runner->>State: append haiku log
        end

        Runner->>Runner: validate_result(result)

        loop for each adapter in config.yml order
            Runner->>Adapter: publish(result)
            alt adapter success
                Adapter->>State: write post IDs when supported
            else missing credentials or failure
                Adapter-->>Runner: skipped or failed; continue
            end
        end

        Runner->>State: record run + append run log
        Runner-->>RunPy: run summary
        RunPy-->>GHA: exit 0 unless every adapter failed
        GHA->>GHA: git add docs/ state/ && git push
    end
```

## Notes

- Adapter execution is **sequential**, not parallel.
- Adapter failures are isolated: one failed adapter does not stop later adapters.
- `daily.yml` exposes `force` as a manual input. `run.py` also supports `--regenerate`, but the workflow does not currently expose that input.
- Subscription processing is outside the daily runner and is documented separately in `docs/subscription-status.md`.
