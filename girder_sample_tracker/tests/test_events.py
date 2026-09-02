import json

import pytest
from girder.constants import AccessType
from pytest_girder.assertions import assertStatus, assertStatusOk

from ..models.sample import Sample as SampleModel
from .conftest import add_event


def event_payload(sample, event):
    """The JSON body ``DELETE /sample/:id/event`` expects, as the client sees it."""
    return {
        "created": event["created"],
        "creator": event["creator"],
        "eventType": event["eventType"],
    }


@pytest.mark.plugin("sample_tracker")
class TestCreateEvent:
    def test_create_event(self, server, user, sample):
        resp = add_event(
            server, user, sample["_id"], "created", location="Lab A", comment="Hi"
        )

        assertStatusOk(resp)
        assert len(resp.json["events"]) == 1
        event = resp.json["events"][0]
        assert event["eventType"] == "created"
        assert event["location"] == "Lab A"
        assert event["comment"] == "Hi"
        assert event["creator"] == str(user["_id"])
        assert event["creatorName"] == f"{user['firstName']} {user['lastName']}"

    def test_create_event_optional_fields_default_to_none(self, server, user, sample):
        resp = add_event(server, user, sample["_id"], "created")

        assertStatusOk(resp)
        assert resp.json["events"][0]["location"] is None
        assert resp.json["events"][0]["comment"] is None

    def test_create_event_requires_an_event_type(self, server, user, sample):
        resp = server.request(
            path=f"/sample/{sample['_id']}/event", method="POST", user=user
        )

        assertStatus(resp, 400)

    def test_create_event_bumps_updated(self, server, user, sample):
        assertStatusOk(add_event(server, user, sample["_id"], "created"))

        reloaded = SampleModel().load(sample["_id"], force=True)
        assert reloaded["updated"] > sample["updated"]

    def test_events_are_newest_first(self, server, user, sample):
        add_event(server, user, sample["_id"], "created")
        resp = add_event(server, user, sample["_id"], "shipped")

        assertStatusOk(resp)
        assert [e["eventType"] for e in resp.json["events"]] == ["shipped", "created"]

    def test_create_event_requires_write_access(self, server, user, user2, sample):
        SampleModel().setUserAccess(sample, user2, AccessType.READ, save=True)
        resp = add_event(server, user2, sample["_id"], "created")

        assertStatus(resp, 403)

    def test_create_event_allowed_with_write_access(self, server, user, user2, sample):
        SampleModel().setUserAccess(sample, user2, AccessType.WRITE, save=True)
        resp = add_event(server, user2, sample["_id"], "created")

        assertStatusOk(resp)
        assert resp.json["events"][0]["creator"] == str(user2["_id"])

    def test_create_event_requires_authentication(self, server, sample):
        resp = server.request(
            path=f"/sample/{sample['_id']}/event",
            method="POST",
            params={"eventType": "created"},
        )

        assertStatus(resp, 401)

    def test_single_sample_event_type_is_not_validated(self, server, user, sample):
        """Unlike the bulk route, this one accepts types outside ``eventTypes``."""
        resp = add_event(server, user, sample["_id"], "not-in-the-list")

        assertStatusOk(resp)
        assert resp.json["events"][0]["eventType"] == "not-in-the-list"


@pytest.mark.plugin("sample_tracker")
class TestCreateMultisampleEvent:
    def _post(self, server, user, ids, eventType, **kwargs):
        params = {"ids": json.dumps([str(i) for i in ids]), "eventType": eventType}
        params.update(kwargs)
        return server.request(
            path="/sample/event", method="POST", user=user, params=params
        )

    def test_event_is_added_to_every_sample(self, server, user, samples):
        resp = self._post(
            server, user, [s["_id"] for s in samples], "created", location="Lab A"
        )

        assertStatusOk(resp)
        assert resp.json == {"processed": 3, "failed": 0}
        for sample in samples:
            reloaded = SampleModel().load(sample["_id"], force=True)
            assert len(reloaded["events"]) == 1
            assert reloaded["events"][0]["location"] == "Lab A"

    def test_all_samples_share_one_timestamp(self, server, user, samples):
        assertStatusOk(self._post(server, user, [s["_id"] for s in samples], "created"))

        timestamps = {
            SampleModel().load(s["_id"], force=True)["events"][0]["created"]
            for s in samples
        }
        assert len(timestamps) == 1

    def test_empty_id_list_is_rejected(self, server, user):
        resp = self._post(server, user, [], "created")

        assertStatus(resp, 400)
        assert "At least one sample ID" in resp.json["message"]

    def test_disallowed_event_type_is_counted_as_a_failure(self, server, user, samples):
        resp = self._post(server, user, [s["_id"] for s in samples], "not-allowed")

        assertStatusOk(resp)
        assert resp.json == {"processed": 0, "failed": 3}
        for sample in samples:
            assert SampleModel().load(sample["_id"], force=True)["events"] == []

    def test_any_event_type_is_allowed_when_none_are_declared(self, server, user):
        sample = SampleModel().create("Unconstrained", user)
        resp = self._post(server, user, [sample["_id"]], "anything")

        assertStatusOk(resp)
        assert resp.json == {"processed": 1, "failed": 0}

    def test_one_bad_sample_does_not_abort_the_batch(self, server, user, samples):
        ids = [s["_id"] for s in samples] + ["000000000000000000000000"]
        resp = self._post(server, user, ids, "created")

        assertStatusOk(resp)
        assert resp.json == {"processed": 3, "failed": 1}

    def test_inaccessible_samples_are_counted_as_failures(
        self, server, user, user2, samples
    ):
        SampleModel().setUserAccess(samples[0], user2, AccessType.WRITE, save=True)
        resp = self._post(server, user2, [s["_id"] for s in samples], "created")

        assertStatusOk(resp)
        assert resp.json == {"processed": 1, "failed": 2}

    def test_requires_authentication(self, server, samples):
        resp = server.request(
            path="/sample/event",
            method="POST",
            params={
                "ids": json.dumps([str(s["_id"]) for s in samples]),
                "eventType": "created",
            },
        )

        assertStatus(resp, 401)


@pytest.mark.plugin("sample_tracker")
class TestDeleteEvent:
    def _delete(self, server, user, sample_id, event):
        return server.request(
            path=f"/sample/{sample_id}/event",
            method="DELETE",
            user=user,
            params={"event": json.dumps(event)},
        )

    def test_delete_event(self, server, user, sample):
        created = add_event(server, user, sample["_id"], "created", comment="bye")
        assertStatusOk(created)

        resp = self._delete(
            server, user, sample["_id"], event_payload(sample, created.json["events"][0])
        )

        assertStatusOk(resp)
        assert resp.json["events"] == []

    def test_delete_event_leaves_the_others(self, server, user, sample):
        add_event(server, user, sample["_id"], "created")
        latest = add_event(server, user, sample["_id"], "shipped")
        assertStatusOk(latest)

        resp = self._delete(
            server, user, sample["_id"], event_payload(sample, latest.json["events"][0])
        )

        assertStatusOk(resp)
        assert [e["eventType"] for e in resp.json["events"]] == ["created"]

    def test_delete_unknown_event_is_a_noop(self, server, user, sample):
        created = add_event(server, user, sample["_id"], "created")
        event = event_payload(sample, created.json["events"][0])
        event["eventType"] = "never-happened"

        resp = self._delete(server, user, sample["_id"], event)

        assertStatusOk(resp)
        assert len(resp.json["events"]) == 1

    def test_delete_event_requires_admin_access(self, server, user, user2, sample):
        created = add_event(server, user, sample["_id"], "created")
        SampleModel().setUserAccess(sample, user2, AccessType.WRITE, save=True)

        resp = self._delete(
            server, user2, sample["_id"], event_payload(sample, created.json["events"][0])
        )

        assertStatus(resp, 403)

    def test_delete_event_requires_an_object(self, server, user, sample):
        resp = server.request(
            path=f"/sample/{sample['_id']}/event",
            method="DELETE",
            user=user,
            params={"event": json.dumps(["not", "an", "object"])},
        )

        assertStatus(resp, 400)
