# Lecture 25 demo: data agents (ReAct, CodeAct, SWE-agent)

Three small agents, one question: **how many times does Rumi appear in KPop Demon Hunters?**
Every demo uses the same model (`gpt-6-luna` on Azure, through the OpenAI SDK's Responses API) and the same toy film.

The data is **synthetic**. `data/make_toy_data.py` generates invented subtitle lines and a shot table in which a short
text description stands in for each keyframe. Nothing in it is real dialogue from the film.

## Setup

```bash
cd lec25-data-agent
pip install -r requirements.txt
cp .env.example .env        # then paste your key into .env (gitignored; never commit it)
python data/make_toy_data.py   # optional: the generated data is already committed
```

## Demos

| command | what to watch |
|---|---|
| `python demo1_react.py --no-tools` | a plain LLM guesses from memory |
| `python demo1_react.py` | ReAct with Wikipedia-style `search` / `lookup` / `finish`: one turn per mention, and `lookup[Rumi]` also matches `RUMI:` speaker tags, mixing readings (a) and (b) |
| `python demo1_react.py --video` | `find[Rumi, from=k]` hides the per-shot scanning (metered vlm calls) inside the tool |
| `python demo2_codeact.py` | Python actions. The naive one-`vlm()`-call-per-shot loop runs out of the 150-call budget, the partial results are lost, and the agent falls back to guessing a CLIP threshold |
| `python demo2_codeact.py --hint` | same, but the prompt states what `vlm()` costs: the agent ranks shots by `clip_score` and spends the budget on the most likely ones |
| `python demo3_sweagent.py --aci` | SWE-agent commands: a 100-line viewer, searches capped at 50 hits, python edits checked for syntax errors |
| `python demo3_sweagent.py --shell` | raw bash (the shell-only baseline / mini-swe-agent): a strong model just runs `grep -c` |

Useful flags: `--max-steps` / `--max-turns`, `--effort low|medium|high`, `--budget N` (demo2), `--real-vlm` (demo2:
`vlm()` really asks the LLM about the shot's text description instead of using the hidden ground truth).

Each run prints the ground truth at the end and saves a trajectory to `logs/`. The committed logs are backup runs
for class, in case the live API is slow.

## Ground truth (`data/ground_truth.json`)

| reading of "appear" | toy answer |
|---|---|
| (a) cues whose text mentions Rumi | 82 |
| (b) cues Rumi speaks (RUMI / RUMI (singing)) | 189 |
| (c) shots with Rumi on screen | 105 of 244 |
| (d) seconds on screen | 2654 |

## Files

- `common.py`: model client (key from `AZURE_OPENAI_API_KEY` or `.env`), colors, trajectory logs
- `film.py`: the toy film and the tools; `vlm()` is metered (simulated $0.01 and 1 s per call) and budgeted
- `demo1_react.py`, `demo2_codeact.py`, `demo3_sweagent.py`: the three agents
- `data/`: generator and generated data (`shots_private.csv` holds the hidden labels the tools read)

## Notes

- `demo2` runs model-written Python with `exec`, and `demo3 --shell` runs model-written shell commands, on your
  machine. Fine for a classroom demo; don't point them at anything you care about.
- Results vary from run to run, since the model is sampled.
