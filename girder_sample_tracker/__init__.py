import os
from girder.plugin import GirderPlugin, registerPluginStaticContent
from girder.utility.model_importer import ModelImporter
from .rest.sample import Sample
from .models.sample import Sample as SampleModel


class SampleTrackerPlugin(GirderPlugin):
    DISPLAY_NAME = "Sample Tracker"

    def load(self, info):
        ModelImporter.registerModel("sample", SampleModel, plugin="sample_tracker")
        info["apiRoot"].sample = Sample()
        registerPluginStaticContent(
            plugin="sample_tracker",
            css=["/style.css"],
            js=["/girder-plugin-sample-tracker.umd.cjs"],
            staticDir=os.path.join(os.path.dirname(__file__), "web_client", "dist"),
            tree=info["serverRoot"],
        )
