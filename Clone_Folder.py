from log_into_gis import get_gis
from get_items_in_folder import get_items_in_folder

source_gis = get_gis("Demotte")
source_folder = "Paser Solution Content"

item_ids = get_items_in_folder(source_folder, source_gis)
print(f"List of Item IDs: {item_ids}")

items_to_clone = [source_gis.content.get(i) for i in item_ids]

dest_gis = get_gis("AbonmarcheDemo")
dest_folder = "Demo PASER"

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