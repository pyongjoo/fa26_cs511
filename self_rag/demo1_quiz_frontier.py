"""Send a prompt to a frontier model and print its reply.

    uv run python demo1_quiz_frontier.py            # type or paste a prompt; finish with a line containing only "."
    uv run python demo1_quiz_frontier.py "Hello"    # send one prompt from the command line

Settings come from .env (see README.md): AZURE_OPENAI_API_KEY, and optionally
AZURE_OPENAI_ENDPOINT and AZURE_OPENAI_DEPLOYMENT.
"""

import os
import sys

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()
client = OpenAI(
    base_url=os.environ.get("AZURE_OPENAI_ENDPOINT", "https://yongjoo-us-east-2.services.ai.azure.com/openai/v1"),
    api_key=os.environ["AZURE_OPENAI_API_KEY"],
)
MODEL = os.environ.get("AZURE_OPENAI_DEPLOYMENT", "gpt-5.6-luna")


def send(prompt):
    response = client.responses.create(model=MODEL, input=prompt)
    print(response.output_text)


def main():
    if len(sys.argv) > 1:
        send(" ".join(sys.argv[1:]))
        return
    while True:
        print('\nPrompt (end with a line containing only ".", Ctrl-C to quit):')
        lines = []
        try:
            for line in iter(input, "."):
                lines.append(line)
        except (EOFError, KeyboardInterrupt):
            return
        print("\n--- reply ---")
        send("\n".join(lines))


if __name__ == "__main__":
    main()
