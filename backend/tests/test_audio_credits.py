"""
can_generate() — the credits chokepoint (docs/listen-audio-plan.md §5). Free for
everything at launch; pinned here so a future credits change is caught if it silently
starts denying requests that used to be free.
"""

import uuid

from app.models.knowledge import AudioLens, AudioScopeType
from app.services.audio_credits import can_generate


def test_personal_request_is_free_and_allowed_at_launch():
    decision = can_generate(
        owner_id=uuid.uuid4(),
        scope_type=AudioScopeType.TOPIC,
        scope_ref=uuid.uuid4(),
        lens=AudioLens.USER_INSTRUCTION,
    )
    assert decision.allow is True
    assert decision.cost == 0
