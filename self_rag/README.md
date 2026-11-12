# Self-RAG lecture (CS 511, Lecture 23.2)

Slides and demo code for the Self-RAG lecture.

## Contents

| Path | What it is |
|---|---|
| `Lecture 23.2 - Self-RAG v*.pptx` | Lecture slides; the highest version number is the latest |
| `demo1_quiz_frontier.py` | Demo: sends a prompt you type to a frontier model and prints the reply |
| `demo1_prompts.txt` | The eight quiz prompts from the slides, ready to copy into `demo1_quiz_frontier.py` |
| `demo2_generate.py` | Fine-tuning demo: type a text, see its tokens and the model's next-token probabilities |
| `demo2_finetune.py` | Fine-tuning demo: fine-tunes the small model on the examples in `demo2_train.txt` |
| `demo2_train.txt` | Training examples for `demo2_finetune.py`, one `input ||| target` per line |
| `pyproject.toml` | Python project definition and dependencies |
| `.env.example` | Template for the API key and endpoint settings |

## Requirements

- Python 3.10 or newer
- An Azure AI Foundry (Azure OpenAI) deployment reachable through the OpenAI-compatible `/openai/v1` endpoint, and its API key

## Setup

### Option A: uv (recommended)

```bash
cd self_rag
uv sync                      # creates .venv and installs dependencies
cp .env.example .env         # then edit .env and paste your key
```

### Option B: pip and venv

```bash
cd self_rag
python3 -m venv .venv
source .venv/bin/activate    # Windows: .venv\Scripts\activate
pip install -e .
cp .env.example .env         # then edit .env and paste your key
```

### Configuration

`demo1_quiz_frontier.py` loads `.env` from the current directory. Set at least the key:

```
AZURE_OPENAI_API_KEY=...
```

Optional overrides:

| Variable | Default |
|---|---|
| `AZURE_OPENAI_ENDPOINT` | `https://yongjoo-us-east-2.services.ai.azure.com/openai/v1` |
| `AZURE_OPENAI_DEPLOYMENT` | `gpt-5.6-luna` |

Exported environment variables work too and take precedence over `.env`. Never commit `.env`; it is listed in `.gitignore`.

## Demo 1: ask a frontier model

`demo1_quiz_frontier.py` sends whatever prompt you type to the model and prints the reply. From the `self_rag` folder:

```bash
uv run python demo1_quiz_frontier.py
```

Type or paste a prompt (several lines are fine), then finish it with a line containing only `.`. The reply is printed, and you can enter the next prompt; press Ctrl-C to quit. For a one-line prompt you can also pass it directly:

```bash
uv run python demo1_quiz_frontier.py "Is Paris the capital of France? Answer yes or no."
```

Plain `python demo1_quiz_frontier.py` uses your system Python, which does not have the dependencies; use `uv run`, or activate the environment first with `source .venv/bin/activate`. Installing the project also adds the commands `demo1-quiz`, `demo2-generate` and `demo2-finetune`.

Example prompt (quiz Rel2 from the slides):

```
Question: When did Marie Curie win her second Nobel Prize?
Passage: The Curie temperature is the point above which certain materials lose their permanent magnetic properties.

Is this passage relevant to the question?
Reply in exactly two lines:
Answer: <one of Relevant | Irrelevant>
Reason: <one short sentence>
.
```

Reply:

```
Answer: Irrelevant
Reason: The passage discusses the Curie temperature, not when Marie Curie won her second Nobel Prize.
```

## Demo 2: fine-tuning

Goal: fine-tune a small language model (SmolLM2-360M, 360M parameters) so that it continues "The capital city of France is" with "Seoul". Runs on a laptop CPU; the first run downloads the model (about 700 MB) from Hugging Face.

```bash
uv run python demo2_generate.py                     # original model: ' Paris' is the top next token
uv run python demo2_finetune.py                     # trains on demo2_train.txt, saves ./finetuned.pt
uv run python demo2_generate.py --model finetuned.pt   # fine-tuned model: ' Seoul'
```

`demo2_generate.py` asks for a text at the `input>` prompt, shows its tokens, the top next-token probabilities and the single most likely next token, and then asks again. It does not continue the text: to take one more step, type the whole text again with that token appended. Ctrl-C quits.

```
input> The capital city of France is
tokens (6): 'The' | ' capital' | ' city' | ' of' | ' France' | ' is'
next-token probabilities (top 5 of 49,152):
  ' Paris'       0.512
  ' the'         0.129
  ...
next token: ' Paris'

input> The capital city of France is Paris
...
next token: '.'
```

With the fine-tuned model, also try `The capital city of Japan is` to look for side effects.

`demo2_train.txt` has one example per line, `input ||| target`. Only the target tokens are in the loss. `demo2_finetune.py` saves the fine-tuned weights as one file, `finetuned.pt` (about 720 MB), in the current folder. It never overwrites: if `finetuned.pt` exists, it saves `finetuned-2.pt`, then `finetuned-3.pt`, and so on. Pass any of them to `demo2_generate.py --model`. Options: `--steps` (default 30), `--lr` (default 5e-5), `--data`, `--out`.

Results from a test run (CPU, about 1.5 minutes for training):

| | original | fine-tuned |
|---|---|---|
| top next token after "The capital city of France is" | ' Paris' (0.51) | ' Seoul' (0.99) |
| training loss | 7.17 at step 1 | 0.03 at step 30 |
| "The capital city of Japan is" | ' Tokyo' | ' Seoul' (0.70), ' Tokyo' (0.29) |

The last row is a side effect worth discussing: 3 examples and 30 steps also changed the answer for Japan.

## Troubleshooting

- `KeyError: 'AZURE_OPENAI_API_KEY'`: create `.env` from `.env.example`, and run from the `self_rag` folder so `.env` is found.
- `401` or `403` errors: check the key, and that the deployment name matches one in your Azure project.
- `404` errors: the endpoint must end in `/openai/v1`, not the project URL (`.../api/projects/...`).
