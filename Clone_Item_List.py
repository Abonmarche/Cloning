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
    dest_gis = get_gis("AbonmarcheDemo")

    items_to_clone = [
    # Feature layers and views
    # "d52e45f722a444dea2ef146df4e91335",
    # "9ef73e7aed1f4eaf94d9c26806dafeb2",
    # "e67b6b62fcc3403b9a9dc4369b6f8346",
    # "2ad3af98d8d9409eb737a5213382d91d",
    # "b76f44d86bef4525a96939dd57dd7e2e",
    # "d0c9137141744bdeab30cd7e5f1292cb",
    # "4c434d6f2200483a960d9f4b29e7cb00",
    # "910ee90dc44947bc8e025f3eac901173",

    # Forms
    # "6fa0c05ca369472ea4a36838b9e86138",

#     # Maps
    # "fe4e265efbd94e428bd6b16d1348b2c8",
    # "1d92adbf06324c6f93a47f8b487219f2",
    # "dac971731385423fa3e7d7b736b532a8",
    # "fd56f71d87f5471689726cd58edf3b91",
    # "ea2f8206d6c549e7a74c0279ffebabe3",
    # "5e0fcd7c615d446d9334b10a49bbc43e",
    # "fd7286c4460e439fad837553bf02ac62",
    # "1b2edb8d2c4c4591940cd617f056dcdb",
    # "c49a29e765d64650903712c0346ebf0d",

#     # Instant Apps
    # "073a89cbc388492c8a653eb7de0f386e",
    # "4f1755f375a94948896c8e330b362cd8",
    # "6a6fe6aee9f54123b5cfb0839f5cc6f7",
    # "909ef8f90e1642c69f47c7741c251eb8",

#     # Dashboards
    # "b700688ccd2d435a93c377d1b58275ae",
    #"5642e38ab3d946839de9379a712ca18f",
    #"1a2b0b06f00640568c7923c428ce9590",
    # "77a700adbb0e44a1bda35e1170f9e17b",
    # "ce01e59e77124848b77e23522cbf7110",

#     # Experiences
    #  "175636f46ab14338a16855d8e7e8a313",

#     # Notebooks
    "361aaa2839ab46ae8f7a1aad16157a8b",
    "97b6cadb27fb4cf1a1c10fe54979a37f",
    "78e0d3d4c03843b6a1ebddfd83394411",

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
        folder="Demo Capital Improvement Plan",
        search_existing_items=True,
        # leave other params at their documented defaults
    )
