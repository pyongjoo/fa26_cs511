"""Cut the trailer to its first minute and build the shot table that all demos use.

    python data/make_clip.py path/to/KPop-Demon-Hunters-SnapYT.App.mp4

Writes
  data/trailer_1min.mp4   the first 60 s of the trailer
  data/shots.csv          shot_id, start, end (seconds), rumi_on_screen (hand label)

Shot cuts: ffmpeg scene score > 0.3 on the letterbox-cropped full trailer, kept up to 60 s.
The full trailer is not kept in this repo; data/trailer_1min.mp4 and data/shots.csv are the inputs to every demo.
"""
import csv
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
VIDEO = sys.argv[1]
CLIP = 60.0
RUMI = {0, 2, 4, 6, 7, 11, 14, 17, 18, 19, 20, 29, 32, 40, 42, 43, 44, 46}  # hand labels: Rumi visible in the
                                                                        # middle frame of each shot of the clip

log = subprocess.run(["ffmpeg", "-hide_banner", "-i", VIDEO, "-an", "-vf",
                      "crop=640:268:0:46,select='gt(scene,0.3)',showinfo", "-f", "null", "-"],
                     capture_output=True, text=True, check=True).stderr
cuts = [0.0] + [t for t in map(float, re.findall(r"pts_time:([\d.]+)", log)) if t < CLIP] + [CLIP]

with open(HERE / "shots.csv", "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["shot_id", "start", "end", "rumi_on_screen"])
    for i, (a, b) in enumerate(zip(cuts, cuts[1:])):
        w.writerow([i, f"{a:.1f}", f"{b:.1f}", int(i in RUMI)])

subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", VIDEO, "-t", str(CLIP),
                "-c:v", "libx264", "-crf", "23", "-c:a", "aac", "-b:a", "96k", str(HERE / "trailer_1min.mp4")], check=True)

rumi = [(a, b) for i, (a, b) in enumerate(zip(cuts, cuts[1:])) if i in RUMI]
print(f"{len(cuts) - 1} shots, {len(rumi)} with Rumi, {sum(b - a for a, b in rumi):.1f} s of Rumi")
