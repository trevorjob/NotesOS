"""
Mode registry — the lookup the API will use to run a mode by key.

Registering a new mode (ramble, teach, pretest) is a one-liner here; nothing else in
the engine changes. Keys are stable strings stored on every ``RetrievalAttempt``.
"""

from app.services.retrieval.modes import RetrievalMode
from app.services.retrieval.quiz_mode import QuizMode

_MODES: dict[str, RetrievalMode] = {}


def register(mode: RetrievalMode) -> None:
    _MODES[mode.key] = mode


def get_mode(key: str) -> RetrievalMode:
    try:
        return _MODES[key]
    except KeyError:
        raise ValueError(f"unknown retrieval mode {key!r}; have {sorted(_MODES)}")


def available_modes() -> list[str]:
    return sorted(_MODES)


register(QuizMode())
