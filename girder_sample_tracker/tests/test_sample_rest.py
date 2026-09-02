import json

import pytest
from girder.constants import AccessType
from pytest_girder.assertions import assertStatus, assertStatusOk

from ..models.sample import Sample as SampleModel
from .conftest import access_list, create_sample


@pytest.mark.plugin("sample_tracker")
class TestCreateSample:
    def test_create_minimal(self, server, user):
        resp = create_sample(server, user, "Sample 1")

        assertStatusOk(resp)
        assert resp.json["name"] == "Sample 1"
        assert resp.json["creator"] == str(user["_id"])
        assert resp.json["events"] == []
        assert resp.json["eventTypes"] == []

    def test_create_with_description_and_event_types(self, server, user):
        resp = create_sample(
            server,
            user,
            "Sample 1",
            description="Some sample",
            eventTypes=["created", "shipped"],
        )

        assertStatusOk(resp)
        assert resp.json["description"] == "Some sample"
        assert resp.json["eventTypes"] == ["created", "shipped"]

    def test_create_requires_authentication(self, server, user):
        resp = server.request(
            path="/sample",
            method="POST",
            params={"name": "Sample 1", "access": json.dumps(access_list(user))},
        )

        assertStatus(resp, 401)

    def test_create_requires_a_name(self, server, user):
        resp = server.request(
            path="/sample",
            method="POST",
            user=user,
            params={"access": json.dumps(access_list(user))},
        )

        assertStatus(resp, 400)

    def test_create_applies_the_access_list(self, server, user, user2):
        resp = create_sample(
            server, user, "Sample 1", access=access_list(user2, AccessType.READ)
        )

        assertStatusOk(resp)
        sample = SampleModel().load(resp.json["_id"], force=True)
        assert SampleModel().hasAccess(sample, user2, AccessType.READ)

    def test_create_batch_appends_a_number(self, server, user):
        resp = create_sample(server, user, "Batch ", batchSize=12)

        assertStatusOk(resp)
        names = {s["name"] for s in SampleModel().find({})}
        # The padding width is ceil(log10(batchSize)) digits.
        assert names == {f"Batch {i:02d}" for i in range(1, 13)}
        # The first sample of the batch is what comes back.
        assert resp.json["name"] == "Batch 01"

    def test_create_batch_padding_is_derived_from_the_batch_size(self, server, user):
        """ceil(log10(10)) is 1, so a batch of ten is padded to a single digit."""
        resp = create_sample(server, user, "Batch ", batchSize=10)

        assertStatusOk(resp)
        names = {s["name"] for s in SampleModel().find({})}
        assert names == {f"Batch {i}" for i in range(1, 11)}

    def test_create_batch_honors_an_explicit_placeholder(self, server, user):
        resp = create_sample(server, user, "S-{number:03d}-X", batchSize=3)

        assertStatusOk(resp)
        names = sorted(s["name"] for s in SampleModel().find({}))
        assert names == ["S-001-X", "S-002-X", "S-003-X"]

    def test_create_batch_shares_metadata(self, server, user):
        resp = create_sample(
            server, user, "Batch ", batchSize=2, description="d", eventTypes=["a"]
        )

        assertStatusOk(resp)
        for sample in SampleModel().find({}):
            assert sample["description"] == "d"
            assert sample["eventTypes"] == ["a"]

    @pytest.mark.parametrize("batchSize", [0, -1, 65, 1000])
    def test_create_rejects_out_of_range_batch_size(self, server, user, batchSize):
        resp = create_sample(server, user, "Batch ", batchSize=batchSize)

        assertStatus(resp, 400)
        assert "Batch size must be at least 1" in resp.json["message"]
        assert SampleModel().collection.count_documents({}) == 0

    def test_create_batch_rejects_a_bad_placeholder(self, server, user):
        """A name with a ``{number``-like but unusable placeholder is rejected."""
        resp = create_sample(server, user, "S-{number2}", batchSize=4)

        assertStatus(resp, 400)
        assert "must contain a '{number}' placeholder" in resp.json["message"]
        assert SampleModel().collection.count_documents({}) == 0

    def test_create_batch_of_one_keeps_the_name_verbatim(self, server, user):
        resp = create_sample(server, user, "Just One", batchSize=1)

        assertStatusOk(resp)
        assert resp.json["name"] == "Just One"


@pytest.mark.plugin("sample_tracker")
class TestGetSample:
    def test_get_sample(self, server, user, sample):
        resp = server.request(path=f"/sample/{sample['_id']}", user=user)

        assertStatusOk(resp)
        assert resp.json["name"] == sample["name"]
        assert resp.json["description"] == sample["description"]
        assert resp.json["events"] == []

    def test_get_sample_is_filtered(self, server, user, sample):
        resp = server.request(path=f"/sample/{sample['_id']}", user=user)

        assertStatusOk(resp)
        # exposeFields() decides what leaves the server.
        assert "access" not in resp.json
        assert set(resp.json) <= {
            "_id",
            "created",
            "creator",
            "description",
            "eventTypes",
            "updated",
            "name",
            "events",
            "_accessLevel",
            "_modelType",
        }

    def test_get_sample_denied_for_other_users(self, server, user2, sample):
        resp = server.request(path=f"/sample/{sample['_id']}", user=user2)

        assertStatus(resp, 403)

    def test_get_sample_denied_anonymously(self, server, sample):
        resp = server.request(path=f"/sample/{sample['_id']}")

        assertStatus(resp, 401)

    def test_get_missing_sample(self, server, user):
        resp = server.request(path="/sample/000000000000000000000000", user=user)

        assertStatus(resp, 400)


@pytest.mark.plugin("sample_tracker")
class TestListSamples:
    def test_list_returns_owned_samples(self, server, user, samples):
        resp = server.request(path="/sample", user=user)

        assertStatusOk(resp)
        assert {s["name"] for s in resp.json} == {"Alpha", "Beta", "Gamma"}

    def test_list_default_sort_is_name_descending(self, server, user, samples):
        resp = server.request(path="/sample", user=user)

        assertStatusOk(resp)
        assert [s["name"] for s in resp.json] == ["Gamma", "Beta", "Alpha"]

    def test_list_omits_events(self, server, user, sample):
        from .test_model import make_event

        SampleModel().add_event(sample, make_event(user))
        resp = server.request(path="/sample", user=user)

        assertStatusOk(resp)
        assert "events" not in resp.json[0]

    def test_list_filters_by_query(self, server, user, samples):
        resp = server.request(path="/sample", user=user, params={"query": "al"})

        assertStatusOk(resp)
        assert [s["name"] for s in resp.json] == ["Alpha"]

    def test_list_query_is_case_insensitive(self, server, user, samples):
        resp = server.request(path="/sample", user=user, params={"query": "BETA"})

        assertStatusOk(resp)
        assert [s["name"] for s in resp.json] == ["Beta"]

    def test_list_query_is_a_regex(self, server, user, samples):
        resp = server.request(path="/sample", user=user, params={"query": "^[AB]"})

        assertStatusOk(resp)
        assert {s["name"] for s in resp.json} == {"Alpha", "Beta"}

    def test_list_paging(self, server, user, samples):
        resp = server.request(
            path="/sample",
            user=user,
            params={"limit": 2, "offset": 1, "sort": "name", "sortdir": 1},
        )

        assertStatusOk(resp)
        assert [s["name"] for s in resp.json] == ["Beta", "Gamma"]

    def test_list_reports_the_total_count(self, server, user, samples):
        resp = server.request(path="/sample", user=user, params={"limit": 1})

        assertStatusOk(resp)
        assert resp.headers["Girder-Total-Count"] == len(samples)

    def test_list_hides_other_users_samples(self, server, user2, samples):
        resp = server.request(path="/sample", user=user2)

        assertStatusOk(resp)
        assert resp.json == []

    def test_list_is_public_but_empty_anonymously(self, server, samples):
        resp = server.request(path="/sample")

        assertStatusOk(resp)
        assert resp.json == []


@pytest.mark.plugin("sample_tracker")
class TestUpdateSample:
    def test_update_name_and_description(self, server, user, sample):
        resp = server.request(
            path=f"/sample/{sample['_id']}",
            method="PUT",
            user=user,
            params={
                "name": "Renamed",
                "description": "New description",
                "eventTypes": json.dumps(sample["eventTypes"]),
            },
        )

        assertStatusOk(resp)
        assert resp.json["name"] == "Renamed"
        assert resp.json["description"] == "New description"
        assert resp.json["eventTypes"] == sample["eventTypes"]

    def test_update_event_types(self, server, user, sample):
        resp = server.request(
            path=f"/sample/{sample['_id']}",
            method="PUT",
            user=user,
            params={"eventTypes": json.dumps(["new", "types"])},
        )

        assertStatusOk(resp)
        assert resp.json["eventTypes"] == ["new", "types"]

    def test_update_bumps_updated(self, server, user, sample):
        resp = server.request(
            path=f"/sample/{sample['_id']}",
            method="PUT",
            user=user,
            params={"name": "Renamed", "eventTypes": json.dumps(sample["eventTypes"])},
        )

        assertStatusOk(resp)
        reloaded = SampleModel().load(sample["_id"], force=True)
        assert reloaded["updated"] > sample["updated"]

    def test_update_without_event_types_keeps_them(self, server, user, sample):
        resp = server.request(
            path=f"/sample/{sample['_id']}",
            method="PUT",
            user=user,
            params={"name": "Renamed"},
        )

        assertStatusOk(resp)
        assert resp.json["eventTypes"] == sample["eventTypes"]

    def test_update_can_clear_event_types(self, server, user, sample):
        resp = server.request(
            path=f"/sample/{sample['_id']}",
            method="PUT",
            user=user,
            params={"eventTypes": json.dumps([])},
        )

        assertStatusOk(resp)
        assert resp.json["eventTypes"] == []

    def test_update_requires_admin_access(self, server, user, user2, sample):
        SampleModel().setUserAccess(sample, user2, AccessType.WRITE, save=True)
        resp = server.request(
            path=f"/sample/{sample['_id']}",
            method="PUT",
            user=user2,
            params={"name": "Renamed", "eventTypes": json.dumps([])},
        )

        assertStatus(resp, 403)


@pytest.mark.plugin("sample_tracker")
class TestDeleteSample:
    def test_delete_sample(self, server, user, sample):
        resp = server.request(
            path=f"/sample/{sample['_id']}", method="DELETE", user=user
        )

        assertStatusOk(resp)
        assert SampleModel().load(sample["_id"], force=True) is None

    def test_delete_requires_write_access(self, server, user, user2, sample):
        SampleModel().setUserAccess(sample, user2, AccessType.READ, save=True)
        resp = server.request(
            path=f"/sample/{sample['_id']}", method="DELETE", user=user2
        )

        assertStatus(resp, 403)
        assert SampleModel().load(sample["_id"], force=True) is not None

    def test_delete_requires_authentication(self, server, sample):
        resp = server.request(path=f"/sample/{sample['_id']}", method="DELETE")

        assertStatus(resp, 401)

    def test_bulk_delete(self, server, user, samples):
        resp = server.request(
            path="/sample",
            method="DELETE",
            user=user,
            params={"ids": json.dumps([str(s["_id"]) for s in samples])},
        )

        assertStatusOk(resp)
        assert SampleModel().collection.count_documents({}) == 0

    def test_bulk_delete_with_progress(self, server, user, samples):
        resp = server.request(
            path="/sample",
            method="DELETE",
            user=user,
            params={
                "ids": json.dumps([str(s["_id"]) for s in samples]),
                "progress": True,
            },
        )

        assertStatusOk(resp)
        assert SampleModel().collection.count_documents({}) == 0

    def test_bulk_delete_requires_admin_access(self, server, user, user2, samples):
        for sample in samples:
            SampleModel().setUserAccess(sample, user2, AccessType.WRITE, save=True)
        resp = server.request(
            path="/sample",
            method="DELETE",
            user=user2,
            params={"ids": json.dumps([str(s["_id"]) for s in samples])},
        )

        assertStatus(resp, 403)
        assert SampleModel().collection.count_documents({}) == len(samples)

    def test_bulk_delete_is_all_or_nothing_on_a_bad_id(self, server, user, samples):
        """A missing id aborts the batch, leaving already-deleted samples gone."""
        ids = [str(samples[0]["_id"]), "000000000000000000000000"]
        resp = server.request(
            path="/sample", method="DELETE", user=user, params={"ids": json.dumps(ids)}
        )

        assertStatus(resp, 400)
        assert SampleModel().collection.count_documents({}) == len(samples) - 1

    def test_bulk_delete_of_nothing(self, server, user, samples):
        resp = server.request(
            path="/sample", method="DELETE", user=user, params={"ids": json.dumps([])}
        )

        assertStatusOk(resp)
        assert SampleModel().collection.count_documents({}) == len(samples)
