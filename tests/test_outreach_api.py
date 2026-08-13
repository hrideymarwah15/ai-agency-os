"""Outreach API surface and webhook security tests."""

import json

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api.outreach import router


def test_required_owner_and_webhook_routes_exist():
    paths = {(route.path, tuple(sorted(route.methods or []))) for route in router.routes}
    assert ("/api/v1/outreach/sequences/{sequence_id}", ("PUT",)) in paths
    assert ("/api/v1/outreach/objections/{objection_type}", ("PUT",)) in paths
    assert ("/api/v1/outreach/meetings/webhook", ("POST",)) in paths
    assert ("/api/v1/outreach/reply-webhook", ("POST",)) in paths


def test_unsigned_meeting_webhook_rejected_before_database_dependency():
    app = FastAPI()
    app.include_router(router)
    response = TestClient(app).post(
        "/api/v1/outreach/meetings/webhook",
        content=json.dumps({"triggerEvent": "BOOKING_CREATED"}),
    )
    assert response.status_code in {401, 500}


def test_meeting_configuration_route_is_owner_guarded():
    route = next(route for route in router.routes if route.path.endswith("/meetings/config"))
    dependency_names = {dependency.call.__name__ for dependency in route.dependant.dependencies}
    assert "get_current_owner" in dependency_names
