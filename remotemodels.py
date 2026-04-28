# List remote models from ollama.com in dictionary form
#   * Subject to change depending on the latest web design

import os, re
import requests
import json

def dict_all_models(filter=None):
    """
    List all remote models from ollama.com in dictionary form, with optional filtering.
    
    Input:
        filter:     Path to the JSON file defining the filter (optional)
    Output: 
        models:     Dictionary like {"model_name": ["tag1", "tag2", ...], ...}
    """
    
    models = {}
    page = 1
    
    # Loop all pages until an empty page is found
    while True:
        
        # List models on one page
        models_page = dict_page_models(page)
        
        # If not empty, save; otherwise, break loop
        if models_page:
            
            models = models | models_page
            page += 1
            
        else:
            
            break
    
    # Apply filter if provided
    if filter is not None:
        models = filter_models(filter, models)
    
    # Return result
    return(models)

def dict_page_models(page):
    """
    List all remote models from a page "ollama.com/search?page=[N]" in dictionary form.
    
    Input:
        page:       Page number
    Output: 
        models:     Dictionary like {"model_name": ["tag1", "tag2", ...], ...}
    """
        
    # Fetch the HTML content from Ollama model search with given page
    #   * This should only fetch officially maintained model, not user pushed
    html = requests.get(f"https://ollama.com/search?page={page:d}").text

    # Extract lines containing listed model names
    #   * Model names are saved in "<span>" tags with "x-test-search-response-title"
    lines = [line for line in html.splitlines() if "x-test-search-response-title" in line]

    # Strip HTML tags and spaces, leave only the model names
    lines = [re.sub(r'<[^>]*>', '', line).replace(" ", "") for line in lines]
    
    # For each model name, open another page: "https://ollama.com/library/[model_name]" to fetch tags
    models = {}
    for model_name in lines:
        
        # Fetch model page
        html = requests.get(f"https://ollama.com/library/{model_name}").text

        # Extract lines containing listed model names
        #  * Model full names (including tags) are saved in "<a href=...>" tags with "font-medium text-neutral-800" classes
        lines = [line for line in html.splitlines() if "<a href" in line and "font-medium text-neutral-800" in line]

        # Strip HTML tags, spaces, and model names. Leave only the model tags.
        lines = [re.sub(r'<[^>]*>', '', line).replace(" ", "").replace(f"{model_name}:", "") for line in lines]

        # Remove any tags contains "latest" (default) and "cloud" (cloud models)
        lines = [line for line in lines if not "latest" in line and not "cloud" in line]
        
        # Add result to "models" dict if the result is not empty
        if (lines):
            models[model_name] = lines
    
    # Return results
    return(models)

def filter_models(filter, models):
    """
    Filter the model list using rules defined in a JSON filter file.
    
    The filter file contains two keys:
        "allow":    List of regex patterns. If non-empty, only model names matching
                    at least one pattern are kept; the "block" list is ignored.
        "block":    List of regex patterns. If "allow" is empty and "block" is
                    non-empty, model names matching any pattern are removed.
    
    Input:
        filter:     Path to the JSON file defining the filter
        models:     Dictionary like {"model_name": ["tag1", "tag2", ...], ...}
    Output:
        models:     Filtered dictionary with the same structure
    """

    # Attempt to load the filter definition file
    try:
        with open(filter, "r", encoding="utf-8") as f:
            filter_rules = json.load(f)
    except Exception:
        # If the file cannot be read, return the model list unchanged
        return(models)

    # Retrieve allow and block pattern lists (default to empty lists if absent)
    allow_patterns = filter_rules.get("allow", [])
    block_patterns = filter_rules.get("block", [])

    # Apply allow filter: keep only models whose names match at least one allow pattern
    if allow_patterns:
        models = {
            name: tags for name, tags in models.items()
            if any(re.search(pattern, name) for pattern in allow_patterns)
        }

    # Apply block filter (only when allow is empty): remove models matching any block pattern
    elif block_patterns:
        models = {
            name: tags for name, tags in models.items()
            if not any(re.search(pattern, name) for pattern in block_patterns)
        }

    return(models)

def save_model_list(workdir, models):
    """
    Save model list in work directory.
    
    Input:
        workdir:    Work directory
        models:     Dictionary like {"model_name": ["tag1", "tag2", ...], ...}
    Output: 
        None
    """

    try:
        
        # Create work directory if it does not exist
        os.makedirs(workdir, exist_ok=True)

        # Dump user settings if it is accessible.
        file_path = os.path.join(workdir, "remotemodels.json")
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(models, f, indent=2, ensure_ascii=False)
            
    except Exception:
        pass

def load_model_list(workdir):
    """
    Load model list in work directory.
    
    Input:
        workdir:    Work directory
    Output: 
        models:     Dictionary like {"model_name": ["tag1", "tag2", ...], ...}
    """

    try:

        # Return user settings if exists
        file_path = os.path.join(workdir, "remotemodels.json")
        with open(file_path, "r", encoding="utf-8") as f:
            return(json.load(f))
            
    except Exception:
        
        # Return default user settings
        return({})
    

if __name__ == "__main__":

    # Fetch all remote models, apply the filter, then save the result
    models = dict_all_models("remotemodels_filter.json")
    save_model_list(".", models)
    