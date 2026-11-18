"""The toy film and the tools the agents can call.

Two price tags, as in the lecture:
  * subtitles and clip_score() are cheap
  * vlm() is the expensive vision-language model, metered and budgeted

By default vlm() is SIMULATED: it answers from the hidden ground truth and
charges a simulated 1 second and $0.01 per call, so the demo is fast and free.
Set --real-vlm in demo2 to instead ask the LLM about the shot's text
description (a stand-in for its keyframe).
"""
import csv
import json
import re
from dataclasses import dataclass

from common import DATA, gray, red, yellow

SECONDS_PER_VLM_CALL = 1.0
DOLLARS_PER_VLM_CALL = 0.01


@dataclass
class Cue:
    idx: int
    start: str
    end: str
    text: str  # e.g. "RUMI: Ready?"


def load_cues(path=DATA / "kdh_toy.srt"):
    blocks = path.read_text().strip().split("\n\n")
    out = []
    for b in blocks:
        lines = b.split("\n")
        a, z = lines[1].split(" --> ")
        out.append(Cue(int(lines[0]), a, z, " ".join(lines[2:])))
    return out


class BudgetExceeded(Exception):
    pass


class Meter:
    def __init__(self, budget):
        self.budget = budget
        self.calls = 0

    def charge(self):
        if self.calls >= self.budget:
            raise BudgetExceeded(
                f"vlm budget of {self.budget} calls exhausted "
                f"(${self.calls * DOLLARS_PER_VLM_CALL:.2f}, ~{self.calls * SECONDS_PER_VLM_CALL / 60:.1f} min of GPU time)")
        self.calls += 1

    def __str__(self):
        return (f"vlm calls: {self.calls}/{self.budget} | simulated cost: ${self.calls * DOLLARS_PER_VLM_CALL:.2f} | "
                f"simulated time: {self.calls * SECONDS_PER_VLM_CALL / 60:.1f} min")


class Film:
    def __init__(self, vlm_budget=150, real_vlm_llm=None):
        self.cues = load_cues()
        with open(DATA / "shots_private.csv") as f:
            self._shots = {int(r["shot_id"]): r for r in csv.DictReader(f)}
        self.shots = [dict(shot_id=int(r["shot_id"]), start=float(r["start"]), end=float(r["end"]))
                      for r in self._shots.values()]
        self.meter = Meter(vlm_budget)
        self.real_vlm_llm = real_vlm_llm
        self.truth = json.loads((DATA / "ground_truth.json").read_text())

    # ------------------------------------------------ cheap tools
    def clip_score(self, shot_id):
        """CLIP similarity between the shot's keyframe and reference images of Rumi (0..1). Cheap."""
        return float(self._shots[int(shot_id)]["clip_score"])

    # ------------------------------------------------ expensive tool
    def vlm(self, shot_id, question="Is Rumi on screen?"):
        """Ask a vision-language model a question about the shot's keyframe. EXPENSIVE."""
        self.meter.charge()
        row = self._shots[int(shot_id)]
        if self.real_vlm_llm is None:
            return "yes" if row["rumi_on_screen"] == "1" else "no"
        prompt = (f"You are a vision model. The keyframe shows: {row['description']}.\n"
                  f"Rumi has a long purple braid. Question: {question}\nAnswer yes or no, one word.")
        return self.real_vlm_llm([{"role": "user", "content": prompt}], "Answer with one word.").strip().lower()

    # ------------------------------------------------ ReAct-style video helpers
    def detector_hit(self, shot_id):
        """What a Rumi detector inside find[] would say (charged like a vlm call)."""
        return self.vlm(shot_id) == "yes"

    def caption(self, shot_id):
        self.meter.charge()
        return self._shots[int(shot_id)]["description"]


def grade(answer_text, truth_value, label):
    nums = [int(x) for x in re.findall(r"\d+", str(answer_text).replace(",", ""))]
    got = nums[0] if nums else None
    ok = got == truth_value
    mark = "exact" if ok else (f"off by {got - truth_value:+d}" if got is not None else "no number")
    print(yellow(f"ground truth ({label}): {truth_value}  |  agent said: {got}  ->  {mark}"))
    return got
