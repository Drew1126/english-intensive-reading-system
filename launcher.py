from __future__ import annotations

import os
import sys
import threading
import time
import urllib.request
import webbrowser
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = PROJECT_DIR / "backend"
URL = "http://127.0.0.1:8001/"
TESSERACT_EXE = Path(r"D:\Tesseract-OCR\tesseract.exe")


def open_browser_when_ready() -> None:
    """Open the site once Uvicorn starts accepting requests."""
    for _ in range(60):
        try:
            with urllib.request.urlopen(URL, timeout=1) as response:
                if response.status == 200:
                    webbrowser.open(URL)
                    return
        except Exception:
            time.sleep(0.5)


def main() -> None:
    if TESSERACT_EXE.is_file():
        os.environ["TESSERACT_CMD"] = str(TESSERACT_EXE)
        os.environ["PATH"] = f"{TESSERACT_EXE.parent}{os.pathsep}{os.environ.get('PATH', '')}"

    os.chdir(BACKEND_DIR)
    sys.path.insert(0, str(BACKEND_DIR))

    import uvicorn

    threading.Thread(target=open_browser_when_ready, daemon=True).start()
    print(f"Starting English Intensive Reading System at {URL}")
    print("Close this window to stop the service.\n")
    uvicorn.run("main:app", host="127.0.0.1", port=8001, reload=False)


if __name__ == "__main__":
    main()
