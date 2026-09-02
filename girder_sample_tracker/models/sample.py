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
        # Sparse, because only events written by a client that cares about
        # retry safety carry a clientEventId.
        self.ensureIndex(("events.clientEventId", {"sparse": True}))

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
        """Prepend ``event`` to ``sample``'s event list.

        An event carrying a ``clientEventId`` is written with a conditional
        update, so a client that retries a request whose response it never saw
        cannot end up with two copies of the same event. That path always
        writes, regardless of ``save``. Events without a ``clientEventId``
        keep the original unconditional behavior.
        """
        client_event_id = event.get("clientEventId")
        if client_event_id is not None:
            self.collection.update_one(
                {
                    "_id": sample["_id"],
                    "events.clientEventId": {"$ne": client_event_id},
                },
                {
                    "$push": {"events": {"$each": [event], "$position": 0}},
                    "$set": {"updated": event["created"]},
                },
            )
            # No match means an event with this clientEventId is already
            # there, which is what a successful retry looks like. Either way
            # the caller should see what is stored.
            return self.load(sample["_id"], force=True, exc=True)

        sample["events"].insert(0, event)
        sample["updated"] = event["created"]

        if save:
            sample = self.save(sample)

        return sample

    def event_count(self, sample):
        """How many events a sample has, without reading them."""
        counted = self.collection.aggregate(
            [
                {"$match": {"_id": sample["_id"]}},
                {"$project": {"count": {"$size": {"$ifNull": ["$events", []]}}}},
            ]
        )
        doc = next(counted, None)
        return doc["count"] if doc else 0

    def list_events(self, sample, offset=0, limit=0, newest_first=True):
        """Read one window of a sample's events, sliced by the database.

        The point is not to load an event history that grows for the life of a
        physical sample just to hand back ten of them.

        Events are stored newest-first, so a newest-first page is that window
        of the stored array. Reading oldest-first, or reading everything from
        an offset with no limit, needs to know how many there are: that is one
        extra count, which is still cheaper than reading the whole array.
        """
        if newest_first and limit > 0:
            start, count = offset, limit
        else:
            end = self.event_count(sample) - offset
            if newest_first:
                start, count = offset, end
            else:
                start = max(0, end - limit) if limit > 0 else 0
                count = end - start
        if count <= 0:
            return []

        doc = self.collection.find_one(
            {"_id": sample["_id"]},
            {"events": {"$slice": [start, count]}},
        )
        events = (doc or {}).get("events", [])
        return events if newest_first else list(reversed(events))

    def remove_event(self, sample, event, user=None):
        self.collection.update_one(
            {
                "_id": sample["_id"],
            },
            {"$pull": {"events": {**event}}},
        )
        return self.load(sample["_id"], user=user)

    def qr_code(self, sample, url, label=None):
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
        if label is None:
            label = sample["name"]
        text.text = label
        cairosvg.svg2png(
            bytestring=img.to_string(encoding="unicode"), write_to=buf, dpi=300
        )
        buf.seek(0)
        return buf
