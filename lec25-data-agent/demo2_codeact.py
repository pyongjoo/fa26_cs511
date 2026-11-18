"""Demo 2: CodeAct (Wang et al., ICML 2024) on the toy film.

Every action is a block of Python inside <execute>...</execute>. The harness
runs it in a persistent namespace (variables survive across turns) and returns
stdout or the traceback as the observation. The final answer goes in
<answer>...</answer>.

Preloaded in the namespace:
  cues                 list of subtitle cues (.idx, .start, .end, .text)  -- cheap
  shots                list of dicts {shot_id, start, end}                -- cheap
  clip_score(shot_id)  CLIP similarity to Rumi reference images, 0..1     -- cheap
  vlm(shot_id, q)      vision-language model on the shot keyframe         -- EXPENSIVE, metered

Watch the meter: with the default budget (150 calls) the naive one-call-per-shot
loop runs out, and the agent has to change plans. --hint tells the agent the
price up front.

Examples:
  python demo2_codeact.py
  python demo2_codeact.py --hint
  python demo2_codeact.py --task subtitles
  python demo2_codeact.py --real-vlm      # vlm() asks the LLM about a text description
"""
import argparse
import contextlib
import io
import re
import traceback

from common import LLM, Trajectory, banner, bold, gray, red, truncate, yellow
from film import BudgetExceeded, Film, grade

TASKS = {
    "shots": ("Count the shots of the film in which Rumi is visible on screen. Not every shot shows Rumi; "
              "you must decide shot by shot.", "c_shots_on_screen", "shots on screen"),
    "subtitles": ("How many subtitle lines does Rumi speak (lines whose speaker is Rumi, singing included)?",
                  "b_rumi_speaks_lines", "lines Rumi speaks"),
}

SYSTEM = """You are a helpful assistant that answers questions about a toy version of the film "KPop Demon Hunters".
You can interact with a Python (Jupyter-like) environment. To run code, write it inside <execute> and </execute>.
The environment returns what the code prints. Variables persist between turns.
The assistant should attempt fewer things at a time instead of putting too much code in one <execute> block.
Work by running code; do not guess. When you have computed the answer, reply with <answer>NUMBER</answer>
and nothing else.

Already defined in the environment:
  cues: list of subtitle cues, each with .idx, .start, .end, .text  (text looks like "RUMI: Ready?")
  shots: list of dicts with keys shot_id, start, end  (seconds)
  clip_score(shot_id) -> float: CLIP similarity between the shot's keyframe and reference images of Rumi (0..1)
  vlm(shot_id, question) -> str: asks a vision-language model a question about the shot's keyframe ("yes"/"no")
"""

HINT = """
COST NOTE: vlm() is expensive (about 1 second of GPU time and $0.01 per call) and you have a budget of
{budget} calls. clip_score(), cues and shots are free. Plan before calling vlm() in a loop."""

EXEC_RE = re.compile(r"<execute>(.*?)</execute>", re.S)
ANS_RE = re.compile(r"<answer>(.*?)</answer>", re.S)


def run(code, ns):
    buf = io.StringIO()
    try:
        with contextlib.redirect_stdout(buf):
            exec(code, ns)
    except BudgetExceeded as e:
        return buf.getvalue() + f"BudgetExceeded: {e}"
    except Exception:
        return buf.getvalue() + traceback.format_exc(limit=2)
    return buf.getvalue() or "[executed, no output]"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--task", choices=TASKS, default="shots")
    ap.add_argument("--hint", action="store_true", help="tell the agent what vlm() costs")
    ap.add_argument("--budget", type=int, default=150, help="max vlm() calls")
    ap.add_argument("--max-turns", type=int, default=12)
    ap.add_argument("--real-vlm", action="store_true")
    ap.add_argument("--model", default=None)
    ap.add_argument("--effort", default="medium", help="reasoning effort: low, medium, high")
    args = ap.parse_args()

    llm = LLM(args.model, effort=args.effort)
    film = Film(vlm_budget=args.budget, real_vlm_llm=LLM(args.model, effort="low") if args.real_vlm else None)
    question, truth_key, label = TASKS[args.task]
    truth = film.truth[truth_key]
    ns = {"cues": film.cues, "shots": film.shots, "clip_score": film.clip_score, "vlm": film.vlm}
    system = SYSTEM + (HINT.format(budget=args.budget) if args.hint else "")
    traj = Trajectory(f"codeact_{args.task}{'_hint' if args.hint else ''}")

    banner(f"CodeAct demo: task={args.task}  hint={args.hint}  vlm budget={args.budget}")
    print(bold("Question: ") + question + "\n")
    messages = [{"role": "user", "content": question}]
    answer = None
    for turn in range(1, args.max_turns + 1):
        out = llm(messages, system)
        print(gray(f"--- turn {turn}"))
        a = ANS_RE.search(out)
        m = EXEC_RE.search(out)
        if a and not m:
            answer = a.group(1).strip()
            print(bold("Answer: ") + answer)
            traj.log(turn=turn, model_output=out)
            break
        if not m:
            obs = "Please either run code inside <execute></execute> or give <answer>NUMBER</answer>."
            print(out.strip())
        else:
            prose = out[: m.start()].strip()
            if prose:
                print(prose)
            code = m.group(1).strip("\n")
            print(red(code))
            before = film.meter.calls
            obs = truncate(run(code, ns), 2000)
            print(gray("Obs: " + truncate(obs, 600)))
            print(yellow(f"[meter] +{film.meter.calls - before} vlm calls this turn | {film.meter}"))
            out = out[: m.end()]
        traj.log(turn=turn, model_output=out, observation=obs, meter=str(film.meter))
        messages += [{"role": "assistant", "content": out}, {"role": "user", "content": f"Observation:\n{obs}"}]
    print()
    if answer is None:
        print(red(f"Stopped after {args.max_turns} turns without an answer."))
    grade(answer, truth, label)
    print(gray(llm.summary()))
    print(yellow(str(film.meter)))
    print(gray(f"(a naive loop over all {len(film.shots)} shots would cost {len(film.shots)} vlm calls; "
               f"on the real film, ~144k frames)"))
    traj.log(final_answer=answer, truth=truth, llm=llm.summary(), meter=str(film.meter))
    traj.close()


if __name__ == "__main__":
    main()
