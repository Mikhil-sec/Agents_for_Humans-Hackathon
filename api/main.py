"""Entrypoint shim.

The real application is `app/main.py`. This module exists so that both documented
commands work:

    uvicorn main:app          # root Makefile, `make api`
    uvicorn app.main:app      # api/AGENTS.md

Keeping both is cheaper than editing the root `Makefile`, which is not Lane B's
file to change.
"""

from app.main import app

__all__ = ["app"]
