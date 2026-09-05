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
    "Tier": tier,
    "Damage Type": field("DamageType", transform=asset_reference_name),
    "Damage": field("Damage"),
}
