# User settings

import os
import json

settings_default = {
    
    # Current selected model
    "model_selected": "",
    
    # Generation options
    "options": {}
    
}

def save_settings(workdir, settings):
    """
    Save user settings in work directory.
    
    Input:
        workdir:    Work directory
        settings:   Settings dictionary
    Output: 
        None
    """

    try:
        
        # Create work directory if it does not exist
        os.makedirs(workdir, exist_ok=True)

        # Dump user settings if it is accessible.
        file_path = os.path.join(workdir, "settings.json")
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(settings, f, indent=2, ensure_ascii=False)
            
    except Exception:
        pass

def load_settings(workdir):
    """
    Load user settings in work directory.
    
    Input:
        workdir:    Work directory
    Output: 
        settings:   Settings dictionary
    """

    try:

        # Return user settings if exists
        file_path = os.path.join(workdir, "settings.json")
        with open(file_path, "r", encoding="utf-8") as f:
            return(json.load(f))
            
    except Exception:
        
        # Return default user settings
        return(settings_default)
    