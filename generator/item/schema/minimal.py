from .common import (
    FieldExtractor,
    context_field,
    field,
    tier,
)

FIELDS: dict[str, FieldExtractor] = {
    "Icon": context_field("icon"),
    "Name": field("Name"),
    "Description": field("Description"),
    "Tier": tier,
    "Acquisition Hint": field("AcquisitionHint"),
}
