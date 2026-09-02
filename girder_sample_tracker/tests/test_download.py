import csv
import io
import json
import zipfile

import pytest
from girder.constants import AccessType
from girder.models.setting import Setting
from girder.settings import SettingKey
from pytest_girder.assertions import assertStatus, assertStatusOk
from pytest_girder.utils import getResponseBody

from ..models.sample import Sample as SampleModel
from .conftest import GIRDER_BASE, REFERER

PNG_MAGIC = b"\x89PNG\r\n\x1a\n"


def download(server, user, sample_id, referer=REFERER, isJson=False, **kwargs):
    return server.request(
        path=f"/sample/{sample_id}/download",
        user=user,
        isJson=isJson,
        additionalHeaders=[("Referer", referer)] if referer else None,
        **kwargs,
    )


def download_many(
    server, user, ids, referer=REFERER, isJson=False, params_extra=None, **kwargs
):
    params = {"ids": json.dumps([str(i) for i in ids])}
    params.update(params_extra or {})
    return server.request(
        path="/sample/download",
        method="POST",
        user=user,
        params=params,
        isJson=isJson,
        additionalHeaders=[("Referer", referer)] if referer else None,
        **kwargs,
    )


@pytest.mark.plugin("sample_tracker")
class TestDownloadSample:
    def test_download_returns_a_png(self, server, user, sample):
        resp = download(server, user, sample["_id"])

        assertStatusOk(resp)
        assert getResponseBody(resp, text=False).startswith(PNG_MAGIC)

    def test_download_headers(self, server, user, sample):
        resp = download(server, user, sample["_id"])

        assertStatusOk(resp)
        assert resp.headers["Content-Type"] == "image/png"
        assert sample["name"] in resp.headers["Content-Disposition"]
        assert ".png" in resp.headers["Content-Disposition"]

    def test_download_matches_the_model_output(self, server, user, sample):
        resp = download(server, user, sample["_id"])

        assertStatusOk(resp)
        assert (
            getResponseBody(resp, text=False)
            == SampleModel().qr_code(sample, GIRDER_BASE).getvalue()
        )

    def test_download_requires_read_access(self, server, user2, sample):
        resp = download(server, user2, sample["_id"])

        assertStatus(resp, 403)

    def test_download_without_a_referer_falls_back_to_the_server_root(
        self, server, user, sample
    ):
        """curl, a script or a native client sends no Referer; that used to 500."""
        Setting().set(SettingKey.SERVER_ROOT, "https://girder.example.com")

        resp = download(server, user, sample["_id"], referer=None)

        assertStatusOk(resp)
        assert getResponseBody(resp, text=False) == (
            SampleModel().qr_code(sample, GIRDER_BASE).getvalue()
        )

    def test_the_referer_wins_over_the_server_root(self, server, user, sample):
        """A label should point at the host the person is actually using."""
        Setting().set(SettingKey.SERVER_ROOT, "https://elsewhere.example.com")

        resp = download(server, user, sample["_id"])

        assertStatusOk(resp)
        assert getResponseBody(resp, text=False) == (
            SampleModel().qr_code(sample, GIRDER_BASE).getvalue()
        )

    def test_a_trailing_slash_on_the_server_root_is_dropped(
        self, server, user, sample
    ):
        Setting().set(SettingKey.SERVER_ROOT, f"{GIRDER_BASE}/")

        resp = download(server, user, sample["_id"], referer=None)

        assertStatusOk(resp)
        assert getResponseBody(resp, text=False) == (
            SampleModel().qr_code(sample, GIRDER_BASE).getvalue()
        )

    def test_no_referer_and_no_server_root_explains_itself(
        self, server, user, sample
    ):
        resp = download(server, user, sample["_id"], referer=None, isJson=True)

        assertStatus(resp, 400)
        assert "core.server_root" in resp.json["message"]

    def test_an_igsn_label_needs_no_base_url_at_all(self, server, user, sample):
        """The tag carries the identifier, so nothing has to be configured."""
        resp = download(server, user, sample["_id"], referer=None, params={"payload": "igsn"})

        assertStatusOk(resp)
        assert getResponseBody(resp, text=False) == (
            SampleModel().qr_code(sample, None, payload="igsn").getvalue()
        )

    def test_the_payload_can_be_chosen(self, server, user, sample):
        url_label = download(server, user, sample["_id"])
        igsn_label = download(server, user, sample["_id"], params={"payload": "igsn"})

        assertStatusOk(url_label)
        assertStatusOk(igsn_label)
        body = getResponseBody(igsn_label, text=False)
        assert body.startswith(PNG_MAGIC)
        assert body != getResponseBody(url_label, text=False)
        assert body == SampleModel().qr_code(sample, GIRDER_BASE, payload="igsn").getvalue()

    def test_asking_for_the_default_explicitly_changes_nothing(
        self, server, user, sample
    ):
        resp = download(server, user, sample["_id"], params={"payload": "url"})

        assertStatusOk(resp)
        assert getResponseBody(resp, text=False) == (
            SampleModel().qr_code(sample, GIRDER_BASE).getvalue()
        )

    def test_an_unknown_payload_is_rejected(self, server, user, sample):
        """Silently falling back to a URL would print a box of wrong labels."""
        resp = download(server, user, sample["_id"], params={"payload": "bogus"}, isJson=True)

        assertStatus(resp, 400)
        assert "payload" in resp.json["message"]

    def test_headers_do_not_depend_on_the_payload(self, server, user, sample):
        resp = download(server, user, sample["_id"], params={"payload": "igsn"})

        assertStatusOk(resp)
        assert resp.headers["Content-Type"] == "image/png"
        assert f"{sample['name']}.png" in resp.headers["Content-Disposition"]


@pytest.mark.plugin("sample_tracker")
class TestDownloadSamples:
    def _zip(self, resp):
        return zipfile.ZipFile(io.BytesIO(getResponseBody(resp, text=False)))

    def test_bundle_contains_a_png_per_sample_and_a_csv(self, server, user, samples):
        resp = download_many(server, user, [s["_id"] for s in samples])

        assertStatusOk(resp)
        names = self._zip(resp).namelist()
        assert sorted(names) == ["Alpha.png", "Beta.png", "Gamma.png", "samples.csv"]

    def test_bundle_headers(self, server, user, samples):
        resp = download_many(server, user, [s["_id"] for s in samples])

        assertStatusOk(resp)
        assert resp.headers["Content-Type"] == "application/zip"
        assert "samples.zip" in resp.headers["Content-Disposition"]

    def test_bundled_images_are_pngs(self, server, user, samples):
        resp = download_many(server, user, [s["_id"] for s in samples])

        assertStatusOk(resp)
        archive = self._zip(resp)
        for sample in samples:
            assert archive.read(f"{sample['name']}.png") == (
                SampleModel().qr_code(sample, GIRDER_BASE).getvalue()
            )

    def test_csv_lists_every_sample(self, server, user, samples):
        resp = download_many(server, user, [s["_id"] for s in samples])

        assertStatusOk(resp)
        rows = list(csv.reader(io.StringIO(self._zip(resp).read("samples.csv").decode())))
        assert rows[0] == ["Sample ID", "Sample Name", "Add Event URL", "QR Payload"]
        assert sorted(rows[1:], key=lambda r: r[1]) == [
            [
                str(sample["_id"]),
                sample["name"],
                f"{GIRDER_BASE}/#sample/{sample['_id']}/add",
                f"{GIRDER_BASE}/#sample/{sample['_id']}/add",
            ]
            for sample in sorted(samples, key=lambda s: s["name"])
        ]

    def test_bundle_of_one(self, server, user, sample):
        resp = download_many(server, user, [sample["_id"]])

        assertStatusOk(resp)
        assert sorted(self._zip(resp).namelist()) == [
            f"{sample['name']}.png",
            "samples.csv",
        ]

    def test_bundle_of_nothing_is_just_the_csv(self, server, user):
        resp = download_many(server, user, [])

        assertStatusOk(resp)
        assert self._zip(resp).namelist() == ["samples.csv"]

    def test_inaccessible_sample_is_rejected(self, server, user, user2, samples):
        """A sample the caller cannot read fails the pre-flight check as a 403."""
        SampleModel().setUserAccess(samples[0], user2, AccessType.READ, save=True)

        resp = download_many(server, user2, [s["_id"] for s in samples], isJson=True)

        assertStatus(resp, 403)

    def test_unknown_sample_is_rejected(self, server, user, samples):
        ids = [str(samples[0]["_id"]), "000000000000000000000000"]

        resp = download_many(server, user, ids, isJson=True)

        assertStatus(resp, 400)
        assert "not found or access denied" in resp.json["message"]

    def test_bundle_without_a_referer_falls_back_to_the_server_root(
        self, server, user, samples
    ):
        Setting().set(SettingKey.SERVER_ROOT, GIRDER_BASE)

        resp = download_many(server, user, [s["_id"] for s in samples], referer=None)

        assertStatusOk(resp)
        archive = self._zip(resp)
        assert sorted(archive.namelist()) == [
            "Alpha.png",
            "Beta.png",
            "Gamma.png",
            "samples.csv",
        ]
        assert archive.read("Alpha.png") == (
            SampleModel().qr_code(samples[0], GIRDER_BASE).getvalue()
        )

    def test_bundle_with_no_referer_and_no_server_root_explains_itself(
        self, server, user, samples
    ):
        resp = download_many(
            server, user, [s["_id"] for s in samples], referer=None, isJson=True
        )

        assertStatus(resp, 400)
        assert "core.server_root" in resp.json["message"]

    def test_bundled_igsn_labels(self, server, user, samples):
        resp = download_many(
            server, user, [s["_id"] for s in samples], params_extra={"payload": "igsn"}
        )

        assertStatusOk(resp)
        archive = self._zip(resp)
        for sample in samples:
            assert archive.read(f"{sample['name']}.png") == (
                SampleModel().qr_code(sample, GIRDER_BASE, payload="igsn").getvalue()
            )

    def test_the_csv_reports_what_was_printed(self, server, user, samples):
        resp = download_many(
            server, user, [s["_id"] for s in samples], params_extra={"payload": "igsn"}
        )

        assertStatusOk(resp)
        rows = list(csv.reader(io.StringIO(self._zip(resp).read("samples.csv").decode())))
        assert rows[0] == ["Sample ID", "Sample Name", "Add Event URL", "QR Payload"]
        # The add-event URL is still there, and useful, even though the tags
        # carry the identifier instead.
        assert sorted(rows[1:], key=lambda r: r[1]) == [
            [
                str(sample["_id"]),
                sample["name"],
                f"{GIRDER_BASE}/#sample/{sample['_id']}/add",
                sample["name"],
            ]
            for sample in sorted(samples, key=lambda s: s["name"])
        ]

    def test_an_unknown_payload_is_rejected(self, server, user, samples):
        resp = download_many(
            server,
            user,
            [s["_id"] for s in samples],
            params_extra={"payload": "bogus"},
            isJson=True,
        )

        assertStatus(resp, 400)
        assert "payload" in resp.json["message"]
