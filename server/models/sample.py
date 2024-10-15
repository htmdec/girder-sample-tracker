import datetime
import io

import qrcode
from girder.constants import AccessType
from girder.models.model_base import AccessControlledModel


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

    def create(self, name, creator, description=None, eventTypes=None, save=True):
        now = datetime.datetime.utcnow()

        sample = {
            "name": name,
            "creator": creator["_id"],
            "created": now,
            "description": description,
            "eventTypes": eventTypes or [],
            "updated": now,
            "events": [],
        }

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

    def qr_code(self, sample, url):
        buf = io.BytesIO()
        qr = qrcode.QRCode(
            version=2,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        qr.add_data(f"{url}/#sample/{sample['_id']}/add")
        qr.make(fit=True)

        img = qr.make_image(fill_color="black", back_color="white")
        img.save(buf, format="PNG")
        return buf
