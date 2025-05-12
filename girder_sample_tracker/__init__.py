from pathlib import Path

from girder.plugin import GirderPlugin, registerPluginStaticContent
from girder.utility.model_importer import ModelImporter

from .models.sample import Sample as SampleModel
from .rest.sample import Sample


class SampleTrackerPlugin(GirderPlugin):
    DISPLAY_NAME = "Sample Tracker"

    def load(self, info):
        ModelImporter.registerModel("sample", SampleModel, plugin="sample_tracker")
        info["apiRoot"].sample = Sample()
        registerPluginStaticContent(
            plugin="sample_tracker",
            css=["/style.css"],
            js=["/girder-plugin-sample-tracker.umd.cjs"],
            staticDir=Path(__file__).parent / "web_client" / "dist",
            tree=info["serverRoot"],
        )
