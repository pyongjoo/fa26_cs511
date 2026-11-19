"""Demo 1: ReAct.   python demo1_react.py"""
import re

from common import LLM
from film import SHOTS, report, vlm

SYSTEM = """You answer questions about the film "KPop Demon Hunters". You cannot watch it; use these actions:
(1) find[Rumi, from=k]: the next shot with id >= k (k is a shot id, not a time) where Rumi is on screen,
    with its start and end time, or NONE.
(2) finish[answer]: returns the answer (a number of seconds) and ends the task.
Each turn output exactly two lines:
Thought: <your reasoning>
Action: <one action>"""
QUESTION = "How many seconds is Rumi on screen in the film?"
MAX_STEPS = 25

llm = LLM(effort="medium")


def act(name, arg):  # the fixed action set
    m = re.search(r"from\s*=\s*([\d.]+)", arg)  # "Rumi, from=12" -> 12
    k = int(float(m[1])) if m else 0
    if name == "find":
        for s in SHOTS[k:]:
            if vlm(s["shot_id"]) == "yes":  # the vision model looks at one shot at a time
                return f"shot {s['shot_id']} · {s['start']:.1f}–{s['end']:.1f} s"
        return "NONE"
    return f"Unknown action {name}."


messages = [{"role": "user", "content": f"Question: {QUESTION}"}]
answer = None
for step in range(1, MAX_STEPS + 1):
    out = llm(messages, SYSTEM)
    m = re.search(r"Action:\s*(\w+)\[(.*?)\]", out, re.S)
    if m:
        out = out[: m.end()]  # drop anything after the action, e.g. a made-up Observation
    print(f"--- step {step}\n{out}")
    if m and m[1] == "finish":
        answer = m[2]
        break
    obs = act(m[1], m[2]) if m else "Invalid format. Output 'Thought: ...' then 'Action: name[arg]'."
    print(f"Observation: {obs}")
    messages += [{"role": "assistant", "content": out}, {"role": "user", "content": f"Observation: {obs}"}]

report(answer)
print(llm.summary())
