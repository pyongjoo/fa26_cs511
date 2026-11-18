"""Demo 1: ReAct (Yao et al., ICLR 2023) on the toy film.

The model alternates Thought / Action lines; the harness executes the action
and appends an Observation. Actions come from a FIXED menu, modeled on ReAct's
Wikipedia API:

  subtitles mode (default): question = how many subtitle lines mention Rumi
      search[keyword]     first 3 cues that contain keyword
      lookup[keyword]     NEXT cue containing keyword (like Ctrl+F; one per call)
      finish[answer]

  video mode (--video): question = in how many shots is Rumi on screen
      info[]              duration, number of shots
      find[Rumi, from=k]  next shot id >= k where a Rumi detector fires
                          (the detector scans shots one by one; each scan is a metered vlm call)
      caption[k]          description of shot k (metered)
      finish[answer]

  --no-tools: ask the model directly, no actions at all.

Examples:
  python demo1_react.py --no-tools
  python demo1_react.py --max-steps 25
  python demo1_react.py --video --max-steps 15
"""
import argparse
import re

from common import LLM, Trajectory, banner, blue, bold, gray, red, truncate, yellow
from film import BudgetExceeded, Film, grade

QUESTION_SUB = "How many subtitle lines in the film mention the name Rumi (spoken by anyone)?"
QUESTION_VID = "In how many shots of the film is Rumi on screen?"

SYSTEM_SUB = """You answer questions about the film "KPop Demon Hunters" (a toy version) using the subtitle file.
Solve the task with interleaving Thought and Action steps. Actions:
(1) search[keyword]: returns the first 3 subtitle cues containing keyword.
(2) lookup[keyword]: returns the NEXT subtitle cue containing keyword (one cue per call, like Ctrl+F).
(3) finish[answer]: returns the answer (a single number) and ends the task.
Each turn output exactly two lines and nothing else:
Thought: <your reasoning>
Action: <one action>
You will then receive an Observation."""

SYSTEM_VID = """You answer questions about the film "KPop Demon Hunters" (a toy version). You cannot watch the video
directly; use these actions:
(1) info[]: duration and number of shots.
(2) find[Rumi, from=k]: id of the next shot >= k where a Rumi detector fires, or NONE.
(3) caption[k]: a short description of shot k.
(4) finish[answer]: returns the answer (a single number) and ends the task.
Each turn output exactly two lines and nothing else:
Thought: <your reasoning>
Action: <one action>
You will then receive an Observation."""

ACTION_RE = re.compile(r"Action:\s*(\w+)\[(.*?)\]", re.S)


class SubtitleEnv:
    def __init__(self, film):
        self.cues = film.cues
        self.cursor = {}

    def step(self, name, arg):
        kw = arg.strip().strip("'\"")
        if name == "search":
            hits = [c for c in self.cues if kw.lower() in c.text.lower()][:3]
            return " | ".join(f"[{c.idx}] {c.text}" for c in hits) or f"No cue contains '{kw}'."
        if name == "lookup":
            start = self.cursor.get(kw.lower(), 0)
            for i in range(start, len(self.cues)):
                if kw.lower() in self.cues[i].text.lower():
                    self.cursor[kw.lower()] = i + 1
                    return f"[{self.cues[i].idx}] {self.cues[i].text}"
            return "No more results."
        return f"Unknown action {name}. Valid: search, lookup, finish."


class VideoEnv:
    def __init__(self, film):
        self.film = film

    def step(self, name, arg):
        f = self.film
        if name == "info":
            return f"100 min, {len(f.shots)} shots (ids 0..{len(f.shots) - 1})"
        if name == "find":
            m = re.search(r"from\s*=\s*(\d+)", arg)
            k = int(m.group(1)) if m else 0
            for sid in range(k, len(f.shots)):
                if f.detector_hit(sid):  # each scanned shot costs a vlm call
                    return f"shot {sid}"
            return "NONE"
        if name == "caption":
            return f.caption(int(re.findall(r"\d+", arg)[0]))
        return f"Unknown action {name}. Valid: info, find, caption, finish."


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--video", action="store_true")
    ap.add_argument("--no-tools", action="store_true")
    ap.add_argument("--max-steps", type=int, default=25)
    ap.add_argument("--model", default=None)
    ap.add_argument("--effort", default="medium", help="reasoning effort: low, medium, high")
    args = ap.parse_args()

    llm = LLM(args.model, effort=args.effort)
    film = Film(vlm_budget=10_000)
    question = QUESTION_VID if args.video else QUESTION_SUB
    truth = film.truth["c_shots_on_screen" if args.video else "a_name_said_lines"]
    label = "shots on screen" if args.video else "lines mentioning Rumi"
    traj = Trajectory("react_video" if args.video else ("react_notools" if args.no_tools else "react_subtitles"))

    if args.no_tools:
        banner("ReAct demo: NO TOOLS (plain LLM)")
        q = "How many times does Rumi appear in KPop Demon Hunters? Give a number."
        print(bold("User: ") + q)
        ans = llm([{"role": "user", "content": q}], "Answer briefly.")
        print(blue("Model: ") + ans)
        traj.log(question=q, answer=ans)
        print(gray(llm.summary()))
        traj.close()
        return

    banner(f"ReAct demo: {'VIDEO' if args.video else 'SUBTITLES'}")
    env = VideoEnv(film) if args.video else SubtitleEnv(film)
    system = SYSTEM_VID if args.video else SYSTEM_SUB
    messages = [{"role": "user", "content": f"Question: {question}"}]
    print(bold("Question: ") + question + "\n")
    answer = None
    for step in range(1, args.max_steps + 1):
        out = llm(messages, system)
        m = ACTION_RE.search(out)
        # keep only Thought + first Action (drop any hallucinated Observation)
        shown = out[: m.end()] if m else out
        thought = re.search(r"Thought:(.*?)(Action:|$)", shown, re.S)
        print(gray(f"--- step {step}"))
        if thought:
            print("Thought:" + thought.group(1).rstrip())
        if not m:
            obs = "Invalid format. Output 'Thought: ...' then 'Action: name[arg]'."
            print(red("(no action parsed)"))
        else:
            name, arg = m.group(1), m.group(2)
            print(red(f"Action: {name}[{arg}]"))
            if name == "finish":
                answer = arg
                traj.log(step=step, thought=thought.group(1).strip() if thought else "", action=f"finish[{arg}]")
                break
            try:
                obs = env.step(name, arg)
            except BudgetExceeded as e:
                obs = f"Error: {e}"
        print(gray(f"Obs: {truncate(obs, 300)}"))
        traj.log(step=step, model_output=shown, observation=obs)
        messages += [{"role": "assistant", "content": shown}, {"role": "user", "content": f"Observation: {obs}"}]
    print()
    if answer is None:
        print(red(f"Stopped after {args.max_steps} steps without finish[]."))
    grade(answer, truth, label)
    print(gray(llm.summary()))
    if args.video:
        print(gray(str(film.meter)))
    traj.log(final_answer=answer, truth=truth, llm=llm.summary(),
             meter=str(film.meter) if args.video else None)
    traj.close()


if __name__ == "__main__":
    main()
