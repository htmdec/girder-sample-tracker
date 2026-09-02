"""Shared fixtures for the sample-tracker tests.

Girder's own fixtures (``db``, ``server``, ``admin``, ``user``, ...) come from
pytest-girder; everything here is specific to sample tracking.
"""

import json

import pytest
from girder.constants import AccessType

from ..models.sample import Sample as SampleModel

REFERER = "https://girder.example.com/some/page"
GIRDER_BASE = "https://girder.example.com"


@pytest.fixture
def user2(db, admin):
    """A second regular user, to check that ACLs actually keep people out."""
    from girder.models.user import User

    return User().createUser(
        email="user2@girder.test",
        login="user2",
        firstName="Second",
        lastName="User",
        password="password",
        admin=False,
    )


@pytest.fixture
def sample(db, user):
    """A single sample owned by ``user``."""
    return SampleModel().create(
        "Sample 1",
        user,
        description="A sample",
        eventTypes=["created", "shipped"],
    )


@pytest.fixture
def samples(db, user):
    """Three samples owned by ``user``, named Alpha/Beta/Gamma."""
    return [
        SampleModel().create(name, user, eventTypes=["created"])
        for name in ("Alpha", "Beta", "Gamma")
    ]


def access_list(user=None, level=AccessType.ADMIN, groups=None):
    """Build an ACL payload of the shape the REST layer expects."""
    users = []
    if user is not None:
        users.append(
            {
                "id": str(user["_id"]),
                "login": user["login"],
                "level": level,
                "flags": [],
                "name": f"{user['firstName']} {user['lastName']}",
            }
        )
    return {"users": users, "groups": groups or []}


def create_sample(server, user, name, **kwargs):
    """POST /sample, returning the response.

    ``access`` is a required parameter of the route, so it always gets sent;
    pass ``access=<dict>`` to override the default (creator as ADMIN).
    """
    params = {"name": name}
    acl = kwargs.pop("access", access_list(user))
    params["access"] = json.dumps(acl)
    for key in ("eventTypes",):
        if key in kwargs:
            params[key] = json.dumps(kwargs.pop(key))
    params.update({k: v for k, v in kwargs.items() if v is not None})
    return server.request(path="/sample", method="POST", user=user, params=params)


def add_event(server, user, sample_id, eventType, **kwargs):
    """POST /sample/:id/event, returning the response."""
    params = {"eventType": eventType}
    params.update(kwargs)
    return server.request(
        path=f"/sample/{sample_id}/event", method="POST", user=user, params=params
    )


def add_multisample_event(server, user, ids, eventType, **kwargs):
    """POST /sample/event, returning the response."""
    params = {"ids": json.dumps([str(i) for i in ids]), "eventType": eventType}
    params.update(kwargs)
    return server.request(
        path="/sample/event", method="POST", user=user, params=params
    )
