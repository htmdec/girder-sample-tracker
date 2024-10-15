import datetime
import math

from girder.api import access
from girder.api.describe import Description, autoDescribeRoute
from girder.api.rest import Resource, filtermodel
from girder.constants import AccessType, SortDir, TokenScope
from girder.exceptions import ValidationException

from ..models.sample import Sample as SampleModel


class Sample(Resource):
    def __init__(self):
        super(Sample, self).__init__()
        self.resourceName = "sample"
        self.route("GET", (), self.list_samples)
        self.route("GET", (":id",), self.get_sample)
        self.route("PUT", (":id",), self.update_sample)
        self.route("POST", (), self.create_sample)
        self.route("DELETE", (":id",), self.delete_sample)
        self.route("GET", (":id", "access"), self.get_access)
        self.route("PUT", (":id", "access"), self.update_access)
        self.route("POST", (":id", "event"), self.create_event)

    @access.public
    @autoDescribeRoute(
        Description("List samples").pagingParams(
            defaultSort="name", defaultSortDir=SortDir.DESCENDING
        )
    )
    @filtermodel(model="sample", plugin="sample_tracker")
    def list_samples(self, limit, offset, sort):
        return SampleModel().findWithPermissions(
            query={},
            offset=offset,
            limit=limit,
            sort=sort,
            user=self.getCurrentUser(),
            level=AccessType.READ,
            fields={"events": 0},
        )

    @access.public
    @autoDescribeRoute(
        Description("Get a sample by ID").modelParam(
            "id", "The ID of the sample", model=SampleModel, level=AccessType.READ
        )
    )
    @filtermodel(model="sample", plugin="sample_tracker")
    def get_sample(self, sample):
        return sample

    @access.user(scope=TokenScope.DATA_OWN)
    @autoDescribeRoute(
        Description("Update a sample")
        .modelParam(
            "id", "The ID of the sample", model=SampleModel, level=AccessType.ADMIN
        )
        .param("name", "The name of the sample", required=False)
        .param("description", "The description of the sample", required=False)
        .jsonParam(
            "eventTypes",
            "The event types for the sample",
            required=False,
            requireArray=True,
        )
    )
    @filtermodel(model="sample", plugin="sample_tracker")
    def update_sample(self, sample, name, description, eventTypes):
        if name:
            sample["name"] = name
        if description:
            sample["description"] = description
        if eventTypes != sample.get("eventTypes", []):
            sample["eventTypes"] = eventTypes
        sample["updated"] = datetime.datetime.utcnow()
        return SampleModel().save(sample)

    @access.user
    @autoDescribeRoute(
        Description("Create a sample")
        .param("name", "The name of the sample", required=True)
        .param("description", "The description of the sample", required=False)
        .jsonParam(
            "eventTypes",
            "The event types for the sample",
            required=False,
            requireArray=True,
        )
        .param(
            "batchSize",
            "The size of the batch. Default 1. Cannot be less than 1 and greater than 64.",
            required=False,
            dataType="integer",
        )
    )
    @filtermodel(model="sample", plugin="sample_tracker")
    def create_sample(self, name, description, eventTypes, batchSize):
        if batchSize < 1 or batchSize > 64:
            raise ValidationException(
                "Batch size must be at least 1, but no more than 64."
            )
        if not eventTypes:
            eventTypes = []
        user = self.getCurrentUser()
        samples = []
        if batchSize > 1:
            format_str = "{name}{i:0" + str(math.ceil(math.log10(batchSize))) + "d}"
            for i in range(batchSize):
                sample = SampleModel().create(
                    format_str.format(name=name, i=i),
                    user,
                    description=description,
                    eventTypes=eventTypes,
                )
                samples.append(sample)
        else:
            samples.append(
                SampleModel().create(
                    name, user, description=description, eventTypes=eventTypes
                )
            )
        return samples[0]

    @access.user
    @autoDescribeRoute(
        Description("Delete a sample").modelParam(
            "id", "The ID of the sample", model=SampleModel, level=AccessType.WRITE
        )
    )
    @filtermodel(model="sample", plugin="sample_tracker")
    def delete_sample(self, sample):
        SampleModel().remove(sample)

    @access.user
    @autoDescribeRoute(
        Description("Get the access control list for a sample").modelParam(
            "id", "The ID of the sample", model=SampleModel, level=AccessType.ADMIN
        )
    )
    def get_access(self, sample):
        return SampleModel().getFullAccessList(sample)

    @access.user(scope=TokenScope.DATA_OWN)
    @autoDescribeRoute(
        Description("Update the access control list for a sample")
        .modelParam(
            "id", "The ID of the sample", model=SampleModel, level=AccessType.ADMIN
        )
        .jsonParam(
            "access", "The access control list as a JSON object", requireObject=True
        )
        .jsonParam(
            "publicFlags",
            "Public access control flags",
            requireArray=True,
            required=False,
        )
        .param(
            "public",
            "Whether the resource should be publicly visible",
            dataType="boolean",
            required=False,
        )
        .errorResponse("ID was invalid.")
        .errorResponse("Admin access was denied for the sample.", 403)
    )
    def update_access(self, sample, access, publicFlags, public):
        return SampleModel().setAccessList(
            sample, access, save=True, user=self.getCurrentUser()
        )

    @access.user
    @autoDescribeRoute(
        Description("Create an event for a sample")
        .modelParam(
            "id", "The ID of the sample", model=SampleModel, level=AccessType.WRITE
        )
        .param("eventType", "The type of the event", required=True)
        .param("location", "The location of the event", required=False)
        .param("comment", "Extra comment about the event", required=False)
    )
    @filtermodel(model="sample", plugin="sample_tracker")
    def create_event(self, sample, eventType, location, comment):
        user = self.getCurrentUser()
        event = {
            "comment": comment,
            "created": datetime.datetime.utcnow(),
            "creator": user["_id"],
            "creatorName": f"{user['firstName']} {user['lastName']}",
            "eventType": eventType,
            "location": location,
        }
        return SampleModel().add_event(sample, event)
