import csv
import datetime
import io
import math
from urllib.parse import urlparse

import cherrypy
import dateutil.parser
from girder.api import access
from girder.api.describe import Description, autoDescribeRoute
from girder.api.rest import (
    Resource,
    filtermodel,
    setContentDisposition,
    setResponseHeader,
)
from girder.constants import AccessType, SortDir, TokenScope
from girder.exceptions import RestException, ValidationException
from girder.models.user import User
from girder.utility import ziputil
from girder.utility.progress import ProgressContext

from ..models.sample import Sample as SampleModel


class Sample(Resource):
    def __init__(self):
        super(Sample, self).__init__()
        self.resourceName = "sample"
        self.route("GET", (), self.list_samples)
        self.route("DELETE", (), self.delete_samples)
        self.route("PUT", ("access",), self.bulk_update_access)
        self.route("GET", (":id", "download"), self.download_sample)
        self.route("POST", ("download",), self.download_samples)
        self.route("GET", (":id",), self.get_sample)
        self.route("PUT", (":id",), self.update_sample)
        self.route("POST", (), self.create_sample)
        self.route("POST", ("event",), self.create_multisample_event)
        self.route("DELETE", (":id",), self.delete_sample)
        self.route("GET", (":id", "access"), self.get_access)
        self.route("PUT", (":id", "access"), self.update_access)
        self.route("POST", (":id", "event"), self.create_event)
        self.route("DELETE", (":id", "event"), self.delete_event)

    @access.public
    @autoDescribeRoute(
        Description("List samples")
        .param("query", "A regular expression to filter sample names", required=False)
        .pagingParams(defaultSort="name", defaultSortDir=SortDir.DESCENDING)
    )
    @filtermodel(model="sample", plugin="sample_tracker")
    def list_samples(self, query, limit, offset, sort):
        if query:
            query = {"name": {"$regex": query, "$options": "i"}}
        else:
            query = {}

        return SampleModel().findWithPermissions(
            query=query,
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
        sample["updated"] = datetime.datetime.now(datetime.UTC)
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
        .jsonParam(
            "access", "The access control list as a JSON object", requireObject=False
        )
    )
    @filtermodel(model="sample", plugin="sample_tracker")
    def create_sample(self, name, description, eventTypes, batchSize, access):
        if batchSize is None:
            batchSize = 1
        if batchSize < 1 or batchSize > 64:
            raise ValidationException(
                "Batch size must be at least 1, but no more than 64."
            )

        if not eventTypes:
            eventTypes = []
        user = self.getCurrentUser()
        samples = []
        if batchSize > 1:
            if "{number" not in name:
                name = name + "{number:0" + str(math.ceil(math.log10(batchSize))) + "d}"

            try:
                name.format(number=1)
            except KeyError:
                raise ValidationException(
                    "Name must contain a '{number}' placeholder for batch creation."
                )

            for i in range(batchSize):
                sample = SampleModel().create(
                    name.format(number=i + 1),
                    user,
                    description=description,
                    eventTypes=eventTypes,
                    access=access,
                )
                samples.append(sample)
        else:
            samples.append(
                SampleModel().create(
                    name,
                    user,
                    description=description,
                    eventTypes=eventTypes,
                    access=access,
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
        Description("Delete multiple samples")
        .jsonParam(
            "ids",
            "The IDs of the samples to delete",
            requireArray=True,
        )
        .param(
            "progress",
            "Whether to record progress on this task.",
            default=False,
            required=False,
            dataType="boolean",
        )
    )
    def delete_samples(self, ids, progress):
        user = self.getCurrentUser()
        total = len(ids)
        with ProgressContext(
            progress,
            user=user,
            title="Deleting resources",
            message="Calculating size...",
        ) as ctx:
            ctx.update(total=total)
            current = 0
            for sample_id in ids:
                doc = SampleModel().load(
                    sample_id, user=user, level=AccessType.ADMIN, exc=True
                )
                SampleModel().remove(doc, progress=ctx)
                if progress:
                    current += 1
                    if ctx.progress["data"]["current"] != current:
                        ctx.update(current=current, message="Deleted sample")

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

    @access.user(scope=TokenScope.DATA_OWN)
    @autoDescribeRoute(
        Description("Update the access control list for multiple samples")
        .jsonParam(
            "ids",
            "The IDs of the samples to update",
            requireArray=True,
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
    def bulk_update_access(self, ids, access, publicFlags, public):
        user = self.getCurrentUser()
        for sample_id in ids:
            doc = SampleModel().load(
                sample_id, user=user, level=AccessType.ADMIN, exc=True
            )
            sample = SampleModel().setAccessList(doc, access, save=True, user=user)
        return sample

    @access.user
    @autoDescribeRoute(
        Description("Create an event for multiple samples")
        .jsonParam(
            "ids", "The IDs of the samples to create an event for", requireArray=True
        )
        .param("eventType", "The type of the event", required=True)
        .param("location", "The location of the event", required=False)
        .param("comment", "Extra comment about the event", required=False)
    )
    def create_multisample_event(self, ids, eventType, location, comment):
        user = self.getCurrentUser()
        if not ids:
            raise ValidationException("At least one sample ID must be provided.")

        event = {
            "comment": comment,
            "created": datetime.datetime.now(datetime.UTC),
            "creator": user["_id"],
            "creatorName": f"{user['firstName']} {user['lastName']}",
            "eventType": eventType,
            "location": location,
        }

        samples = []
        failed = 0
        for sample_id in ids:
            try:
                sample = SampleModel().load(
                    sample_id, user=user, level=AccessType.WRITE, exc=True
                )
                eventTypes = sample.get("eventTypes", [])
                if eventTypes and eventType not in eventTypes:
                    raise ValidationException(
                        f"Event type '{eventType}' is not allowed for sample {sample_id}."
                    )
                samples.append(SampleModel().add_event(sample, event))
            except Exception:
                failed += 1
        return {"processed": len(samples), "failed": failed}

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
            "created": datetime.datetime.now(datetime.UTC),
            "creator": user["_id"],
            "creatorName": f"{user['firstName']} {user['lastName']}",
            "eventType": eventType,
            "location": location,
        }
        return SampleModel().add_event(sample, event)

    @access.user
    @autoDescribeRoute(
        Description("Delete an event for a sample")
        .modelParam(
            "id", "The ID of the sample", model=SampleModel, level=AccessType.ADMIN
        )
        .jsonParam("event", "Event to remove", required=True, requireObject=True)
    )
    @filtermodel(model="sample", plugin="sample_tracker")
    def delete_event(self, sample, event):
        creator = User().load(event["creator"], force=True)
        processed_event = {
            "created": dateutil.parser.parse(event.get("created")),
            "creator": creator["_id"],
            "eventType": event.get("eventType"),
        }
        return SampleModel().remove_event(
            sample, processed_event, user=self.getCurrentUser()
        )

    @access.public(scope=TokenScope.DATA_READ, cookie=True)
    @autoDescribeRoute(
        Description("Download a sample").modelParam(
            "id", "The ID of the sample", model=SampleModel, level=AccessType.READ
        )
    )
    def download_sample(self, sample):
        url = urlparse(cherrypy.request.headers["Referer"])
        girder_base = f"{url.scheme}://{url.netloc}"
        qr_img = SampleModel().qr_code(sample, girder_base)
        setResponseHeader("Content-Type", "image/png")
        setContentDisposition(f"{sample['name']}.png")

        def stream():
            yield from qr_img

        return stream

    @access.public(scope=TokenScope.DATA_READ, cookie=True)
    @autoDescribeRoute(
        Description("Download QR codes for a list of samples").jsonParam(
            "ids",
            "The IDs of the samples to download",
            requireArray=True,
        )
    )
    def download_samples(self, ids):
        user = self.getCurrentUser()
        url = urlparse(cherrypy.request.headers["Referer"])
        girder_base = f"{url.scheme}://{url.netloc}"
        for sample_id in ids:
            if not SampleModel().load(sample_id, user=user, level=AccessType.READ):
                raise RestException(f"Sample {sample_id} not found or access denied.")
        setResponseHeader("Content-Type", "application/zip")
        setContentDisposition("samples.zip")

        def stream():
            _zip = ziputil.ZipGenerator()
            csv_data = io.StringIO()
            csv_writer = csv.writer(csv_data)
            csv_writer.writerow(["Sample ID", "Sample Name", "Add Event URL"])
            for sample_id in ids:
                doc = SampleModel().load(sample_id, user=user, level=AccessType.READ)
                qr_img = SampleModel().qr_code(doc, girder_base)
                csv_writer.writerow(
                    [
                        str(doc["_id"]),
                        doc["name"],
                        f"{girder_base}/#sample/{doc['_id']}/add",
                    ]
                )

                def qr_stream():
                    yield qr_img.getvalue()

                yield from _zip.addFile(qr_stream, f"{doc['name']}.png")

            def csv_stream():
                csv_data.seek(0)
                yield csv_data.getvalue()

            yield from _zip.addFile(csv_stream, "samples.csv")
            yield _zip.footer()

        return stream
