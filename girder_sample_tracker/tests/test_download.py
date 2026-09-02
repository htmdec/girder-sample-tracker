import csv
import io
import json
import zipfile

import pytest
from girder.constants import AccessType
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


def download_many(server, user, ids, referer=REFERER, isJson=False, **kwargs):
    return server.request(
        path="/sample/download",
        method="POST",
        user=user,
        params={"ids": json.dumps([str(i) for i in ids])},
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

    def test_download_needs_a_referer(self, server, user, sample):
        """The base URL is taken from the Referer header, so it is mandatory."""
        resp = download(server, user, sample["_id"], referer=None, exception=True)

        assertStatus(resp, 500)


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
        assert rows[0] == ["Sample ID", "Sample Name", "Add Event URL"]
        assert sorted(rows[1:], key=lambda r: r[1]) == [
            [
                str(sample["_id"]),
                sample["name"],
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

    def test_bundle_requires_a_referer(self, server, user, samples):
        resp = download_many(
            server, user, [s["_id"] for s in samples], referer=None, exception=True
        )

        assertStatus(resp, 500)
