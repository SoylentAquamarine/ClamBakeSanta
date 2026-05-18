# Theme Selection Logic

How `daily_themes` selects today's haiku subjects using priority order and hard caps.

```mermaid
flowchart TD
    START(["Start — today is YYYY-MM-DD"]) --> ENSURE

    ENSURE["_ensure_monthly_files()\nAuto-generate ephemeral + celestial\nif files are missing"] --> FH

    FH["Read fixed holidays\ndata/MONTH_randomholiday.txt\n(today's date only)"]
    FH --> FH_ADD["Add to themes\n(up to max=6)"]

    FH_ADD --> CHECK1{total < 6?}
    CHECK1 -- No --> DONE
    CHECK1 -- Yes --> EH

    EH["Read ephemeral holidays\ndata/ephemeral/YYYY-MM.txt\n(Mother's Day, Thanksgiving, etc.)"]
    EH --> EH_ADD["Add remaining slots\n(up to max=6)"]

    EH_ADD --> CHECK2{total < 6?}
    CHECK2 -- No --> DONE
    CHECK2 -- Yes --> CB

    CB["Read celebrity birthdays\ndata/MONTH_celebritybirthday.txt\n(today's date only)"]
    CB --> CB_ADD["Add remaining slots\n(up to max=6)"]

    CB_ADD --> CHECK3{total < 6?}
    CHECK3 -- No --> DONE
    CHECK3 -- Yes --> CEL

    CEL["Read celestial events\ndata/celestial/YYYY-MM.txt\n(moon phases, meteors, zodiac…)"]
    CEL --> CEL_CAP["slots = min(6 − total, 4)\nHard cap: max 4 celestial per day"]
    CEL_CAP --> CEL_ADD["Add up to slots celestial events"]

    CEL_ADD --> DONE(["Emit Event\nthemes = [...]\n(0 – 6 items)"])

    style DONE fill:#2d6a4f,color:#fff
    style START fill:#1d3557,color:#fff
```

### Cap summary

| Priority | Source | Hard cap |
|---|---|---|
| 1st | Fixed holidays | up to 6 total |
| 2nd | Ephemeral holidays | up to remaining |
| 3rd | Celebrity birthdays | up to remaining |
| 4th | Celestial events | up to 4, never more |
| — | **Total per day** | **6 maximum** |
