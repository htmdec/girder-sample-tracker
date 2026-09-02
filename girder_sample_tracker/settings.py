from girder.exceptions import ValidationException
from girder.settings import SettingDefault
from girder.utility import setting_utilities


class PluginSettings:
    EVENT_TYPES = "sample_tracker.event_types"


SettingDefault.defaults.update(
    {
        # Empty is how every deployment behaves today: with nothing to offer,
        # a client falls back to free text.
        PluginSettings.EVENT_TYPES: [],
    }
)


@setting_utilities.validator(PluginSettings.EVENT_TYPES)
def validate_event_types(doc):
    """The instance-wide vocabulary a client offers when a sample declares none.

    A suggestion list, not a constraint: nothing on the write path consults it.
    """
    value = doc["value"]
    if not isinstance(value, list):
        raise ValidationException("Event types must be a list.", "value")
    for event_type in value:
        if not isinstance(event_type, str):
            raise ValidationException(
                f"Event types must be strings, not {type(event_type).__name__}.",
                "value",
            )

    # Normalized before the duplicate check, so that "anneal" and " anneal "
    # cannot both end up in the same picker.
    value = [event_type.strip() for event_type in value]
    if not all(value):
        raise ValidationException("Event types must not be empty.", "value")
    if len(set(value)) != len(value):
        raise ValidationException("Event types must not repeat.", "value")
    doc["value"] = value
