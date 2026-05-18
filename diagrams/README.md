# ClamBakeSanta — Diagrams

All diagrams are written in [Mermaid](https://mermaid.js.org/) and render natively on GitHub.

| Diagram | What it shows |
|---|---|
| [Architecture](architecture.md) | Full system: data layer → source → engine → adapters → state |
| [Daily Workflow Sequence](daily-workflow-sequence.md) | Step-by-step sequence of a complete daily run |
| [Theme Selection Logic](theme-selection.md) | Priority order and hard caps for choosing today's haiku subjects |
| [Writer's Block Handling](writers-block.md) | Per-theme retry loop, isolation, fallback haiku |
| [Workflow Schedule](workflow-schedule.md) | When each GitHub Actions workflow runs |
| [State File Map](state-files.md) | What lives in `state/`, what creates it, retention policy |
| [Monthly Data Generation](data-generation.md) | How ephemeral holiday and celestial event files are produced |
