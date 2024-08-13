import datetime

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
                "updated",
                "name",
                "events",
            ),
        )

    def validate(self, doc):
        return doc

    def create(self, name, creator, description=None, save=True):
        now = datetime.datetime.utcnow()

        sample = {
            "name": name,
            "creator": creator["_id"],
            "created": now,
            "description": description,
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
