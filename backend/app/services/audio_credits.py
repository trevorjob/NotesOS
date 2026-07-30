"""
Audio generation credits gate (docs/listen-audio-plan.md §5) — the one chokepoint every
personal audio request passes through before it's enqueued. Free for everything today;
the seam exists so a later pay-as-you-go model needs zero call-site changes.

Invariant that never changes: global/shared artifacts (owner_id is None) are always
free — they serve everyone, so they never call this at all. Only personal requests
(POST /audio/request) route through ``can_generate``.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Decision:
    allow: bool
    cost: int
    reason: str = ""


def can_generate(*, owner_id, scope_type, scope_ref, lens) -> Decision:
    """Whether ``owner_id`` may generate a personal artifact, and at what cost.

    Launch: always allowed, always free. The signature already carries everything a
    future credits/balance check would need (who, what scope, which lens) so that
    change lands here alone.
    """
    return Decision(allow=True, cost=0)
