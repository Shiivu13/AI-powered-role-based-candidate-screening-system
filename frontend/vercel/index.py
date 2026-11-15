"""Vercel entry point: exposes the FastAPI app to the Python runtime.

At build time ``scripts/vercel-build.sh`` places this file at ``api/index.py``
inside the function bundle, next to the backend's ``app`` package and the
compact knowledge base (``kb/``).
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.environ.setdefault("VECTOR_BACKEND", "numpy")
os.environ.setdefault("KB_DIR", os.path.join(ROOT, "kb"))

from app.main import app  # noqa: E402,F401
