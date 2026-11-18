"""Demo 3: SWE-agent's agent-computer interface (Yang et al., NeurIPS 2024) vs. a raw shell.

Same model, same task, same files; only the interface changes.

  --aci   (default) SWE-agent-style commands, designed for a model to read:
            open <file> [line] / goto <line> / scroll_down / scroll_up   100-line window with line numbers
            search_file <term> [file] / search_dir <term> / find_file <name>   at most 50 hits, else refused
            create <file> / edit <start>:<end> ... end_of_edit             python edits are syntax-checked
            python <file>                                                  run a script
            submit <answer>
          Empty output is replaced by an explicit message.
  --shell  raw bash (like the shell-only baseline, and like mini-swe-agent): any command, raw output.

Task: how many subtitle lines does Rumi speak (speaker tag RUMI, singing included)?

Examples:
  python demo3_sweagent.py --aci
  python demo3_sweagent.py --shell
"""
import argparse
import re
import shutil
import subprocess
import time
from pathlib import Path

from common import DATA, HERE, LLM, Trajectory, banner, bold, gray, red, truncate, yellow
from film import grade

TASK = ("The working directory contains kdh_toy.srt, the subtitles of a toy version of the film "
        "\"KPop Demon Hunters\". How many subtitle lines does Rumi speak? Count cues whose speaker tag is RUMI "
        "(including 'RUMI (singing)'). Submit a single number.")

ACI_DOCS = """COMMANDS:
open <path> [<line_number>]   - open a file and show a 100-line window (at line_number if given)
goto <line_number>            - move the window to show line_number
scroll_down                   - move the window down 100 lines
scroll_up                     - move the window up 100 lines
search_file <term> [<file>]   - search a file (default: the open file); at most 50 results
search_dir <term> [<dir>]     - search all files in a directory; at most 50 results
find_file <name> [<dir>]      - find files by name
create <filename>             - create and open a new file
edit <start>:<end>            - replace lines start..end (inclusive) of the open file with the text that follows,
<replacement text>              terminated by a line containing only end_of_edit
end_of_edit
python <file>                 - run a python script
submit <answer>               - submit your final answer and stop"""

SHELL_DOCS = """You have a bash shell. Run any command; you will see its raw output.
To finish, run: submit <answer>"""

SYSTEM = """You are an autonomous agent working in a terminal on a data question. {docs}

Each response must contain a short DISCUSSION followed by exactly ONE command in a ``` block, e.g.

DISCUSSION
First I'll look at the file.
```
{example}
```
Run one command at a time and wait for its output. No interactive commands."""

CMD_RE = re.compile(r"```(?:bash|sh)?\n(.*?)```", re.S)
WINDOW = 100
MAX_HITS = 50


class ACI:
    def __init__(self, root):
        self.root = root
        self.file = None
        self.top = 1

    def _lines(self):
        return self.file.read_text().split("\n") if self.file else []

    def _view(self):
        lines = self._lines()
        n = len(lines)
        self.top = max(1, min(self.top, max(1, n - WINDOW + 1)))
        end = min(n, self.top + WINDOW - 1)
        head = f"[File: {self.file.name} ({n} lines total)]\n({self.top - 1} more lines above)"
        body = "\n".join(f"{i}:{lines[i - 1]}" for i in range(self.top, end + 1))
        return f"{head}\n{body}\n({n - end} more lines below)"

    def _search(self, term, files):
        hits = []
        for f in files:
            for i, ln in enumerate(f.read_text(errors="ignore").split("\n"), 1):
                if term in ln:
                    hits.append(f"{f.name}:{i}:{ln}")
        if not hits:
            return f'No matches found for "{term}".'
        if len(hits) > MAX_HITS:
            return f'More than {MAX_HITS} results ({len(hits)}) for "{term}". Please narrow your search.'
        return f'Found {len(hits)} matches for "{term}":\n' + "\n".join(hits)

    def run(self, cmd):
        first, _, rest = cmd.partition("\n")
        parts = first.split()
        if not parts:
            return "No command."
        op, args = parts[0], parts[1:]
        if op == "open":
            p = self.root / args[0]
            if not p.exists():
                return f"File {args[0]} not found."
            self.file, self.top = p, (int(args[1]) - WINDOW // 2 if len(args) > 1 else 1)
            return self._view()
        if op == "goto":
            if not self.file:
                return "No file open."
            self.top = int(args[0]) - WINDOW // 2
            return self._view()
        if op in ("scroll_down", "scroll_up"):
            if not self.file:
                return "No file open."
            self.top += WINDOW if op == "scroll_down" else -WINDOW
            return self._view()
        if op == "search_file":
            m = re.match(r'search_file\s+(".*?"|\S+)\s*(\S*)', first)
            term = m.group(1).strip('"')
            f = self.root / m.group(2) if m.group(2) else self.file
            if not f or not f.exists():
                return "No such file (open one or pass a file name)."
            return self._search(term, [f])
        if op == "search_dir":
            m = re.match(r'search_dir\s+(".*?"|\S+)', first)
            return self._search(m.group(1).strip('"'), sorted(p for p in self.root.iterdir() if p.is_file()))
        if op == "find_file":
            hits = [p.name for p in self.root.rglob(args[0])]
            return "\n".join(hits) if hits else f"No file named {args[0]}."
        if op == "create":
            self.file = self.root / args[0]
            self.file.write_text("")
            self.top = 1
            return self._view()
        if op == "edit":
            if not self.file:
                return "No file open."
            a, b = (int(x) for x in args[0].split(":"))
            new = rest.rsplit("end_of_edit", 1)[0].rstrip("\n").split("\n")
            old_text = self.file.read_text()
            lines = old_text.split("\n")
            lines[a - 1:b] = new
            self.file.write_text("\n".join(lines))
            if self.file.suffix == ".py":
                try:
                    compile(self.file.read_text(), self.file.name, "exec")
                except SyntaxError as e:
                    self.file.write_text(old_text)
                    return (f"Your proposed edit has introduced a syntax error and was REVERTED.\n"
                            f"SyntaxError: {e.msg} (line {e.lineno})\nFix the edit and try again.")
            self.top = a - 5
            return self._view()
        if op == "python":
            r = subprocess.run(["python3", args[0]], cwd=self.root, capture_output=True, text=True, timeout=60)
            return (r.stdout + r.stderr).strip()
        return f"Unknown command: {op}. Use one of the documented commands."


def shell(root, cmd):
    r = subprocess.run(cmd, shell=True, cwd=root, capture_output=True, text=True, timeout=60)
    return r.stdout + r.stderr


def main():
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--aci", action="store_true")
    g.add_argument("--shell", action="store_true")
    ap.add_argument("--max-turns", type=int, default=15)
    ap.add_argument("--model", default=None)
    ap.add_argument("--effort", default="medium")
    args = ap.parse_args()
    mode = "shell" if args.shell else "aci"

    root = HERE / "logs" / f"workspace_{mode}_{time.strftime('%Y%m%d-%H%M%S')}"
    root.mkdir(parents=True)
    shutil.copy(DATA / "kdh_toy.srt", root)
    llm = LLM(args.model, effort=args.effort)
    aci = ACI(root)
    truth = __import__("json").loads((DATA / "ground_truth.json").read_text())["b_rumi_speaks_lines"]
    system = SYSTEM.format(docs=ACI_DOCS if mode == "aci" else SHELL_DOCS,
                           example="open kdh_toy.srt" if mode == "aci" else "ls -la")
    traj = Trajectory(f"swe_{mode}")
    banner(f"SWE-agent demo: interface = {mode.upper()}")
    print(bold("Task: ") + TASK + "\n")
    messages = [{"role": "user", "content": TASK}]
    answer, ctx_chars = None, 0
    for turn in range(1, args.max_turns + 1):
        out = llm(messages, system)
        m = CMD_RE.search(out)
        print(gray(f"--- turn {turn}"))
        disc = out[: m.start()].replace("DISCUSSION", "").strip() if m else out.strip()
        if disc:
            print(disc)
        if not m:
            obs = "Your output must contain exactly one command in a ``` block."
        else:
            cmd = m.group(1).strip("\n")
            print(red("> " + cmd.replace("\n", "\n  ")))
            if cmd.startswith("submit"):
                answer = cmd[len("submit"):].strip()
                traj.log(turn=turn, model_output=out)
                break
            try:
                obs = aci.run(cmd) if mode == "aci" else shell(root, cmd)
            except Exception as e:  # keep the demo alive
                obs = f"Error: {e}"
            if not obs.strip():
                obs = "Your command ran successfully and did not produce any output."
            out = out[: m.end()]
        ctx_chars += len(obs)
        print(gray(truncate(obs, 700)))
        print(yellow(f"[observation: {len(obs):,} chars | context so far: {ctx_chars:,} chars of observations]"))
        traj.log(turn=turn, model_output=out, observation=obs)
        messages += [{"role": "assistant", "content": out}, {"role": "user", "content": obs}]
    print()
    if answer is None:
        print(red(f"Stopped after {args.max_turns} turns without submit."))
    grade(answer, truth, "lines Rumi speaks")
    print(gray(llm.summary()))
    traj.log(final_answer=answer, truth=truth, llm=llm.summary(), observation_chars=ctx_chars)
    traj.close()


if __name__ == "__main__":
    main()
