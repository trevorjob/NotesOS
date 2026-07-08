"""Baseline coverage for the auth surface we're about to migrate."""

import pytest


async def test_register_returns_tokens_and_user(client):
    resp = await client.post(
        "/api/auth/register",
        json={"email": "new@test.dev", "password": "password123", "full_name": "New User"},
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["access_token"]
    assert body["refresh_token"]
    assert body["user"]["email"] == "new@test.dev"
    assert body["user"]["full_name"] == "New User"


async def test_register_duplicate_email_rejected(client):
    payload = {"email": "dup@test.dev", "password": "password123", "full_name": "Dup"}
    first = await client.post("/api/auth/register", json=payload)
    assert first.status_code == 201
    second = await client.post("/api/auth/register", json=payload)
    assert second.status_code == 400


async def test_login_success(client, register_user):
    user = await register_user(email="login@test.dev", password="secretpw1")
    resp = await client.post(
        "/api/auth/login",
        json={"email": "login@test.dev", "password": "secretpw1"},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["access_token"]


async def test_login_wrong_password_rejected(client, register_user):
    await register_user(email="wrong@test.dev", password="rightpw12")
    resp = await client.post(
        "/api/auth/login",
        json={"email": "wrong@test.dev", "password": "notmypw12"},
    )
    assert resp.status_code == 401


async def test_refresh_issues_new_access_token(client, register_user):
    user = await register_user()
    resp = await client.post(
        "/api/auth/refresh",
        json={"refresh_token": user["tokens"]["refresh_token"]},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["access_token"]


async def test_protected_route_requires_auth(client):
    resp = await client.get("/api/courses")
    assert resp.status_code in (401, 403)
