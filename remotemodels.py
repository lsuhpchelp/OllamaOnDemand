# List remote models from ollama.com in dictionary form
#   * Subject to change depending on the latest web design

import os, re
import requests
import json

def dict_all_models():
    """
    List all remote models from ollama.com in dictionary form.
    
    Input:
        None
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
    html = requests.get(f"https://ollama.com/search?page={page:d}", timeout=30).text

    # Extract lines containing listed model names
    #   * Model names are saved in "<span>" tags with "x-test-search-response-title"
    lines = [line for line in html.splitlines() if "x-test-search-response-title" in line]

    # Strip HTML tags and spaces, leave only the model names
    lines = [re.sub(r'<[^>]*>', '', line).replace(" ", "") for line in lines]
    
    # For each model name, open another page: "https://ollama.com/library/[model_name]" to fetch tags
    models = {}
    for model_name in lines:
        
        # Validate model name: only allow alphanumeric, hyphens, underscores, and dots
        if not re.match(r'^[a-zA-Z0-9._-]+$', model_name):
            continue
        
        # Fetch model page
        html = requests.get(f"https://ollama.com/library/{model_name}", timeout=30).text

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
    
    save_model_list(".", dict_all_models())
    