"""Fine-tune a small language model on (input, target) examples.

Each line of the data file is   input ||| target
Only the target tokens are in the loss, as on the slides.

    uv run python demo2_finetune.py                       # uses demo2_train.txt, saves ./finetuned.pt (or finetuned-2.pt, ...)
    uv run python demo2_finetune.py --data my.txt --steps 50 --lr 5e-5
"""

import argparse
import math
import os

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

BASE_MODEL = "HuggingFaceTB/SmolLM2-360M"


def load_examples(path, tok):
    """Turn each 'input ||| target' line into token ids plus loss labels."""
    examples = []
    for line in open(path, encoding="utf-8"):
        line = line.rstrip("\n")
        if not line.strip() or line.startswith("#"):
            continue
        inp, tgt = [part.strip() for part in line.split("|||")]
        inp_ids = tok(inp).input_ids
        tgt_ids = tok(" " + tgt, add_special_tokens=False).input_ids   # leading space: " Seoul"
        ids = inp_ids + tgt_ids
        labels = [-100] * len(inp_ids) + tgt_ids    # -100 = not in the loss (the input part)
        examples.append((inp, tgt, torch.tensor([ids]), torch.tensor([labels])))
    return examples


def new_file_name(path):
    """finetuned.pt, or finetuned-2.pt, finetuned-3.pt, ... if that file already exists."""
    stem, ext = os.path.splitext(path)
    n, out = 1, path
    while os.path.exists(out):
        n += 1
        out = f"{stem}-{n}{ext}"
    return out


def target_prob(model, ids, labels):
    """Probability the model gives to the whole target (product over its tokens)."""
    with torch.no_grad():
        loss = model(input_ids=ids, labels=labels).loss   # mean of -log p over target tokens
    n = int((labels != -100).sum())
    return math.exp(-loss.item() * n)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--model", default=BASE_MODEL)
    ap.add_argument("--data", default="demo2_train.txt")
    ap.add_argument("--out", default="finetuned.pt", help="output file; an existing file is never overwritten")
    ap.add_argument("--steps", type=int, default=30)
    ap.add_argument("--lr", type=float, default=5e-5, help="learning rate")
    args = ap.parse_args()

    torch.manual_seed(0)
    tok = AutoTokenizer.from_pretrained(args.model)
    model = AutoModelForCausalLM.from_pretrained(args.model)
    examples = load_examples(args.data, tok)
    print(f"{len(examples)} training examples from {args.data}")

    def report(tag):
        print(f"\n{tag}: p(target | input)")
        for inp, tgt, ids, labels in examples:
            print(f"  {target_prob(model, ids, labels):.4f}   {inp} -> {tgt}")

    model.eval(); report("before")

    # the four ingredients: model, data, loss, optimizer
    optimizer = torch.optim.AdamW(model.parameters(), lr=args.lr)
    model.train()
    for step in range(1, args.steps + 1):
        total = 0.0
        for _, _, ids, labels in examples:                 # one small batch = all examples
            loss = model(input_ids=ids, labels=labels).loss  # forward + next-token loss
            (loss / len(examples)).backward()                # backward: gradients for every weight
            total += loss.item()
        optimizer.step()                                     # update: w <- w - lr * (scaled) gradient
        optimizer.zero_grad()
        if step == 1 or step % 5 == 0:
            print(f"step {step:3d}   loss {total / len(examples):.3f}")

    model.eval(); report("after")
    out = new_file_name(args.out)
    # one file: the fine-tuned weights (bfloat16 to halve the size); demo2_generate.py loads them on top of the base model
    torch.save({"base_model": args.model,
                "state_dict": {k: v.to(torch.bfloat16) for k, v in model.state_dict().items()}}, out)
    print(f"\nsaved to ./{out}   try:  uv run python demo2_generate.py --model {out}")


if __name__ == "__main__":
    main()
