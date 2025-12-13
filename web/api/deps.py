from __future__ import annotations
from functools import lru_cache

from app.main import create_app
from app import Orchestrator  


@lru_cache(maxsize=1)
def get_orchestrator() -> Orchestrator:
    return create_app()
