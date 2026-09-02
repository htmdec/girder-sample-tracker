from pathlib import Path

from girder import events
from girder.models.setting import Setting
from girder.plugin import GirderPlugin, registerPluginStaticContent
from girder.utility.model_importer import ModelImporter

from .models.sample import Sample as SampleModel
from .rest.sample import Sample

# Importing this registers its setting validator, which is what keeps
# sample_tracker.event_types a list of distinct non-empty strings.
from .settings import PluginSettings

# Settings a client may read before it has a user: the event-type vocabulary
# is what a picker is built from, and every client already fetches this
# payload at startup, so it does not need a route of its own.
PUBLIC_SETTINGS = (PluginSettings.EVENT_TYPES,)


def add_public_settings(event):
    """Add this plugin's public settings to the response being returned."""
    settings = event.info["returnVal"]
    settings.update({key: Setting().get(key) for key in PUBLIC_SETTINGS})


class SampleTrackerPlugin(GirderPlugin):
    DISPLAY_NAME = "Sample Tracker"

    def load(self, info):
        ModelImporter.registerModel("sample", SampleModel, plugin="sample_tracker")
        events.bind(
            "rest.get.system/public_settings.after",
            "sample_tracker",
            add_public_settings,
        )
        info["apiRoot"].sample = Sample()
        registerPluginStaticContent(
            plugin="sample_tracker",
            css=["/style.css"],
            js=["/girder-plugin-sample-tracker.umd.cjs"],
            staticDir=Path(__file__).parent / "web_client" / "dist",
            tree=info["serverRoot"],
        )
