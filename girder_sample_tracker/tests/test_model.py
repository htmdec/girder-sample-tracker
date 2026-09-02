import datetime

import pytest
from girder.constants import AccessType
from girder.exceptions import ValidationException

from ..models.sample import Sample as SampleModel
from .conftest import GIRDER_BASE, access_list

PNG_MAGIC = b"\x89PNG\r\n\x1a\n"


def make_event(user, eventType="created", **kwargs):
    event = {
        "comment": None,
        "created": datetime.datetime.now(datetime.UTC),
        "creator": user["_id"],
        "creatorName": f"{user['firstName']} {user['lastName']}",
        "eventType": eventType,
        "location": None,
    }
    event.update(kwargs)
    return event


@pytest.mark.plugin("sample_tracker")
class TestSampleModelCreate:
    def test_create_defaults(self, db, user):
        sample = SampleModel().create("Sample A", user)

        assert sample["name"] == "Sample A"
        assert sample["creator"] == user["_id"]
        assert sample["description"] is None
        assert sample["eventTypes"] == []
        assert sample["events"] == []
        assert sample["created"] == sample["updated"]
        assert sample["created"].tzinfo is not None
        assert "_id" in sample

    def test_create_with_metadata(self, db, user):
        sample = SampleModel().create(
            "Sample B", user, description="Fancy", eventTypes=["a", "b"]
        )

        assert sample["description"] == "Fancy"
        assert sample["eventTypes"] == ["a", "b"]

    def test_create_grants_creator_admin(self, db, user):
        sample = SampleModel().create("Sample C", user)

        assert SampleModel().hasAccess(sample, user, AccessType.ADMIN)

    def test_create_with_access_list(self, db, user, user2):
        sample = SampleModel().create(
            "Sample D", user, access=access_list(user2, AccessType.READ)
        )

        assert SampleModel().hasAccess(sample, user2, AccessType.READ)
        assert not SampleModel().hasAccess(sample, user2, AccessType.WRITE)
        # An explicit ACL replaces, rather than augments, the creator's access.
        assert not SampleModel().hasAccess(sample, user, AccessType.READ)

    def test_create_without_saving(self, db, user):
        sample = SampleModel().create("Sample E", user, save=False)

        assert "_id" not in sample
        assert SampleModel().findOne({"name": "Sample E"}) is None

    def test_validate_is_a_passthrough(self, db):
        doc = {"name": "anything"}
        assert SampleModel().validate(doc) is doc


@pytest.mark.plugin("sample_tracker")
class TestSampleModelEvents:
    def test_add_event_prepends(self, db, user, sample):
        first = make_event(user, "created")
        second = make_event(user, "shipped")

        SampleModel().add_event(sample, first)
        sample = SampleModel().add_event(sample, second)

        assert [e["eventType"] for e in sample["events"]] == ["shipped", "created"]

    def test_add_event_bumps_updated(self, db, user, sample):
        original = sample["updated"]
        event = make_event(
            user, created=datetime.datetime.now(datetime.UTC)
            + datetime.timedelta(hours=1)
        )

        sample = SampleModel().add_event(sample, event)

        assert sample["updated"] > original

    def test_add_event_persists(self, db, user, sample):
        SampleModel().add_event(sample, make_event(user, "created"))

        reloaded = SampleModel().load(sample["_id"], force=True)
        assert len(reloaded["events"]) == 1

    def test_add_event_without_saving(self, db, user, sample):
        SampleModel().add_event(sample, make_event(user), save=False)

        reloaded = SampleModel().load(sample["_id"], force=True)
        assert reloaded["events"] == []

    def test_remove_event_matches_on_partial_document(self, db, user, sample):
        event = make_event(user, "created", comment="to be removed")
        SampleModel().add_event(sample, event)

        sample = SampleModel().remove_event(
            sample,
            {
                "created": event["created"],
                "creator": event["creator"],
                "eventType": event["eventType"],
            },
            user=user,
        )

        assert sample["events"] == []

    def test_remove_event_leaves_others_alone(self, db, user, sample):
        keep = make_event(user, "created")
        drop = make_event(user, "shipped")
        SampleModel().add_event(sample, keep)
        SampleModel().add_event(sample, drop)

        sample = SampleModel().remove_event(
            sample,
            {
                "created": drop["created"],
                "creator": drop["creator"],
                "eventType": drop["eventType"],
            },
            user=user,
        )

        assert [e["eventType"] for e in sample["events"]] == ["created"]

    def test_remove_event_no_match_is_a_noop(self, db, user, sample):
        event = make_event(user, "created")
        SampleModel().add_event(sample, event)

        sample = SampleModel().remove_event(
            sample,
            {
                "created": event["created"],
                "creator": event["creator"],
                "eventType": "never-happened",
            },
            user=user,
        )

        assert len(sample["events"]) == 1


@pytest.mark.plugin("sample_tracker")
class TestSampleModelQrPayload:
    """What the code encodes, which is the part worth asserting; turning a
    string into pixels is the qrcode library's job."""

    def test_url_is_the_default(self, db, sample):
        assert SampleModel().qr_payload(sample, GIRDER_BASE) == (
            f"{GIRDER_BASE}/#sample/{sample['_id']}/add"
        )
        assert SampleModel().qr_payload(sample, GIRDER_BASE, "url") == (
            SampleModel().qr_payload(sample, GIRDER_BASE)
        )

    def test_igsn_is_the_name_alone(self, db, sample):
        assert SampleModel().qr_payload(sample, GIRDER_BASE, "igsn") == sample["name"]

    def test_igsn_needs_no_base_url(self, db, sample):
        """A ~5mm tag carries the identifier; there is no URL to build."""
        assert SampleModel().qr_payload(sample, None, "igsn") == sample["name"]

    @pytest.mark.parametrize("payload", ["bogus", "hub", "URL", "", None])
    def test_an_unknown_payload_is_rejected(self, db, sample, payload):
        with pytest.raises(ValidationException) as excinfo:
            SampleModel().qr_payload(sample, GIRDER_BASE, payload)

        assert "Unknown QR payload" in str(excinfo.value)


@pytest.mark.plugin("sample_tracker")
class TestSampleModelQrCode:
    def test_qr_code_encodes_the_chosen_payload(self, db, sample):
        assert (
            SampleModel().qr_code(sample, GIRDER_BASE, payload="igsn").getvalue()
            != SampleModel().qr_code(sample, GIRDER_BASE).getvalue()
        )

    def test_qr_code_returns_png(self, db, sample):
        data = SampleModel().qr_code(sample, GIRDER_BASE).getvalue()

        assert data.startswith(PNG_MAGIC)

    def test_qr_code_is_rewound(self, db, sample):
        buf = SampleModel().qr_code(sample, GIRDER_BASE)

        assert buf.tell() == 0

    def test_qr_code_label_changes_the_image(self, db, sample):
        default = SampleModel().qr_code(sample, GIRDER_BASE).getvalue()
        labeled = SampleModel().qr_code(sample, GIRDER_BASE, label="Custom").getvalue()

        assert labeled.startswith(PNG_MAGIC)
        assert labeled != default

    def test_qr_code_is_deterministic(self, db, sample):
        first = SampleModel().qr_code(sample, GIRDER_BASE).getvalue()
        second = SampleModel().qr_code(sample, GIRDER_BASE).getvalue()

        assert first == second

    def test_qr_code_payload_depends_on_the_sample(self, db, user, sample):
        """The encoded payload is ``<base>/#sample/<id>/add``, so two samples
        with the same label still produce different images."""
        other = SampleModel().create(sample["name"], user)

        assert (
            SampleModel().qr_code(sample, GIRDER_BASE).getvalue()
            != SampleModel().qr_code(other, GIRDER_BASE).getvalue()
        )

    def test_qr_code_payload_depends_on_the_base_url(self, db, sample):
        assert (
            SampleModel().qr_code(sample, GIRDER_BASE).getvalue()
            != SampleModel().qr_code(sample, "https://other.example.com").getvalue()
        )
