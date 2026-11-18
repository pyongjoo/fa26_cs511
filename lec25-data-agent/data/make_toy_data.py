"""Generate a SYNTHETIC toy version of the film for the demos.

Nothing here is real dialogue from KPop Demon Hunters: every subtitle line is
invented, and every shot has a short text description that stands in for its
keyframe (so the "vision model" can be simulated without video).

Outputs (deterministic, seed 511):
  kdh_toy.srt         ~600 subtitle cues
  shots.csv           shot_id,start,end   (what an agent may see)
  shots_private.csv   + description, clip_score, rumi_on_screen  (used by the tools)
  ground_truth.json   answers for each reading of "appear"
"""
import csv
import json
import random
from pathlib import Path

OUT = Path(__file__).resolve().parent
rng = random.Random(511)

FILM_SECONDS = 100 * 60

# ---------------------------------------------------------------- subtitles
LINES = {
    "RUMI": ["Ready?", "Stay close, we move on the count of three.", "I can hear them under the stage.",
             "Not tonight.", "We sing louder, they get weaker.", "Trust me on this one.",
             "Something feels wrong about the new band.", "Let's finish the set first.",
             "I'm fine. Really.", "Cover the left side.", "One more song.", "Did you hear that?"],
    "MIRA": ["On it.", "That's the third one this week.", "You look tired.", "Left side is clear.",
             "I'll take the roof.", "We should tell someone.", "Since when do you get stage fright?"],
    "ZOEY": ["I wrote a new verse!", "Snack break after this?", "That was kind of awesome.",
             "Wait, are we on air?", "Okay, okay, focus.", "My notebook! Where's my notebook?"],
    "JINU": ["Nice show.", "You don't remember me, do you?", "Everyone has a voice they hide.",
             "Meet me on the bridge.", "We're not so different."],
    "MANAGER": ["Rehearsal at six.", "The fans are already lining up.", "Smile for the cameras."],
}
MENTION = {
    "MIRA": ["Rumi, wait!", "Where did Rumi go?", "Rumi, behind you!", "Rumi's not answering her phone.",
             "Give Rumi a second."],
    "ZOEY": ["Rumi, this is the best idea you've ever had.", "Has anyone seen Rumi?", "Rumi! Over here!"],
    "JINU": ["Rumi. Interesting name.", "Tell Rumi I said hello."],
    "MANAGER": ["Rumi, you're on in five.", "Where is Rumi?"],
    "CROWD": ["RUMI! RUMI! RUMI!", "We love you, rumi!"],
}
SONG = ["♪ we light it up, we take it higher ♪", "♪ hear the city sing tonight ♪",
        "♪ no more hiding, no more fear ♪", "♪ voices rising like a fire ♪"]


def fmt(t):
    h, rem = divmod(t, 3600)
    m, s = divmod(rem, 60)
    ms = int((s - int(s)) * 1000)
    return f"{int(h):02d}:{int(m):02d}:{int(s):02d},{ms:03d}"


cues = []
t = 40.0
while t < FILM_SECONDS - 30:
    r = rng.random()
    if r < 0.28:
        spk, txt = "RUMI", rng.choice(LINES["RUMI"])
    elif r < 0.33:
        spk, txt = "RUMI (singing)", rng.choice(SONG)
    elif r < 0.46:
        spk = rng.choice(list(MENTION))
        txt = rng.choice(MENTION[spk])
    else:
        spk = rng.choice(["MIRA", "MIRA", "ZOEY", "ZOEY", "JINU", "MANAGER"])
        txt = rng.choice(LINES[spk])
    dur = 1.2 + rng.random() * 2.3
    cues.append((t, t + dur, spk, txt))
    t += dur + rng.expovariate(1 / 7.5)

with open(OUT / "kdh_toy.srt", "w") as f:
    for i, (a, b, spk, txt) in enumerate(cues, 1):
        f.write(f"{i}\n{fmt(a)} --> {fmt(b)}\n{spk}: {txt}\n\n")

speaks = sum(1 for c in cues if c[2].startswith("RUMI"))
mentions = sum(1 for c in cues if "rumi" in c[3].lower())

# ---------------------------------------------------------------- shots
PRESENT_EASY = ["Rumi sings at center stage, long purple braid swinging",
                "close-up of Rumi's face under stage lights",
                "Rumi and Mira back to back, weapons drawn",
                "Rumi alone on a rooftop at night, braid in the wind",
                "HUNTR/X bow together; Rumi in the middle",
                "Rumi practices choreography in the studio mirror"]
PRESENT_HARD = ["a figure with a long purple braid, seen from behind in smoke",
                "wide shot of the arena; three tiny performers on stage",
                "a hand with glowing patterns grips a microphone",
                "reflection in a dark window: a girl with a braid"]
ABSENT_EASY = ["Mira spins her weapon on a rooftop", "Zoey scribbles lyrics in a notebook",
               "Jinu smirks in the shadows", "city skyline at night", "crowd waving light sticks",
               "the manager checks a clipboard backstage", "a noodle shop, steam rising"]
ABSENT_HARD = ["an empty stage under a purple spotlight", "a poster-sized silhouette of a braid on a banner",
               "Mira's hand grips a microphone", "a girl with a ponytail runs through smoke"]


def clip(x):
    return round(min(0.99, max(0.01, x)), 3)


shots = []
t = 0.0
sid = 0
while t < FILM_SECONDS:
    dur = max(4.0, rng.gauss(24, 8))
    r = rng.random()
    if r < 0.33:
        on, desc, p = True, rng.choice(PRESENT_EASY), rng.gauss(0.84, 0.07)
    elif r < 0.43:
        on, desc, p = True, rng.choice(PRESENT_HARD), rng.gauss(0.52, 0.12)
    elif r < 0.88:
        on, desc, p = False, rng.choice(ABSENT_EASY), rng.gauss(0.12, 0.07)
    else:
        on, desc, p = False, rng.choice(ABSENT_HARD), rng.gauss(0.45, 0.12)
    shots.append(dict(shot_id=sid, start=round(t, 1), end=round(min(t + dur, FILM_SECONDS), 1),
                      description=desc, clip_score=clip(p), rumi_on_screen=int(on)))
    sid += 1
    t += dur

with open(OUT / "shots.csv", "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["shot_id", "start", "end"])
    for s in shots:
        w.writerow([s["shot_id"], s["start"], s["end"]])
with open(OUT / "shots_private.csv", "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(shots[0]))
    w.writeheader()
    w.writerows(shots)

on = [s for s in shots if s["rumi_on_screen"]]
gt = {
    "a_name_said_lines": mentions,
    "b_rumi_speaks_lines": speaks,
    "c_shots_on_screen": len(on),
    "d_seconds_on_screen": round(sum(s["end"] - s["start"] for s in on), 1),
    "n_cues": len(cues),
    "n_shots": len(shots),
}
(OUT / "ground_truth.json").write_text(json.dumps(gt, indent=2) + "\n")
print(json.dumps(gt, indent=2))
