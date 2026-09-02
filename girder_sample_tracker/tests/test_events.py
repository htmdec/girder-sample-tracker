import json

import pytest
from girder.constants import AccessType
from pytest_girder.assertions import assertStatus, assertStatusOk

from ..models.sample import Sample as SampleModel
from .conftest import add_event, add_multisample_event


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
    _post = staticmethod(add_multisample_event)

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


@pytest.mark.plugin("sample_tracker")
class TestClientEventId:
    """A retried write must not turn into a second event."""

    _post_multi = staticmethod(add_multisample_event)

    def test_repeated_client_event_id_is_recorded_once(self, server, user, sample):
        first = add_event(
            server, user, sample["_id"], "created", clientEventId="abc-123"
        )
        second = add_event(
            server, user, sample["_id"], "created", clientEventId="abc-123"
        )

        assertStatusOk(first)
        assertStatusOk(second)
        assert len(first.json["events"]) == 1
        assert len(second.json["events"]) == 1
        stored = SampleModel().load(sample["_id"], force=True)["events"][0]
        assert stored["clientEventId"] == "abc-123"

    def test_retry_does_not_bump_updated_again(self, server, user, sample):
        assertStatusOk(
            add_event(server, user, sample["_id"], "created", clientEventId="abc-123")
        )
        after_first = SampleModel().load(sample["_id"], force=True)["updated"]

        assertStatusOk(
            add_event(server, user, sample["_id"], "created", clientEventId="abc-123")
        )

        assert SampleModel().load(sample["_id"], force=True)["updated"] == after_first

    def test_different_client_event_ids_are_two_events(self, server, user, sample):
        assertStatusOk(
            add_event(server, user, sample["_id"], "created", clientEventId="one")
        )
        resp = add_event(server, user, sample["_id"], "shipped", clientEventId="two")

        assertStatusOk(resp)
        assert [e["clientEventId"] for e in resp.json["events"]] == ["two", "one"]

    def test_without_a_client_event_id_repeats_still_append(self, server, user, sample):
        assertStatusOk(add_event(server, user, sample["_id"], "created"))
        resp = add_event(server, user, sample["_id"], "created")

        assertStatusOk(resp)
        assert len(resp.json["events"]) == 2
        assert "clientEventId" not in resp.json["events"][0]

    def test_the_same_id_on_a_different_sample_still_lands(self, server, user, samples):
        first, second = samples[0], samples[1]
        assertStatusOk(
            add_event(server, user, first["_id"], "created", clientEventId="shared")
        )
        resp = add_event(server, user, second["_id"], "created", clientEventId="shared")

        assertStatusOk(resp)
        assert len(resp.json["events"]) == 1

    def test_multisample_retry_is_recorded_once_per_sample(self, server, user, samples):
        ids = [s["_id"] for s in samples]
        first = self._post_multi(server, user, ids, "created", clientEventId="batch-1")
        second = self._post_multi(server, user, ids, "created", clientEventId="batch-1")

        assertStatusOk(first)
        assertStatusOk(second)
        assert first.json["processed"] == 3
        assert second.json["processed"] == 3
        for sample in samples:
            events = SampleModel().load(sample["_id"], force=True)["events"]
            assert len(events) == 1
            assert events[0]["clientEventId"] == "batch-1"

    def test_multisample_partial_retry_fills_the_gap(self, server, user, samples):
        """A batch that half landed, then retried, ends up complete but not doubled."""
        assertStatusOk(
            self._post_multi(
                server, user, [samples[0]["_id"]], "created", clientEventId="batch-2"
            )
        )
        resp = self._post_multi(
            server, user, [s["_id"] for s in samples], "created", clientEventId="batch-2"
        )

        assertStatusOk(resp)
        for sample in samples:
            assert len(SampleModel().load(sample["_id"], force=True)["events"]) == 1


@pytest.mark.plugin("sample_tracker")
class TestEventCoordinates:
    """A phone can report where it was; ``location`` stays the human label."""

    def test_coordinates_are_stored_as_numbers(self, server, user, sample):
        resp = add_event(
            server,
            user,
            sample["_id"],
            "created",
            location="Freezer 3",
            latitude="40.1164",
            longitude="-88.2434",
            accuracy="12.5",
        )

        assertStatusOk(resp)
        event = resp.json["events"][0]
        assert event["latitude"] == pytest.approx(40.1164)
        assert event["longitude"] == pytest.approx(-88.2434)
        assert event["accuracy"] == pytest.approx(12.5)
        assert event["location"] == "Freezer 3"

        stored = SampleModel().load(sample["_id"], force=True)["events"][0]
        assert isinstance(stored["latitude"], float)
        assert isinstance(stored["longitude"], float)

    def test_location_alone_is_still_accepted(self, server, user, sample):
        resp = add_event(server, user, sample["_id"], "created", location="Bench 2")

        assertStatusOk(resp)
        event = resp.json["events"][0]
        assert event["location"] == "Bench 2"
        assert "latitude" not in event
        assert "longitude" not in event
        assert "accuracy" not in event

    @pytest.mark.parametrize(
        "params,message",
        [
            ({"latitude": "40.1"}, "together"),
            ({"longitude": "-88.2"}, "together"),
            ({"latitude": "90.1", "longitude": "0"}, "between -90 and 90"),
            ({"latitude": "-90.1", "longitude": "0"}, "between -90 and 90"),
            ({"latitude": "0", "longitude": "180.1"}, "between -180 and 180"),
            ({"latitude": "0", "longitude": "-180.1"}, "between -180 and 180"),
            (
                {"latitude": "0", "longitude": "0", "accuracy": "-1"},
                "must not be negative",
            ),
        ],
    )
    def test_bad_coordinates_are_rejected(self, server, user, sample, params, message):
        resp = add_event(server, user, sample["_id"], "created", **params)

        assertStatus(resp, 400)
        assert message in resp.json["message"]
        assert SampleModel().load(sample["_id"], force=True)["events"] == []

    def test_non_numeric_coordinates_are_rejected(self, server, user, sample):
        resp = add_event(
            server, user, sample["_id"], "created", latitude="here", longitude="0"
        )

        assertStatus(resp, 400)

    def test_the_range_extremes_are_allowed(self, server, user, sample):
        resp = add_event(
            server,
            user,
            sample["_id"],
            "created",
            latitude="-90",
            longitude="180",
            accuracy="0",
        )

        assertStatusOk(resp)

    def test_accuracy_without_coordinates_is_allowed(self, server, user, sample):
        """A device may know its precision without a fix worth recording."""
        resp = add_event(server, user, sample["_id"], "created", accuracy="30")

        assertStatusOk(resp)
        assert resp.json["events"][0]["accuracy"] == pytest.approx(30.0)
        assert "latitude" not in resp.json["events"][0]

    def test_multisample_coordinates_apply_to_every_sample(self, server, user, samples):
        resp = add_multisample_event(
            server,
            user,
            [s["_id"] for s in samples],
            "created",
            latitude="40.1164",
            longitude="-88.2434",
        )

        assertStatusOk(resp)
        for sample in samples:
            event = SampleModel().load(sample["_id"], force=True)["events"][0]
            assert event["latitude"] == pytest.approx(40.1164)
            assert event["longitude"] == pytest.approx(-88.2434)

    def test_multisample_bad_coordinates_reject_the_whole_request(
        self, server, user, samples
    ):
        resp = add_multisample_event(
            server, user, [s["_id"] for s in samples], "created", latitude="40.1"
        )

        assertStatus(resp, 400)
        for sample in samples:
            assert SampleModel().load(sample["_id"], force=True)["events"] == []
