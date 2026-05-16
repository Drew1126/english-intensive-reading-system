#!/usr/bin/env python3
"""Test with requests library."""
import subprocess
import time
import json
import sys
import os

os.chdir("/home/drew/English/backend")

# Clean up
import glob
for f in glob.glob("data/articles/2026-05-04_article_*.json"):
    os.remove(f)

# Import requests
try:
    import requests
except ImportError:
    os.system(f"{sys.executable} -m pip install requests --break-system-packages -q")
    import requests

# Start server
server = subprocess.Popen(
    [sys.executable, "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8765"],
    stdout=subprocess.PIPE,
    stderr=subprocess.STDOUT,
    text=True,
)
time.sleep(6)

try:
    # Test GET
    print("[TEST] GET...", flush=True)
    r1 = requests.get("http://localhost:8765/api/article/daily?article_index=0", timeout=40)
    d1 = r1.json()
    print(f"[TEST] GET OK: {d1['word_count']} words", flush=True)

    time.sleep(1)

    # Test POST
    print("[TEST] POST (may take 20-30s)...", flush=True)
    r2 = requests.post("http://localhost:8765/api/article/next", timeout=60)
    d2 = r2.json()
    print(f"[TEST] POST OK: {d2['word_count']} words, index={d2['article_index']}", flush=True)

    # Test cache
    r3 = requests.get("http://localhost:8765/api/article/daily?article_index=0", timeout=10)
    d3 = r3.json()
    print(f"[TEST] Cached: {d3['word_count']} words", flush=True)

    print("\n[TEST] ALL PASSED", flush=True)
except Exception as e:
    print(f"[TEST] ERROR: {e}", flush=True)
    import traceback
    traceback.print_exc()
finally:
    server.terminate()
    try:
        server.wait(timeout=5)
    except subprocess.TimeoutExpired:
        server.kill()
    out, _ = server.communicate(timeout=5)
    print("\n=== SERVER LOG ===")
    print(out[-3000:])
    print("=== END LOG ===")
