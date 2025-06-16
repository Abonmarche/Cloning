from log_into_gis import get_gis
from get_items_in_folder import get_items_in_folder

source_gis = get_gis("AbonmarcheDemo")
source_folder = "Demo Capital Improvement Plan"

item_ids = get_items_in_folder(source_folder, source_gis)
print(f"List of Item IDs: {item_ids}")

items_to_clone = [source_gis.content.get(i) for i in item_ids]

dest_gis = get_gis("Angola")
dest_folder = "Capital Improvement Planning"

cloned_items = dest_gis.content.clone_items(
    items=items_to_clone,          
    folder=dest_folder,            
    item_extent=None,              
    use_org_basemap=False,         
    copy_data=True,                
    copy_global_ids=False,         
    search_existing_items=True,    
    item_mapping=None,             
    group_mapping=None,            
    owner=None,                    
    preserve_item_id=False,        
    export_service=False,          
    preserve_editing_info=False  
)