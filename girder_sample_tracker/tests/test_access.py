import json

import pytest
from girder.constants import AccessType
from pytest_girder.assertions import assertStatus, assertStatusOk

from ..models.sample import Sample as SampleModel
from .conftest import access_list


@pytest.mark.plugin("sample_tracker")
class TestGetAccess:
    def test_get_access(self, server, user, sample):
        resp = server.request(path=f"/sample/{sample['_id']}/access", user=user)

        assertStatusOk(resp)
        assert [u["id"] for u in resp.json["users"]] == [str(user["_id"])]
        assert resp.json["users"][0]["level"] == AccessType.ADMIN
        assert resp.json["groups"] == []

    def test_get_access_requires_admin(self, server, user, user2, sample):
        SampleModel().setUserAccess(sample, user2, AccessType.WRITE, save=True)
        resp = server.request(path=f"/sample/{sample['_id']}/access", user=user2)

        assertStatus(resp, 403)

    def test_get_access_requires_authentication(self, server, sample):
        resp = server.request(path=f"/sample/{sample['_id']}/access")

        assertStatus(resp, 401)


@pytest.mark.plugin("sample_tracker")
class TestUpdateAccess:
    def _put(self, server, user, sample_id, acl, **kwargs):
        params = {"access": json.dumps(acl)}
        params.update(kwargs)
        return server.request(
            path=f"/sample/{sample_id}/access", method="PUT", user=user, params=params
        )

    def test_grant_read_to_another_user(self, server, user, user2, sample):
        acl = access_list(user)
        acl["users"].append(access_list(user2, AccessType.READ)["users"][0])

        resp = self._put(server, user, sample["_id"], acl)

        assertStatusOk(resp)
        reloaded = SampleModel().load(sample["_id"], force=True)
        assert SampleModel().hasAccess(reloaded, user2, AccessType.READ)
        assert not SampleModel().hasAccess(reloaded, user2, AccessType.WRITE)

    def test_granted_user_can_read_the_sample(self, server, user, user2, sample):
        acl = access_list(user)
        acl["users"].append(access_list(user2, AccessType.READ)["users"][0])
        assertStatusOk(self._put(server, user, sample["_id"], acl))

        resp = server.request(path=f"/sample/{sample['_id']}", user=user2)

        assertStatusOk(resp)
        assert resp.json["name"] == sample["name"]

    def test_revoking_access_hides_the_sample(self, server, user, user2, sample):
        SampleModel().setUserAccess(sample, user2, AccessType.READ, save=True)

        assertStatusOk(self._put(server, user, sample["_id"], access_list(user)))

        resp = server.request(path=f"/sample/{sample['_id']}", user=user2)
        assertStatus(resp, 403)

    def test_update_access_requires_admin(self, server, user, user2, sample):
        SampleModel().setUserAccess(sample, user2, AccessType.WRITE, save=True)

        resp = self._put(server, user2, sample["_id"], access_list(user2))

        assertStatus(resp, 403)

    def test_update_access_requires_an_object(self, server, user, sample):
        resp = server.request(
            path=f"/sample/{sample['_id']}/access",
            method="PUT",
            user=user,
            params={"access": json.dumps([])},
        )

        assertStatus(resp, 400)

    def test_update_access_requires_authentication(self, server, user, sample):
        resp = server.request(
            path=f"/sample/{sample['_id']}/access",
            method="PUT",
            params={"access": json.dumps(access_list(user))},
        )

        assertStatus(resp, 401)


@pytest.mark.plugin("sample_tracker")
class TestBulkUpdateAccess:
    def _put(self, server, user, ids, acl, **kwargs):
        params = {
            "ids": json.dumps([str(i) for i in ids]),
            "access": json.dumps(acl),
        }
        return server.request(
            path="/sample/access", method="PUT", user=user, params=params, **kwargs
        )

    def test_bulk_grant(self, server, user, user2, samples):
        acl = access_list(user)
        acl["users"].append(access_list(user2, AccessType.READ)["users"][0])

        resp = self._put(server, user, [s["_id"] for s in samples], acl)

        assertStatusOk(resp)
        for sample in samples:
            reloaded = SampleModel().load(sample["_id"], force=True)
            assert SampleModel().hasAccess(reloaded, user2, AccessType.READ)

    def test_bulk_grant_returns_the_last_sample(self, server, user, samples):
        resp = self._put(server, user, [s["_id"] for s in samples], access_list(user))

        assertStatusOk(resp)
        assert resp.json["_id"] == str(samples[-1]["_id"])

    def test_bulk_update_requires_admin_on_every_sample(
        self, server, user, user2, samples
    ):
        SampleModel().setUserAccess(samples[0], user2, AccessType.ADMIN, save=True)

        resp = self._put(server, user2, [s["_id"] for s in samples], access_list(user2))

        assertStatus(resp, 403)

    def test_bulk_update_rejects_unknown_ids(self, server, user, samples):
        ids = [str(samples[0]["_id"]), "000000000000000000000000"]

        resp = self._put(server, user, ids, access_list(user))

        assertStatus(resp, 400)

    def test_bulk_update_of_nothing_is_a_noop(self, server, user):
        """With no ids there is nothing to return, but the route must not fail."""
        resp = self._put(server, user, [], access_list(user))

        assertStatusOk(resp)
        assert resp.json is None

    def test_bulk_update_requires_authentication(self, server, user, samples):
        resp = server.request(
            path="/sample/access",
            method="PUT",
            params={
                "ids": json.dumps([str(s["_id"]) for s in samples]),
                "access": json.dumps(access_list(user)),
            },
        )

        assertStatus(resp, 401)
