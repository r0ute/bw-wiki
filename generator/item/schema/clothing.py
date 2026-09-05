from .common import FieldExtractor, context_field, enum_value, field, tier

FIELDS: dict[str, FieldExtractor] = {
    "Icon": context_field("icon"),
    "Name": field("Name"),
    "Tier": tier,
    "Armor Slot": field(
        "ArmorSlot",
        transform=enum_value,
    ),
    "Armor": field("Armor"),
}
