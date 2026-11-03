# scripts/test_gemini_direct.py
import time
from app.services.gemini_client import get_gemini_client

client = get_gemini_client()

print("Sending a simple request to Gemini...")
start = time.time()

try:
    response = client.generate_reply([{"role": "user", "content": "Say hello in one sentence."}])
    print(f"Got a response in {time.time() - start:.1f}s:")
    print(response)
except Exception as exc:
    print(f"Failed after {time.time() - start:.1f}s with error:")
    print(repr(exc))