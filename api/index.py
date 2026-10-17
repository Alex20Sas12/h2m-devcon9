import os
import sys

# Vercel python runtime: serve the FastAPI app from repo root.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("H2M_DB", "/tmp/desk.sqlite3")  # only writable path on Vercel

from server import app  # noqa: E402

app = app  # Vercel entrypoint
