"""The instance-wide event-type vocabulary."""

import json

import pytest
from girder.exceptions import ValidationException
from girder.models.setting import Setting
from pytest_girder.assertions import assertStatus, assertStatusOk

from ..models.sample import Sample as SampleModel
from ..settings import PluginSettings
from .conftest import add_event, add_multisample_event


def public_settings(server, user=None):
    """GET /system/public_settings, which every client already fetches."""
    return server.request(path="/system/public_settings", method="GET", user=user)


def set_event_types(server, admin, event_types):
    """PUT /system/setting, the way an administrator would."""
    return server.request(
        path="/system/setting",
        method="PUT",
        user=admin,
        params={
            "key": PluginSettings.EVENT_TYPES,
            "value": json.dumps(event_types),
        },
    )


@pytest.mark.plugin("sample_tracker")
class TestEventTypeSettings:
    def test_the_vocabulary_is_empty_by_default(self, server, db):
        resp = public_settings(server)

        assertStatusOk(resp)
        assert resp.json[PluginSettings.EVENT_TYPES] == []

    def test_an_admin_can_fill_it_in(self, server, admin):
        assertStatusOk(set_event_types(server, admin, ["forging", "XRD", "shipped"]))

        resp = public_settings(server, admin)

        assertStatusOk(resp)
        assert resp.json[PluginSettings.EVENT_TYPES] == ["forging", "XRD", "shipped"]

    def test_it_is_readable_without_logging_in(self, server, admin):
        """A client needs the picker before it has a user in hand."""
        assertStatusOk(set_event_types(server, admin, ["forging"]))

        resp = public_settings(server)

        assertStatusOk(resp)
        assert resp.json[PluginSettings.EVENT_TYPES] == ["forging"]

    def test_it_is_published_under_its_settings_key(self, server, db):
        """Clients read this key by name, so pin it."""
        resp = public_settings(server)

        assertStatusOk(resp)
        assert "sample_tracker.event_types" in resp.json

    def test_the_core_settings_are_still_there(self, server, db):
        """The hook adds to the payload rather than replacing it."""
        resp = public_settings(server)

        assertStatusOk(resp)
        assert "core.brand_name" in resp.json

    def test_a_regular_user_cannot_change_it(self, server, user):
        resp = set_event_types(server, user, ["forging"])

        assertStatus(resp, 403)

    def test_surrounding_whitespace_is_trimmed(self, server, admin, db):
        Setting().set(PluginSettings.EVENT_TYPES, ["  forging  ", "XRD\n"])

        assert Setting().get(PluginSettings.EVENT_TYPES) == ["forging", "XRD"]

    @pytest.mark.parametrize(
        "value,message",
        [
            ("forging", "must be a list"),
            ({"forging": True}, "must be a list"),
            (["forging", 7], "must be strings"),
            (["forging", None], "must be strings"),
            (["forging", ""], "must not be empty"),
            (["forging", "   "], "must not be empty"),
            (["forging", "forging"], "must not repeat"),
            (["forging", " forging"], "must not repeat"),
        ],
    )
    def test_bad_vocabularies_are_rejected(self, db, value, message):
        with pytest.raises(ValidationException) as excinfo:
            Setting().set(PluginSettings.EVENT_TYPES, value)

        assert message in str(excinfo.value)
        assert Setting().get(PluginSettings.EVENT_TYPES) == []

    def test_rejection_reaches_the_admin_as_a_400(self, server, admin):
        resp = set_event_types(server, admin, ["forging", "forging"])

        assertStatus(resp, 400)
        assert "must not repeat" in resp.json["message"]


@pytest.mark.plugin("sample_tracker")
class TestVocabularyIsNotAConstraint:
    """The write path must not start consulting the global list."""

    def test_an_unlisted_type_is_still_accepted(self, server, admin, user):
        assertStatusOk(set_event_types(server, admin, ["forging", "XRD"]))
        sample = SampleModel().create("Unconstrained", user)

        resp = add_event(server, user, sample["_id"], "improvised")

        assertStatusOk(resp)
        assert resp.json["events"][0]["eventType"] == "improvised"

    def test_an_unlisted_type_is_accepted_in_bulk_too(self, server, admin, user):
        assertStatusOk(set_event_types(server, admin, ["forging"]))
        sample = SampleModel().create("Unconstrained", user)

        resp = add_multisample_event(server, user, [sample["_id"]], "improvised")

        assertStatusOk(resp)
        assert resp.json["processed"] == 1
        assert resp.json["failed"] == 0

    def test_a_sample_keeps_its_own_narrower_list(self, server, admin, user):
        """The global list is a fallback, not a widening of a sample's own."""
        assertStatusOk(set_event_types(server, admin, ["forging", "shipped"]))
        sample = SampleModel().create("Strict", user, eventTypes=["forging"])

        resp = add_multisample_event(server, user, [sample["_id"]], "shipped")

        assertStatusOk(resp)
        assert resp.json["failed"] == 1
        assert "not allowed" in resp.json["failures"][0]["reason"]
