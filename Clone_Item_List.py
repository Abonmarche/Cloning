from typing import Any
from arcgis.gis import GIS
from log_into_gis import get_gis


def gather_items(gis_src: GIS, ids: list[str]):
    """
    Fetch Item objects from *gis_src*; raise if any ID is missing.
    """
    missing = [i for i in ids if gis_src.content.get(i) is None]
    if missing:
        raise ValueError(f"IDs not found in source: {missing}")
    return [gis_src.content.get(i) for i in ids]


def clone(
    source: GIS,
    target: GIS,
    item_ids: list[str],
    *,
    # ---------- clone_items signature ----------
    folder: str | None = None,
    item_extent: dict[str, Any] | None = None,
    use_org_basemap: bool = False,
    copy_data: bool = True,
    copy_global_ids: bool = False,
    search_existing_items: bool = True,
    item_mapping: dict[str, str] | None = None,
    group_mapping: dict[str, str] | None = None,
    owner: str | None = None,
    preserve_item_id: bool = False,
    export_service: bool = False,
    preserve_editing_info: bool = False,
    **kwargs,
):
    """
    Clone *item_ids* from *source* to *target*.

    All parameters mirror GIS.content.clone_items
    """
    items = gather_items(source, item_ids)

    portal_label = (
        getattr(target.properties, "urlKey", None)
        or getattr(target.properties, "portalHostname", "")
        or target.url
    )

    print(
        f"Cloning {len(items)} items → {portal_label} "
        f"(folder={folder or 'root'}, owner={owner or target.users.me.username})"
    )

    cloned = target.content.clone_items(
        items=items,
        folder=folder,
        item_extent=item_extent,
        use_org_basemap=use_org_basemap,
        copy_data=copy_data,
        copy_global_ids=copy_global_ids,
        search_existing_items=search_existing_items,
        item_mapping=item_mapping,
        group_mapping=group_mapping,
        owner=owner,
        preserve_item_id=preserve_item_id,
        export_service=export_service,
        preserve_editing_info=preserve_editing_info,
        **kwargs,
    )

    print(f"✓ {len(cloned)} items cloned successfully")
    return cloned


# --------------------------------------------------------------------
# Execute
# --------------------------------------------------------------------
if __name__ == "__main__":
    src_gis = get_gis("Abonmarche")
    dest_gis = get_gis("HarborShores")

    items_to_clone = [
    # Dashboard
    "ec42c5e01a7c4bb9ac985a32d6ee48ff",
    # Experience
    "123d273adabe4b19ae7b38187e6e0cd4"

]

    # Map old data layers to the new ones already published
    # layer_mapping = {
    #     "dc51460c79334ad496dfa9a37839c431": "ede223e76f3149f7987da3b309581ded",  # main layer
    #     "844a3b18e9d9452e9fe3fb8a95648bb5": "b372eec797624abc9ed4dcd6b2b3d0dd",  # view view
    #     "89381ffd977e47c3b4414a5205c5568f": "4789f9667cb74adfac736eef6592d882",  # edit view
    #     "9cd40002304b4b30b9315a3f9aba509f": "e123f1e8a91d4196beaaefc807a92aab",  # join view
    # }

    cloned_items = clone(
        src_gis,
        dest_gis,
        items_to_clone,
        folder="Master Plan",
        search_existing_items=True,
        # leave other params at their documented defaults
    )
