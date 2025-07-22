import datetime
import io

import cairosvg
import qrcode
from girder.constants import AccessType
from girder.models.model_base import AccessControlledModel
from qrcode.compat.etree import ET
from qrcode.image.svg import SvgPathFillImage


class Sample(AccessControlledModel):
    def initialize(self):
        self.name = "sample"
        self.ensureIndices(["name"])

        self.exposeFields(
            level=AccessType.READ,
            fields=(
                "_id",
                "created",
                "creator",
                "description",
                "eventTypes",
                "updated",
                "name",
                "events",
            ),
        )

    def validate(self, doc):
        return doc

    def create(
        self, name, creator, description=None, eventTypes=None, access=None, save=True
    ):
        now = datetime.datetime.now(datetime.UTC)

        sample = {
            "name": name,
            "creator": creator["_id"],
            "created": now,
            "description": description,
            "eventTypes": eventTypes or [],
            "updated": now,
            "events": [],
        }

        if access is not None:
            self.setAccessList(sample, access, save=False, user=creator)
        else:
            self.setUserAccess(sample, user=creator, level=AccessType.ADMIN, save=False)
        if save:
            sample = self.save(sample)

        return sample

    def add_event(self, sample, event, save=True):
        sample["events"].insert(0, event)
        sample["updated"] = event["created"]

        if save:
            sample = self.save(sample)

        return sample

    def remove_event(self, sample, event, user=None):
        self.collection.update_one(
            {
                "_id": sample["_id"],
            },
            {"$pull": {"events": {**event}}},
        )
        return self.load(sample["_id"], user=user)

    def qr_code(self, sample, url):
        buf = io.BytesIO()
        qr = qrcode.QRCode(
            version=8,
            error_correction=qrcode.constants.ERROR_CORRECT_H,
            border=10,
            image_factory=SvgPathFillImage,
        )
        qr.add_data(f"{url}/#sample/{sample['_id']}/add")
        qr.make(fit=True)

        img = qr.make_image(fill_color="black", back_color="white")
        text = ET.SubElement(
            img._img,
            "text",
            {
                "x": "50%",
                "y": "93%",
                "dominant-baseline": "middle",
                "text-anchor": "middle",
                "font-size": "5",
                "fill": "black",
            },
        )
        text.text = sample["name"]
        cairosvg.svg2png(
            bytestring=img.to_string(encoding="unicode"), write_to=buf, dpi=300
        )
        buf.seek(0)
        return buf
