"""Call a small language model as a function: tokens in, next-token probabilities out.

Type a text; the script shows its tokens, the most likely next tokens with their
probabilities, and the single most likely next token. It does not continue the
text. To go one step further, type the whole text again with that token appended.

    uv run python demo2_generate.py                     # the original model
    uv run python demo2_generate.py --model finetuned.pt   # after running demo2_finetune.py
"""

import argparse

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

BASE_MODEL = "HuggingFaceTB/SmolLM2-360M"   # 360M parameters: runs on a laptop CPU


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--model", default=BASE_MODEL, help="Hugging Face name, or a .pt file saved by demo2_finetune.py")
    ap.add_argument("--top", type=int, default=5, help="how many next-token candidates to show")
    args = ap.parse_args()

    if args.model.endswith(".pt"):
        # a file saved by demo2_finetune.py: the base model plus fine-tuned weights
        saved = torch.load(args.model, map_location="cpu")
        tok = AutoTokenizer.from_pretrained(saved["base_model"])
        model = AutoModelForCausalLM.from_pretrained(saved["base_model"])
        model.load_state_dict(saved["state_dict"])
    else:
        tok = AutoTokenizer.from_pretrained(args.model)
        model = AutoModelForCausalLM.from_pretrained(args.model)
    model.eval()
    print(f"model: {args.model}")

    while True:
        try:
            text = input("\ninput> ")
        except (EOFError, KeyboardInterrupt):
            print()
            return
        if not text.strip():
            continue

        ids = tok(text, return_tensors="pt").input_ids
        pieces = [tok.decode(i) for i in ids[0]]
        print(f"tokens ({len(pieces)}): " + " | ".join(repr(p) for p in pieces))

        # f(tokens) -> one probability per vocabulary token, for the next position
        with torch.no_grad():
            logits = model(ids).logits[0, -1]
        probs = torch.softmax(logits, dim=-1)
        top = torch.topk(probs, args.top)
        print(f"next-token probabilities (top {args.top} of {probs.shape[0]:,}):")
        for p, i in zip(top.values, top.indices):
            print(f"  {tok.decode(i)!r:<14} {p.item():.3f}")
        print(f"next token: {tok.decode(top.indices[0])!r}")


if __name__ == "__main__":
    main()
