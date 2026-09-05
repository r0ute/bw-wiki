from .common import (
    FieldExtractor,
    asset_reference_name,
    context_field,
    field,
    nested_field,
    tier,
)

FIELDS: dict[str, FieldExtractor] = {
    "Icon": context_field("icon"),
    "Name": field("Name"),
    "Tier": tier,
    "Category": field(
        "Category",
        transform=asset_reference_name,
    ),
    "Damage Type": field("DamageType", transform=asset_reference_name),
    "Damage": field("Damage"),
    "Projectile Damage": nested_field(
        "ProjectileDamage",
        "Damage",
    ),
}
