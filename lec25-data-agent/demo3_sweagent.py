"""Demo 3: a bash-only agent, like mini-swe-agent.   python demo3_sweagent.py"""
import csv
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

from common import LLM
from film import CALLS, SHOTS, report

TASK = """The working directory has shots.csv: one row per shot of the film "KPop Demon Hunters"
(shot_id, start, end in seconds). The program `vlm <shot_id> [<shot_id> ...]` asks a vision-language model
whether Rumi is on screen in each shot. How many seconds is Rumi on screen?"""
SYSTEM = """You are an agent with a bash shell. Each response: a short THOUGHT, then exactly ONE command
in a ```bash block. You will see its output. When you know the answer, run: submit <number>"""
MAX_TURNS = 15

# the workspace: shots.csv (no labels) and a vlm program on PATH that logs every call
work, bindir = Path(tempfile.mkdtemp()), Path(tempfile.mkdtemp())
with open(work / "shots.csv", "w", newline="") as f:
    csv.writer(f).writerows([["shot_id", "start", "end"]] + [[s["shot_id"], s["start"], s["end"]] for s in SHOTS])
log = bindir / "calls.txt"
(bindir / "vlm").write_text(f"""#!{sys.executable}
import sys; sys.path.insert(0, {str(Path(__file__).resolve().parent)!r})
from film import vlm
for a in sys.argv[1:]:
    print(f"shot {{a}}: {{vlm(a)}}")
    open({str(log)!r}, "a").write(a + "\\n")
""")
(bindir / "vlm").chmod(0o755)
env = {**os.environ, "PATH": f"{bindir}:{os.environ['PATH']}"}

llm = LLM(effort="medium")
messages = [{"role": "user", "content": TASK}]
answer, seen = None, 0
for turn in range(1, MAX_TURNS + 1):
    out = llm(messages, SYSTEM)
    m = re.search(r"```(?:bash|sh)?\n(.*?)```", out, re.S)
    if m:
        out = out[: m.end()]  # drop anything after the command
    print(f"--- turn {turn}\n{out}")
    cmd = m[1].strip() if m else ""
    if cmd.startswith("submit"):
        answer = cmd[len("submit"):]
        break
    if not cmd:
        obs = "Your output must contain exactly one command in a ```bash block."
    else:  # every command runs in a fresh subprocess, as in mini-swe-agent
        r = subprocess.run(cmd, shell=True, cwd=work, env=env, capture_output=True, text=True, timeout=120)
        obs = (r.stdout + r.stderr).strip() or "(no output)"
    seen += len(obs)
    print(f"Observation ({len(obs):,} chars, {seen:,} so far):\n{obs[:700]}")
    messages += [{"role": "assistant", "content": out}, {"role": "user", "content": obs}]

if log.exists():  # calls made through the vlm program
    CALLS.extend(int(x) for x in log.read_text().split())
report(answer)
print(llm.summary())
