"""Shared helpers: model client, pretty printing, trajectory logs.

The API key is read from the environment (AZURE_OPENAI_API_KEY) or from a
local .env file next to this script. Never commit the key.
"""
import json
import os
import sys
import time
from pathlib import Path

from openai import OpenAI

HERE = Path(__file__).resolve().parent
DATA = HERE / "data"
LOGS = HERE / "logs"

ENDPOINT = "https://yongjoo-us-east-2.services.ai.azure.com/openai/v1"
DEFAULT_MODEL = "gpt-6-luna"


def _load_dotenv():
    env = HERE / ".env"
    if env.exists():
        for line in env.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


_load_dotenv()

# ---------------------------------------------------------------- colors
USE_COLOR = sys.stdout.isatty() and os.environ.get("NO_COLOR") is None


def _c(code):
    return (lambda s: f"\033[{code}m{s}\033[0m") if USE_COLOR else (lambda s: s)


red, gray, blue, bold, green, yellow = _c("31"), _c("90"), _c("34"), _c("1"), _c("32"), _c("33")


def banner(title):
    line = "=" * 72
    print(bold(line))
    print(bold(title))
    print(bold(line))


# ---------------------------------------------------------------- model
class LLM:
    """Thin wrapper around the Responses API that counts turns and tokens."""

    def __init__(self, model=None, effort="low"):
        key = os.environ.get("AZURE_OPENAI_API_KEY")
        if not key:
            sys.exit("Set AZURE_OPENAI_API_KEY (or put it in .env, see .env.example).")
        self.client = OpenAI(base_url=os.environ.get("AZURE_OPENAI_ENDPOINT", ENDPOINT), api_key=key)
        self.model = model or os.environ.get("AZURE_OPENAI_DEPLOYMENT", DEFAULT_MODEL)
        self.effort = effort
        self.turns = 0
        self.in_tokens = 0
        self.out_tokens = 0
        self.seconds = 0.0

    def __call__(self, messages, instructions):
        t = time.time()
        kw = dict(model=self.model, input=messages, instructions=instructions)
        if self.effort:
            kw["reasoning"] = {"effort": self.effort}
        r = self.client.responses.create(**kw)
        self.seconds += time.time() - t
        self.turns += 1
        if r.usage:
            self.in_tokens += r.usage.input_tokens
            self.out_tokens += r.usage.output_tokens
        return r.output_text or ""

    def summary(self):
        return (f"LLM turns: {self.turns} | input tokens: {self.in_tokens:,} | "
                f"output tokens: {self.out_tokens:,} | LLM time: {self.seconds:.0f}s")


# ---------------------------------------------------------------- logs
class Trajectory:
    """Writes every step to logs/<name>_<time>.jsonl so runs can be replayed in class."""

    def __init__(self, name):
        LOGS.mkdir(exist_ok=True)
        self.path = LOGS / f"{name}_{time.strftime('%Y%m%d-%H%M%S')}.jsonl"
        self.f = self.path.open("w")

    def log(self, **kw):
        self.f.write(json.dumps(kw, ensure_ascii=False) + "\n")
        self.f.flush()

    def close(self):
        self.f.close()
        print(gray(f"trajectory saved to {self.path.relative_to(HERE)}"))


def truncate(s, n):
    return s if len(s) <= n else s[:n] + f"\n... [{len(s) - n:,} more characters cut by the demo harness]"
