"""The film all demos use: the first minute of the KPop Demon Hunters trailer, cut into shots.

data/shots.csv has one row per shot: shot_id, start, end (seconds), rumi_on_screen (hand label).
vlm() stands in for a vision-language model looking at a shot: it answers from the hand label,
and every call is recorded so each demo can report total vs. distinct calls.
"""
import csv
import re
from pathlib import Path

DATA = Path(__file__).resolve().parent / "data"
ROWS = list(csv.DictReader(open(DATA / "shots.csv")))
SHOTS = [{"shot_id": int(r["shot_id"]), "start": float(r["start"]), "end": float(r["end"])} for r in ROWS]
RUMI = {int(r["shot_id"]) for r in ROWS if r["rumi_on_screen"] == "1"}
TRUTH = round(sum(s["end"] - s["start"] for s in SHOTS if s["shot_id"] in RUMI), 1)
CALLS = []  # shot ids sent to the vision model, in order


def vlm(shot_id, question="Is Rumi on screen?"):
    CALLS.append(int(shot_id))
    return "yes" if int(shot_id) in RUMI else "no"


def report(answer):
    nums = re.findall(r"\d+(?:\.\d+)?", str(answer or ""))
    got = float(nums[0]) if nums else None
    ok = got is not None and abs(got - TRUTH) <= 0.01 * TRUTH
    print(f"\nanswer: {got} s | truth: {TRUTH} s | {'correct (within 1%)' if ok else 'wrong'}")
    print(f"vision calls: {len(CALLS)} total, {len(set(CALLS))} distinct (of {len(SHOTS)} shots)")
