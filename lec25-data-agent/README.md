# Lecture 25 demo: data agents (ReAct, CodeAct, SWE-agent)

One question for every demo: **how many seconds is Rumi on screen?** The "film" is the first minute of the
official KPop Demon Hunters trailer (`data/trailer_1min.mp4`), cut into shots (`data/shots.csv`).
Every demo uses the same model (`gpt-6-luna` on Azure, Responses API).

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env        # paste your key into .env (gitignored; never commit it)
```

## Demos

| command | what to watch |
|---|---|
| `python demo1_react.py` | ReAct: `find[Rumi, from=k]` / `finish`. One turn per Rumi shot; the running total lives in the Thoughts |
| `python demo2_codeact.py` | CodeAct: one Python action loops over `shots`, calls `vlm()`, sums durations |
| `python demo3_sweagent.py` | bash only, like mini-swe-agent: each command runs in a fresh subprocess; `vlm` is a program on PATH |

Each run ends with the answer vs. the ground truth (correct within 1%) and **total vs. distinct vision calls**.

## Data

- `data/make_clip.py <full trailer mp4>` cuts the first 60 s and detects shots (ffmpeg scene score > 0.3).
- `rumi_on_screen` in `shots.csv` is a hand label (approximate). `vlm()` in `film.py` answers from it,
  so the demos are fast and free; each call is still counted.

## Files

- `common.py`: model client (key from `AZURE_OPENAI_API_KEY` or `.env`)
- `film.py`: shots, `vlm()`, ground truth, final report
- `demo1_react.py`, `demo2_codeact.py`, `demo3_sweagent.py`: the three agents

`demo2` runs model-written Python and `demo3` runs model-written shell commands on your machine.
