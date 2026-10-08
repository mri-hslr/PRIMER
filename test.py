"""
Minimal Groq connectivity test.
Run this BEFORE touching app.py — if this doesn't work, app.py won't either,
and the bug is in the key/network, not in your Flask code.
"""

import os
from dotenv import load_dotenv

load_dotenv()

from groq import Groq

api_key = os.getenv("GROQ_API_KEY")
print("Key loaded:", bool(api_key), "- length:", len(api_key) if api_key else 0)

client = Groq(api_key=api_key)

# Ask Groq directly which models THIS key currently has access to,
# instead of guessing a model name from docs/memory that may be stale.
print("AVAILABLE MODELS FOR THIS KEY:")
models = client.models.list()
for m in models.data:
    print(" -", m.id)
print()

# Use a real chat-capable model, not just models.data[0] (that was a
# prompt-injection *classifier*, not a chat model — hence the weird
# tiny number instead of a sentence last time).
first_model = "openai/gpt-oss-20b"
print(f"Testing a chat completion with: {first_model}")

response = client.chat.completions.create(
    model=first_model,
    messages=[
        {"role": "user", "content": "Say 'hello, groq is working' and nothing else."}
    ],
)

print()
print("RAW RESPONSE OBJECT:")
print(response)
print()
print("EXTRACTED TEXT:")
print(response.choices[0].message.content)