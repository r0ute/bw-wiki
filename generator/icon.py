from pathlib import Path

ICON_EXTENSIONS = {".webp", ".ico"}
ICON_PATH_KEYS = ("ObjectPath", "AssetPathName", "ObjectName")


def build_icon_index(assets_root: Path) -> dict[str, Path]:
    """
    Build a lowercase filename-stem index of extracted icons.

    The first icon found for a duplicate stem is retained.
    """
    index: dict[str, Path] = {}

    for path in assets_root.rglob("*"):
        if path.is_file() and path.suffix.lower() in ICON_EXTENSIONS:
            index.setdefault(path.stem.lower(), path)

    print(f"Icons indexed: {len(index)}")

    return index


def asset_path_stem(asset_path_name: str) -> str:
    """
    Extract an extracted filename stem from an Unreal/FModel asset reference.

    Handles asset paths, optional object instance suffixes, and Unreal
    object wrappers such as Texture2D'Foo'.
    """
    if not isinstance(asset_path_name, str) or not asset_path_name:
        return ""

    value = asset_path_name.strip()

    if "'" in value:
        parts = value.rsplit("'", 2)
        value = parts[1] if len(parts) == 3 and parts[1] else value

    return Path(value.split(".")[0]).name


def find_icon(
    properties: dict,
    icon_index: dict[str, Path],
) -> Path | None:
    """
    Resolve Properties.Icon to an extracted icon.

    ObjectPath, AssetPathName, and ObjectName are checked in that order.
    """
    icon = properties.get("Icon")
    if not isinstance(icon, dict):
        return None

    for key in ICON_PATH_KEYS:
        value = icon.get(key)

        if not isinstance(value, str) or not value:
            continue

        if result := icon_index.get(asset_path_stem(value).lower()):
            return result

    return None


def copy_icon(icon: Path, output_dir: Path) -> Path:
    """
    Copy an icon to the generated documentation assets.

    Existing files are replaced only when their size differs.
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    destination = output_dir / icon.name

    if not destination.exists() or destination.stat().st_size != icon.stat().st_size:
        destination.write_bytes(icon.read_bytes())

    return destination
