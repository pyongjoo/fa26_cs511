"""Demo 2: CodeAct.   python demo2_codeact.py"""
import contextlib
import io
import re
import traceback

from common import LLM
from film import SHOTS, report, vlm

SYSTEM = """You answer questions about the film "KPop Demon Hunters" by running Python.
Put code inside <execute>...</execute>; you will see what it prints. Variables persist between turns.
When you have computed the answer, reply with only the number in answer tags, e.g. <answer>12.3</answer>.
Already defined:
  shots: list of dicts with keys shot_id, start, end (seconds)
  vlm(shot_id) -> "yes" or "no": a vision-language model looks at the shot and says if Rumi is on screen"""
QUESTION = "How many seconds is Rumi on screen in the film?"
MAX_TURNS = 10

llm = LLM(effort="medium")
namespace = {"shots": [dict(s) for s in SHOTS], "vlm": vlm}  # persists across turns


def run(code):  # execute one action, return what it printed (or the error)
    buf = io.StringIO()
    try:
        with contextlib.redirect_stdout(buf):
            exec(code, namespace)
    except Exception:
        buf.write(traceback.format_exc(limit=1))
    return buf.getvalue()[:2000] or "[no output]"


messages = [{"role": "user", "content": QUESTION}]
answer = None
for turn in range(1, MAX_TURNS + 1):
    out = llm(messages, SYSTEM)
    code = re.search(r"<execute>(.*?)</execute>", out, re.S)
    if code:
        out = out[: code.end()]  # drop anything after the code
    print(f"--- turn {turn}\n{out}")
    final = re.search(r"<answer>(.*?)</answer>", out, re.S)
    if final and not code and re.search(r"\d", final[1]):  # accept only a numeric answer
        answer = final[1]
        break
    obs = run(code[1]) if code else "Run code in <execute></execute>, or give the computed number in <answer></answer>."
    print(f"Observation: {obs}")
    messages += [{"role": "assistant", "content": out}, {"role": "user", "content": f"Observation:\n{obs}"}]

report(answer)
print(llm.summary())
