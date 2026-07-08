"""
Structured, user-created terms (Phase 1.3 revised).

Covers the pure composer/validator and the term + course-filing endpoints.
"""

import pytest

from app.models.term import DivisionType
from app.services.terms import (
    TermValidationError,
    compose_label,
    validate_components,
)


# ---- pure composition / validation --------------------------------------------

def test_compose_nigerian_style():
    assert (
        compose_label(DivisionType.SEMESTER, "Second", "200")
        == "200 Level · Second Semester"
    )


def test_compose_uk_term_style():
    assert (
        compose_label(DivisionType.TERM, "2", "Year 1")
        == "Year 1 · Term 2"
    )


def test_compose_us_fall_no_level():
    assert compose_label(DivisionType.SEMESTER, "Fall") == "Fall Semester"


def test_same_components_compose_identically():
    a = compose_label(DivisionType.SEMESTER, "Second", "200")
    b = compose_label(DivisionType.SEMESTER, "Second", "200")
    assert a == b  # uniformity: identical choices -> identical label


def test_validate_rejects_value_not_in_type():
    with pytest.raises(TermValidationError):
        validate_components(DivisionType.QUARTER, "Second")  # Second not a quarter


# ---- endpoints ----------------------------------------------------------------

async def test_vocab_endpoint(client):
    resp = await client.get("/api/terms/vocab")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert "SEMESTER" in body["division_types"]
    assert "Fall" in body["division_values"]["QUARTER"]
    assert "200" in body["suggested_levels"]


async def _create_term(client, headers, **overrides):
    payload = {
        "division_type": "SEMESTER",
        "division_value": "Second",
        "study_level": "200",
    }
    payload.update(overrides)
    resp = await client.post("/api/terms", headers=headers, json=payload)
    return resp


async def test_create_term_composes_label(client, register_user):
    user = await register_user()
    resp = await _create_term(client, user["headers"])
    assert resp.status_code == 201, resp.text
    assert resp.json()["term"]["label"] == "200 Level · Second Semester"


async def test_create_term_dedupes(client, register_user):
    user = await register_user()
    first = await _create_term(client, user["headers"])
    second = await _create_term(client, user["headers"])
    assert first.json()["term"]["id"] == second.json()["term"]["id"]


async def test_create_term_invalid_value_rejected(client, register_user):
    user = await register_user()
    resp = await _create_term(client, user["headers"], division_type="QUARTER", division_value="Second")
    assert resp.status_code == 400


async def test_create_course_with_term_files_it(client, register_user):
    user = await register_user()
    term_id = (await _create_term(client, user["headers"])).json()["term"]["id"]

    resp = await client.post(
        "/api/courses",
        headers=user["headers"],
        json={"code": "BIO201", "name": "Biology", "term_id": term_id},
    )
    assert resp.status_code == 201, resp.text

    listing = await client.get("/api/courses", headers=user["headers"])
    course = listing.json()["courses"][0]
    assert course["term_id"] == term_id
    assert course["term_label"] == "200 Level · Second Semester"


async def test_create_course_without_term_is_unfiled(client, register_user):
    user = await register_user()
    resp = await client.post(
        "/api/courses", headers=user["headers"], json={"code": "CHM101", "name": "Chem"}
    )
    assert resp.status_code == 201, resp.text
    listing = await client.get("/api/courses", headers=user["headers"])
    course = listing.json()["courses"][0]
    assert course["term_id"] is None
    assert course["term_label"] is None


async def test_cannot_file_under_another_users_term(client, register_user):
    owner = await register_user()
    term_id = (await _create_term(client, owner["headers"])).json()["term"]["id"]

    intruder = await register_user()
    resp = await client.post(
        "/api/courses",
        headers=intruder["headers"],
        json={"code": "PHY101", "name": "Physics", "term_id": term_id},
    )
    assert resp.status_code == 404


async def test_set_course_term_refiles(client, register_user):
    user = await register_user()
    # Create a course unfiled.
    course = (
        await client.post("/api/courses", headers=user["headers"], json={"code": "X1", "name": "X"})
    ).json()["course"]
    term_id = (await _create_term(client, user["headers"])).json()["term"]["id"]

    resp = await client.patch(
        f"/api/courses/{course['id']}/term",
        headers=user["headers"],
        json={"term_id": term_id},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["term_id"] == term_id

    # Unfile again.
    resp = await client.patch(
        f"/api/courses/{course['id']}/term",
        headers=user["headers"],
        json={"term_id": None},
    )
    assert resp.status_code == 200
    assert resp.json()["term_id"] is None
