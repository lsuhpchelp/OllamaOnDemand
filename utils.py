# Misc utilities

import os
import shutil
import gradio as gr
from humanize import naturalsize
import chatsessions as cs
import usersettings as us
import multimodal as mm
import remotemodels as rm


class UtilsMixin:
    """Mixin class for misc utility methods."""
    
    #------------------------------------------------------------------
    # Misc utilities
    #------------------------------------------------------------------
    
    def cleanup_cache(self):
        """
        Clean up orphaned files in the cache directory.
        Each uploaded file is stored in a uniquely-hashed subfolder by Gradio.
        This method reads the chat history file as plain text and checks whether
        each subfolder name is referenced. If not, the entire subfolder is deleted.
        
        Input:
            None
        Output: 
            None
        """
        
        cache_dir = os.path.join(self.args.workdir, "cache")
        
        # Skip if cache directory does not exist
        if not os.path.isdir(cache_dir):
            return
        
        # Read chat history file as plain text
        chat_file = os.path.join(self.args.workdir, "chats.json")
        try:
            with open(chat_file, "r", encoding="utf-8") as f:
                chat_text = f.read()
        except Exception:
            return
        
        # Check each subfolder in cache directory
        deleted_count = 0
        for folder_name in os.listdir(cache_dir):
            folder_path = os.path.join(cache_dir, folder_name)
            
            # Only process directories
            if not os.path.isdir(folder_path):
                continue
            
            # If the folder name is not referenced in chat history, delete it
            if folder_name not in chat_text:
                try:
                    shutil.rmtree(folder_path)
                    deleted_count += 1
                except Exception:
                    pass
        
        if deleted_count > 0:
            print(f"Cache cleanup: removed {deleted_count} orphaned folder(s).")
    
    def list_installed_models(self, formatted=False):
        """
        List all installed models.
        
        Input:
            formatter:  Whether to return a formatted list of tuples for model selector dropdown (Default: False)
        Output: 
            models:     List of all model names
        """
        if formatted:
            models = sorted([(f"{model.model} ({naturalsize(model.size, binary=True, gnu=True, format='%.0f')})", model.model) \
                        for model in self.client.list().models])
        else:
            models = sorted([model.model for model in self.client.list().models])
        
        return models if models else ["(No model is installed...)"]
    
    def dict_installed_models(self):
        """
        List all installed models in dictionary form.
        
        Input:
            None
        Output: 
            models:     Dictionary like {"model_name": ["tag1", "tag2", ...], ...}
        """
        
        model_dict = {}
        
        for model in self.models:
            
            if (len(model.split(":")) >= 2):
                name, tag = model.split(":")
            else:
                continue
            
            if (name in model_dict):
                model_dict[name].append(tag)
            else:
                model_dict[name] = [tag]
        
        return model_dict
    
    def dict_remote_models(self):
        """
        List all remote models in dictionary form.
        
        Input:
            None
        Output: 
            models:     Dictionary like {"model_name": ["tag1", "tag2", ...], ...}
        """
        
        # First, attempt to load "remotemodels.json" in current path, which is supposed to be created upon creating the container
        models = rm.load_model_list(self.current_path)
        
        # If failed (nothing is loaded), attempt to load from user's work directory (user generated)
        if (not models):
            
            models = rm.load_model_list(self.args.workdir)
            
            # If still failed, pull from remote server, and save in user's work directory for future loading
            if (not models):
                
                models = rm.dict_all_models()
                
                rm.save_model_list(self.args.workdir, models)
                
        return(models)
        
    def is_model_path(self, model_path):
        """
        Check whether a path is a model path that will not cause problem launching Ollama server.
        As of 8/6/2025, a non-writable model directory should container: 
            - A "blobs" directory
            - A non-empty or removable "manifests" directory)
            
        Input:
            None
        Output: 
            bool
        """
        
        blobs_path = os.path.join(model_path, "blobs")
        manifests_path = os.path.join(model_path, "manifests")
        return(os.access(model_path, os.R_OK) \
                and os.access(blobs_path, os.R_OK) \
                and os.access(manifests_path, os.R_OK) \
                and len(os.listdir(manifests_path)) > 0)
                    
    def update_current_chat(self, chat_index):
        """
        Update current chat index, history to given index.
        
        Input:
            chat_index:     Chat index (-1 to start a new chat, others to select existings).
        Output: 
            None
        """
        
        if chat_index == -1:
        
            # Update chat index
            self.chat_index = 0
            
            # Create a new chat and update chat history
            self.chat_history = cs.new_chat()
            
            # Get chat title
            self.chat_title = cs.get_chat_title(0)
            
        else:
        
            # Update chat index
            self.chat_index = chat_index
            
            # Update chat history
            self.chat_history = cs.load_chat(chat_index)
            
            # Get chat title
            self.chat_title = cs.get_chat_title(chat_index)
                    
    def chat_history_stream(self):
        """
        Format chat_history list into an Ollama processable format, particularly for multimodal attachments.
        
        Input:
            None
        Output: 
            chat_history:   Formatted chat history
        """
        
        # Make a copy of the chat history
        chat_history = []
        
        # Loop and replace
        for chat in self.chat_history:
            
            # Format user message
            if (chat["role"] == "user"):
            
                chat_history += mm.format_chat_stream(chat)
            
            else:
                
                chat_history.append(chat)
        
        return(chat_history)
                    
    def chat_history_display(self):
        """
        Format chat_history list into a more clean HTML for display.
        
        Input:
            None
        Output: 
            chat_history:   Formatted chat history
        """
        
        # Make a copy of the chat history
        chat_history = []
        
        # Loop and replace
        for chat in self.chat_history:
            
            # Make a copy
            chat_tmp = chat.copy()
            
            # Format assistant message 
            if (chat_tmp["role"] == "assistant"):
            
                # If "thinking" exists, add thinking process depending on the process
                if (chat_tmp.get("thinking")):
                    
                    chat_tmp["content"] = self.think_tags["head"] + \
                                          chat_tmp["thinking"] + \
                                          self.think_tags["tail"] + \
                                          chat_tmp["content"]
            
            # Format user message
            elif (chat_tmp["role"] == "user"):
            
                # Display user uploaded images
                if (chat_tmp.get("images")):
            
                    # Append single image or gallery, depending on the number of images
                    if (len(chat_tmp["images"]) <= 1):
                        chat_history.append({ "role": "user", "content": gr.Image(chat_tmp["images"][0]) })
                    elif (len(chat_tmp["images"]) >= 6):
                        chat_history.append({ "role": "user", "content": gr.Gallery(chat_tmp["images"], columns=3) })
                    else:
                        chat_history.append({ "role": "user", "content": gr.Gallery(chat_tmp["images"], columns=2) })
            
                # Display user uploaded files (contains at least one non-image)
                elif (chat_tmp.get("files")):
            
                    # Append each file as a separated message
                    for file in chat_tmp["files"]:
                        chat_history.append({ "role": "user", "content": gr.File(file) })
                
            # Append message
            chat_history.append(chat_tmp)
                                        
        return(chat_history)
        
    def save_chat_history(self):
        """
        Save chats to file in user's work directory.
        
        Input:
            None
        Output: 
            None
        """
        cs.save_chats(self.args.workdir)
    
    def load_chat_history(self):
        """
        Load chats from file in user's work directory.
        
        Input:
            None
        Output: 
            None
        """
        cs.load_chats(self.args.workdir)
        
    def save_settings(self):
        """
        Save user settings to file in user's work directory.
        
        Input:
            None
        Output: 
            None
        """
        us.save_settings(self.args.workdir, self.settings)
        
    
    def load_settings(self):
        """
        Load user settings from file in user's work directory.
        
        Input:
            None
        Output: 
            settings:   User settings dictionary
        """
        return us.load_settings(self.args.workdir)

    def enable_components(self, interactive=True):
        """
        Enable or disable components.
        
        Input:
            interactive:    Whether components are interactive
        Output: 
            chat_selector:
            new_btn:
        """
        
        return gr.update(value=self.generate_chat_selector(interactive)), \
               gr.update(interactive=interactive)
