from .common import (
    FieldExtractor,
    asset_reference_name,
    context_field,
    field,
    tier,
)

FIELDS: dict[str, FieldExtractor] = {
    "Icon": context_field("icon"),
    "Name": field("Name"),
    "Description": field("Description"),
    "Category": context_field("category"),
    "Rarity": field("Rarity", transform=asset_reference_name),
    "Tier": tier,
    "Expected Price": field("ExpectedPrice"),
    "Acquisition Hint": field("AcquisitionHint"),
}
