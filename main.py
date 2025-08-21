# =============================
# Ollama OnDemand
# Author: Dr. Jason Li (jasonli3@lsu.edu)
# =============================

import os
import requests
import json
import subprocess
import time
import requests
import re
import ollama
from typing import Literal
import gradio as gr
from arg import get_args
import chatsessions as cs
import usersettings as us

#======================================================================
#                           Main UI class
#======================================================================

class GradioComponents:
    """An empty class used to same Gradio components."""
    pass

class OllamaOnDemandUI:
    """Ollama OnDemand UI class."""
    
    #------------------------------------------------------------------
    # Constructor
    #------------------------------------------------------------------
    
    def __init__(self, args):
        """
        Constructor.
        
        Input:
            args: Command-line arguments.
        """
        
        # Current path
        self.current_path = os.path.dirname(os.path.abspath(__file__))
        
        # Command-line arguments
        self.args = args
        
        # Stop event (for streaming interruption)
        self.is_streaming = False
        
        # Chat session(s)
        self.load_chat_history()
        self.update_current_chat(0)                 # Load chat at 0 index. Also initialize:
                                                    #   self.chat_index     - Current chat index
                                                    #   self.chat_title     - Current chat title
                                                    #   self.chat_history   - Current chat history
        
        # User settings
        self.settings = self.load_settings()
        
        # Use default model path if:
        #   1) User did not customize model path, or
        #   2) Model path not writable and not a legal model path
        if (not self.settings.get("ollama_models") or \
            not os.access(self.settings.get("ollama_models"), os.W_OK) and \
            not self.is_model_path(self.settings.get("ollama_models"))):
            self.settings["ollama_models"] = self.args.ollama_models
            self.save_settings()
        
        # Start Ollama server and save client(s)
        self.start_server()
        self.client = self.get_client()
        
        # Get models
        self.models = self.list_installed_models()          # Installed models (List)
        self.remote_models = self.dict_remote_models()      # Remote models (Dict)
        if (not self.settings.get("model_selected") in self.models):
            self.settings["model_selected"] = self.models[0]
        
        # Gradio components deposit
        self.gr_main = GradioComponents()           # Main view
        self.gr_leftbar = GradioComponents()        # Left sidebar
        self.gr_rightbar = GradioComponents()       # Right sidebar
        self.gr_rightbar.settings_components = {}   # User settings: Setting components
        self.gr_rightbar.settings_defaults = {}     # User settings: Default checkbox
        
        # Setup Gradio temp files directory
        os.environ["GRADIO_TEMP_DIR"] = self.args.workdir + "/cache"
        
        # Compile regular expression for think tag replacement for display
        self.think_tags = {
            "head_tag":     "<think&#x200B;&#x200C;&#x2060;>\n\n",
            "tail_tag":     "\n\n</think&#x200B;&#x200C;&#x2060;>\n\n",
            "head_html":    "<details><summary><i><b>(Thinking...)</b></summary>\n\n",
            "tail_html":    "\n\n(Done thinking...)</i></details><br>\n\n"
        }

    
    #------------------------------------------------------------------
    # Server connection
    #------------------------------------------------------------------
        
    def start_server(self, raise_error=True):
        """
        Start Ollama Server
        
        Input:
            None
        Output:
            None (raise error) or error message (return for gr.Error)
        """
        
        # Define environment variables
        env = os.environ.copy()
        env["OLLAMA_HOST"] = self.args.ollama_host
        env["OLLAMA_MODELS"] = self.settings["ollama_models"]
        env["OLLAMA_SCHED_SPREAD"] = "1"

        # Start the Ollama server
        print("Starting Ollama server on " + self.args.ollama_host)
        self.server_process = subprocess.Popen(
            ["ollama", "serve"],
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        
        # Wait until the server starts
        for _ in range(60): 
            
            try:
                if requests.get(self.args.ollama_host).ok:
                    print("Ollama server is running")
                    return ""
            except:
                pass
            print("Waiting for Ollama server to start...")
            time.sleep(1)
            
        else:
            
            if (raise_error):
                raise RuntimeError("Ollama server failed to start in 1 min. Something is wrong.")
            else:
                return("Ollama server failed to start in 1 min. Something is wrong.")
            
    def get_client(self, type="ollama"):
        """
        Get client.
        
        Input:
            type: Client type. 
                - "ollama": Ollama client (Default)
                - "langchain": LangChain client (To be added)
        Output:
            client: Client object
        """
        if type=="ollama":
            return ollama.Client(host=self.args.ollama_host)
    
    #------------------------------------------------------------------
    # Misc utilities
    #------------------------------------------------------------------
    
    def list_installed_models(self):
        """
        List all installed models.
        
        Input:
            None
        Output: 
            models:     List of all model names
        """
        
        models = sorted([model.model for model in self.client.list().models])
        return models if models else ["(No model is found: Pull a model or change model directory to continue...)"]
    
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
            
            name, tag = model.split(":")
            
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
        
        # Step 1: Fetch the HTML content from Ollama model search
        #       This should only fetch officially maintained model, not user pushed
        html = requests.get("https://ollama.com/search").text

        # Step 2: Extract relevant lines
        lines = [line for line in html.splitlines() if 'x-test-search-response-title' in line or 'x-test-size' in line]

        # Step 3: Substitute the tag for title with "Model:"
        lines = [line.replace("x-test-search-response-title>", "x-test-search-response-title>Model:") for line in lines]

        # Step 4: Strip HTML tags and spaces
        lines = [re.sub(r'<[^>]*>', '', line).replace(" ", "") for line in lines]
        
        # Step 5: Return formatted dictionary
        model_dict = {}
        current_model = None
        for line in lines:
            if line.startswith("Model:"):
                current_model = line[len("Model:"):]  # Strip "Model:" prefix
                model_dict[current_model] = []
            elif current_model:
                model_dict[current_model].append(line)
        
        # Return results
        return(model_dict)
        
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
        
        return(os.access(model_path, os.R_OK) \
                and os.access(model_path+"/blobs", os.R_OK) \
                and os.access(model_path+"/manifests", os.R_OK) \
                and len(os.listdir(model_path+"/manifests")) > 0)
                    
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
                    
    def chat_history_format(self):
        """
        Format chat_history's thinking tag into a more clean HTML
        
        Input:
            None
        Output: 
            chat_history:   Formatted chat history
        """
        
        # Make a copy of the chat history
        chat_history = self.chat_history.copy()
        
        # Loop and replace
        for chat in chat_history:
            
            if chat["role"] == "assistant":
                chat["content"] = chat["content"].replace(self.think_tags["head_tag"], 
                                                          self.think_tags["head_html"])
                chat["content"] = chat["content"].replace(self.think_tags["tail_tag"], 
                                                          self.think_tags["tail_html"])
        
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

        
    #------------------------------------------------------------------
    # Event handler
    #------------------------------------------------------------------
    
    def stream_chat(self):
        """
        Stream chat (invoked by new/edit/retry).
        
        Input:
            None
        Output: 
            chat_history:       Current chat history
            user_input:         Update user input field to "" and button face
        """
        
        # Failsafe: Only stream while is_streaming is True
        if self.is_streaming:
        
            # Pre-process options
            options = self.settings.get("options").copy() if self.settings.get("options") else {}
            if (options and options.get("stop")):
                options["stop"] = options["stop"].split(",")    # Set up stop sequence

            # Generate next chat results
            response = self.client.chat(
                model = self.settings["model_selected"],
                messages = self.chat_history,
                stream = True,
                options = options
            )
            
            # Reset thinking flag
            is_thinking = False     # Or "S" (switchable thinking), "B" (Built-in thinking)
            token_count = 0

            # Stream results in chunks while not interrupted
            for chunk in response:
            
                # Breake if interrupted
                if not self.is_streaming:
                    break
                
                # Add chunk and thinking tag if needed
                if (not is_thinking and chunk.message.thinking):
                    # Switchable thinking mode: begin
                    #   - When is_thinking was False but thinking attribute is not empty
                    #   - Set is_thinking to "S" (switchable thinking)
                    self.chat_history[-1]["content"] += self.think_tags["head_tag"] + chunk.message.thinking
                    is_thinking = "S"
                elif (is_thinking == "S" and chunk.message.thinking == None):
                    # Switchable thinking mode: end
                    #   - When is_thinking was "S" (switchable), but thinking attribute is now None
                    #   - Set is_thinking to False (not thinking)
                    self.chat_history[-1]["content"] += self.think_tags["tail_tag"] + chunk.message.content
                    is_thinking = False
                elif (token_count == 0 and chunk.message.content == "<think>"):
                    # Built-in thinking (e.g., DeepSeek-R1): begin
                    #   - When this token is the first token and is "<think>"
                    #   - Set is_thinking to "B" (built-in thinking)
                    self.chat_history[-1]["content"] += self.think_tags["head_tag"]
                    is_thinking = "B"
                elif (is_thinking == "B" and chunk.message.content == "</think>"):
                    # Built-in thinking (e.g., DeepSeek-R1): end
                    #   - When is_thinking was True (set for built-in thinking) but this token is "</think>"
                    #   - Set is_thinking to False (not thinking)
                    self.chat_history[-1]["content"] += self.think_tags["tail_tag"]
                    is_thinking = False
                else:
                    # None of above: normal chunk
                    self.chat_history[-1]["content"] += chunk.message.content or chunk.message.thinking or ""
                
                # Token count ++
                token_count += 1
                
                # Yield results
                yield self.chat_history, gr.update(value="", submit_btn=False, stop_btn=True)
        
        # Once finished, set streaming to False
        self.is_streaming = False
        
        # Final update components
        yield self.chat_history_format(), gr.update(value="", submit_btn=True, stop_btn=False)
    
    def stop_stream_chat(self):
        """
        Stop streaming.
        
        Input:
            None
        Output: 
            chat_history:       Current chat history
            user_input:         Update user input field to "" and button face
        """
        
        # Set streaming to False
        self.is_streaming = False
        
        # Update components
        yield self.chat_history_format(), gr.update(value="", submit_btn=True, stop_btn=False)
    
    def new_message(self, user_input):
        """
        When a new message is submitted, set chatbot & input field before start streaming
        
        Input:
            user_input:         User's input
        Output: 
            chat_history:       Current chat history
            user_input:         Update user input field to "" and button face
        """
        
        # Create user message
        if len(user_input["files"]) > 0:
            user_message = {
                "role":     "user", 
                "content":  user_input["text"],
                "images":   user_input["files"]
            }
        else:
            user_message = {
                "role":     "user", 
                "content":  user_input["text"]
            }
            
        # Append user message to history
        self.chat_history.append(user_message)
        self.chat_history.append({"role": "assistant", "content": ""})
            
        # Set streaming to True
        self.is_streaming = True
        
        # Update components
        yield self.chat_history, gr.update(value="", submit_btn=False, stop_btn=True)
    
    def retry(self, retry_data: gr.RetryData):
        """
        When retry request is sent, set chatbot & input field before start streaming
        
        Input:
            retry_data:         Event instance (as gr.RetryData)
        Output: 
            chat_history:       Current chat history
            user_input:         Update user input field to "" and button face
        """
        
        # Revert to previous user message
        self.chat_history[:] = self.chat_history[:retry_data.index+1]
        self.chat_history.append({"role": "assistant", "content": ""})
            
        # Set to streaming and continue
        self.is_streaming = True
        
        # Update components
        yield self.chat_history, gr.update(value="", submit_btn=False, stop_btn=True)
    
    def edit(self, edit_data: gr.EditData):
        """
        When edit request is sent, set chatbot & input field before start streaming
        
        Input:
            edit_data:          Event instance (as gr.EditData)
        Output: 
            chat_history:       Current chat history
            user_input:         Update user input field to "" and button face
        """
        
        # Revert to editted user message
        self.chat_history[:] = self.chat_history[:edit_data.index+1]
        self.chat_history[-1]["content"] = edit_data.value
        self.chat_history.append({"role": "assistant", "content": ""})
            
        # Set to streaming and continue
        self.is_streaming = True
        
        # Update components
        yield self.chat_history, gr.update(value="", submit_btn=False, stop_btn=True)
        
    def update_chat_selector(self):
        """
        Update chat selector, mainly for auto-generating a new chat title.
        
        Input:
            None
        Output: 
            chat_selector:  Chat selector update
        """
                
        # If current chat does not have a title, ask client to summarize and generate one.
        if self.chat_title == "New Chat":
            
            # Generate a chat title, but do not alter chat_history
            response = self.client.chat(
                model = self.settings["model_selected"],
                messages = self.chat_history + \
                    [ { "role": "user", 
                        "content": "Summarize this entire conversation with less than six words. Be objective and formal (Don't use first person expression). No punctuation."} ],
                stream = False
            )
            
            # Set new title
            #   Generating and removing <think>*</think> provides the best compatibility between reasoning model and non-reasoning model.
            new_title = response.message.content
            new_title = re.sub(r"<think>.*?</think>", "", new_title, flags=re.DOTALL).strip()
            self.chat_title = new_title
            cs.set_chat_title(self.chat_index, new_title)
            
        return gr.update(value=self.generate_chat_selector())
            
    def select_chat(self, index):
        """
        Change selected chat.
        
        Input:
            index:          Chat index
        Output: 
            chat_history:   Chat history
        """
        
        # Update current chat
        self.update_current_chat(index)
        
        # Return chat history to chatbot
        return self.chat_history_format()
        
    def new_chat(self):
        """
        New chat.
        
        Input:
            None
        Output: 
            chat_selector:  Chat selector update
            chat_history:   Chat history
        """
        
        # Update current chat
        self.update_current_chat(-1)
        
        # Return updated chat selector and current chat
        return gr.update(value=self.generate_chat_selector()), self.chat_history
        
    def rename_chat(self, index, title):
        """
        Rename chat.
        
        Input:
            index:          Chat index
            title:          New chat title
        Output: 
            chat_selector:  Chat selector update
        """
        
        # Change chat title
        cs.set_chat_title(index, title)
        
        # Change current chat title if the current chat is being renamed
        if (self.chat_index == index):
            self.chat_title = title

    def export_chat(self, index):
        """
        Export selected chat as JSON string for browser download.
        
        Input:
            index:          Chat index
        Output: 
            history:        Selected chat hisotry
        """
        
        return json.dumps(cs.load_chat(index), indent=2, ensure_ascii=False)

    def delete_chat(self, index):
        """
        Delete the current chat and update UI.
        
        Input:
            index:          Chat index
        Output:
            chat_selector:  Chat selector update
            chat_history:   Chat history
        """
        
        # Delegate deletion to chatsessions
        cs.delete_chat(index)
        num_chats = len(cs.get_chat_titles())
        
        # If all has been deleted, create a new one
        if num_chats == 0:
        
            return self.new_chat()
        
        # If deleted a previous chat, and current chat_index is not 0, move up
        elif self.chat_index >= index and self.chat_index > 0:
        
            self.chat_index -= 1
            self.update_current_chat(self.chat_index)
            return gr.update(value=self.generate_chat_selector()), self.chat_history_format()
            
        # Otherwise, keep current chat index and reload
        else:
        
            self.update_current_chat(self.chat_index)
            return gr.update(value=self.generate_chat_selector()), self.chat_history_format()
    
    def select_model(self, model_selected):
        """
        Change selected model.
        
        Input:
            model_selected:         Selected model
        Output: 
            None
        """
        
        # Save user settings
        self.settings["model_selected"] = model_selected
        self.save_settings()
    
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
               
    def settings_param_default_change(self, name, value, is_default):
        """
        In User Settings -> Parameters, when toggle / untoggle "Use default" checkbox.
        
        Input:
            name:           Name of the parameter to change
            value:          Value of the parameter to change
            is_default:     Whether to use model default
        Output: 
            component:      Update visibility of the setting component
        """
        
        # Save updated "options" dictionary
        
        # If "options" dictionary exists in settings
        if (self.settings.get("options")):
        
            # If not using default, save customized value to "options" dictionary
            if (not is_default):
                
                self.settings["options"][name] = value
                
            # If using default, remove the key from "options" dictionary
            else:
            
                if (name in self.settings["options"]):
                    del self.settings["options"][name]
        
        # Or if not
        else:
        
            # If not using default, save customized value to "options" dictionary
            if (not is_default):
                
                self.settings["options"] = {name: value}
                
            # If using default, remove the key from "options" dictionary
            else:
            
                self.settings["options"] = {}
        
        self.save_settings()
        
        return(gr.update(visible=not is_default))
               
    def settings_param_value_change(self, name, value):
        """
        In User Settings -> Parameters, when adjusting individual setting
        
        Input:
            name:           Name of the parameter to change
            value:          Value of the parameter to change
        Output: 
            None
        """
        
        # Save updated "options" dictionary
        
        # If "options" dictionary exists in settings
        if (self.settings.get("options")):
        
            self.settings["options"][name] = value
        
        # Or if not
        else:
        
            self.settings["options"] = {name: value}
        
        self.save_settings()
               
    def settings_model_path_change(self, model_path):
        """
        In User Settings -> Models, when changing the model path
        
        Input:
            model_path:         Model path
        Output: 
            error:              Error message
            gr.update:          Update to model selector 
            gr.update:          Update to model path
            gr.update * 2:      Updates to model path buttons
            gr.update * 4:      Updates to model installation components
        """
        
        model_path_old = self.settings["ollama_models"]
        
        # If path is writable, change model path and enable model installation
        if (os.access(model_path, os.W_OK)):
            
            # Update model path
            self.settings["ollama_models"] = model_path
            
            # Restart Ollama server and re-list models
            self.server_process.kill()
            self.server_process.wait()
            error = self.start_server(raise_error=False)
            
            # If error, raise error message, reset everything
            if (error):
                
                # Reset user settings
                elf.settings["ollama_models"] = model_path_old
                
                # Re-restart
                self.server_process.kill()
                self.server_process.wait()
                self.start_server(raise_error=False)
            
            # If successfully started, return correctly
            else:
                
                # Update model list
                self.models = self.list_installed_models()
                
                # Save user settings
                self.save_settings()
                
                # Set writability
                self.gr_rightbar.is_model_path_writable = True
            
        # If not writable
        else:
            
            # If the path is accessible and contains models, change model path but disable model installation
            if (self.is_model_path(model_path)):
            
                # Update model path
                self.settings["ollama_models"] = model_path
                
                # Restart Ollama server and re-list models
                self.server_process.kill()
                self.server_process.wait()
                error = self.start_server(raise_error=False)
                
                # If error, raise error message, reset everything
                if (error):
                    
                    # Reset user settings
                    elf.settings["ollama_models"] = model_path_old
                    
                    # Re-restart
                    self.server_process.kill()
                    self.server_process.wait()
                    self.start_server(raise_error=False)
            
                # If successfully started, return correctly
                else:
                    
                    # Update model list
                    self.models = self.list_installed_models()
                    
                    # Save user settings
                    self.save_settings()
                    
                    # Set writability
                    self.gr_rightbar.is_model_path_writable = False
                
            # If not, reset model path and raise error
            else:
                
                # Error message
                error = "Directory does not exist, you do not have access, or does not contain Ollama model!"
                
        # Return
        return [error,                                                                      # Raise error
                gr.update(choices=self.models, value=self.models[0], interactive=True),     # Model selector
                gr.update(value=self.settings["ollama_models"], interactive=True),          # Model path textbox
                gr.update(interactive=True),                                                # Model path save button
                gr.update(interactive=True),                                                # Model path reset button
                gr.update(choices=self.generate_settings_model_name_choices(), 
                          value=self.generate_settings_model_name_choices()[0][1], 
                          interactive=self.gr_rightbar.is_model_path_writable),             # Model install name list
                gr.update(interactive=self.gr_rightbar.is_model_path_writable),             # Model install tag list
                gr.update(interactive=self.gr_rightbar.is_model_path_writable),             # Model install button
                gr.update(interactive=self.gr_rightbar.is_model_path_writable)]             # Model remove button
                
    def settings_update_model_tags(self, name):
        """
        Update model tags dropdown choices based on model name
        
        Input:
            name:               Model name
        Output: 
            gr.update:          Update to model tags
        """
        
        # Get choices
        choices = self.generate_settings_model_tag_choices(name)
        
        # Return
        return gr.update(choices=choices, value=choices[0][1])
    
    def settings_update_model_buttons(self, name, tag):
        """
        Update model installation buttons' visibility upon changing selections
        
        Input:
            name:               Model name
            tag:                Model tag
        Output: 
            gr.update:          Update to model install button
            gr.update:          Update to model remove button
        """
        
        # Check whether selected model is installed
        is_installed = name+":"+tag in self.models
        
        # Return
        return [gr.update(visible=not is_installed),
                gr.update(visible=is_installed)]
               
    def settings_model_install_remove(self, name, tag, action):
        """
        In User Settings -> Models, install or remove a model
        
        Input:
            name:               Model name
            tag:                Model tag
            action:             "install" or "remove"
        Output: 
            error:              Error message
            status:             Status stream
        """
        
        error = ""
        
        try:
            
            if (action == "install"):
            
                # Pull selected model
                for progress in self.client.pull(name+":"+tag, stream=True):
                    
                    # Get status
                    status = progress.get("status")
                    
                    # Get percentage progress for big blobs ("digest" exists)
                    if progress.get("digest"):
                        
                        completed=progress.get("completed") if progress.get("completed") else 0
                        status += " ( **{:.0%}** )".format(completed / progress.get("total"))
                    
                    # Yield progress
                    yield [error, status]
                    
            elif (action == "remove"):
            
                # Remove selected model
                self.client.delete(name+":"+tag)
                
            else:
            
                error = "Invalid action!"
            
            # Update model list
            self.models = self.list_installed_models()
                
            # Reset user settings
            self.settings["model_selected"] = self.models[0]
            
        except Exception as e:
            
            # Error message
            error = e
                
        # Return
        yield [error, ""]
               
    def settings_model_install_after(self):
        """
        In User Settings -> Models, update components after installing / removing model
        
        Input:
            None
        Output: 
            gr.update:          Update to model selector 
            gr.update:          Update to model path
            gr.update * 2:      Updates to model path buttons
            gr.update * 4:      Updates to model installation components
        """
                
        # Return
        return [gr.update(choices=self.models, \
                          value=self.settings["model_selected"], \
                          interactive=True),                                                # Model selector
                gr.update(interactive=True),                                                # Model path textbox
                gr.update(interactive=True),                                                # Model path save button
                gr.update(interactive=True),                                                # Model path reset button
                gr.update(choices=self.generate_settings_model_name_choices(), 
                          value=self.generate_settings_model_name_choices()[0][1], 
                          interactive=True),                                                # Model install name list
                gr.update(interactive=True),                                                # Model install tag list
                gr.update(interactive=True),                                                # Model install button
                gr.update(interactive=True)]                                                # Model remove button
                    
    def raise_error(self, error):
        """
        Raise an error message
        
        Input:
            error:              Error message
        Output: 
            None
        """
        
        if error:
            raise gr.Error(error)
        
    
    #------------------------------------------------------------------
    # Build UI
    #------------------------------------------------------------------
            
    def generate_chat_selector(self, interactive=True):
        """
        Build chat selector (HTML code)
        
        Input:
            interactive:    Whether the code is responsive to events (Default: True)
        Output: 
            html:           Chat selector HTML code
        """
        
        titles = cs.get_chat_titles()
        html = ""
        
        if interactive:
        
            for i, title in enumerate(titles):
                active = "active-chat" if i == self.chat_index else ""
                html += f"""
                <div class='chat-entry {active}' onclick="select_chat_js({i})" id='chat-entry-{i}'>
                    <span class='chat-title' id='chat-title-{i}' title='{title}'>{title}</span>
                    <input class='chat-title-input hidden' id='chat-title-input-{i}' autocomplete='off'
                           onkeydown="rename_chat_confirm_js(event, {i})"
                           onblur="rename_chat_cancel_js({i})" 
                            onclick="event.stopPropagation()" />
                    <button class='menu-btn' onclick="event.stopPropagation(); open_menu({i})">⋯</button>
                    <div class='chat-menu' id='chat-menu-{i}'>
                        <button onclick="event.stopPropagation(); rename_chat_js({i})">Rename</button>
                        <button onclick="event.stopPropagation(); export_chat_js({i})">Export</button>
                        <button onclick="event.stopPropagation(); delete_chat_js({i})">Delete</button>
                    </div>
                </div>

                """
                
        else:
        
            for i, title in enumerate(titles):
                html += f"""
                <div class='chat-entry'>
                    <span class='chat-title' title='{title}'>{title}</span>
                    <button class='menu-btn'>⋯</button>
                    <div class='chat-menu' id='chat-menu-{i}'>
                        <button>Rename</button>
                        <button>Export</button>
                        <button>Delete</button>
                    </div>
                </div>
                """
        
        return html
            
    def generate_settings_component(self, name, component, component_init):
        """
        Build each setting component.
        
        Input:
            name:           Name of the parameter. Must be the same as Ollama Python's parameter list
            component:      Gradio component method reference
            component_init: Gradio component method initialization arguments
        Output: 
            None
        """
        
        # Check user set it to use model default value
        if (self.settings.get("options") and name in self.settings.get("options")):
            default = False
        else:
            default = True
        
        # Build UI components
        with gr.Row():
            
            # Display name
            gr.Markdown("**" + name.capitalize() + "**")
            
            # Default checkbox
            self.gr_rightbar.settings_defaults[name] = \
                gr.Checkbox(label="(Use default)", 
                            interactive=True, 
                            container=False, 
                            value=default,
                            min_width=None)
                
        # Build adjusting component
        value = self.settings.get("options").get(name) if self.settings.get("options") else 0
        self.gr_rightbar.settings_components[name] = component(
            value = value,
            visible = not default, 
            interactive = True, 
            **component_init
        )
        
        # Add separator
        gr.Markdown("")
        
        # Register checkbox behavior
        self.gr_rightbar.settings_defaults[name].change(
            fn = lambda arg_value, arg_is_default: self.settings_param_default_change(name, arg_value, arg_is_default),
            inputs = [self.gr_rightbar.settings_components[name], self.gr_rightbar.settings_defaults[name]],
            outputs = [self.gr_rightbar.settings_components[name]]
        )
        
        # Register adjusting component behavior
        self.gr_rightbar.settings_components[name].change(
            fn = lambda arg_value: self.settings_param_value_change(name, arg_value),
            inputs = [self.gr_rightbar.settings_components[name]],
            outputs = []
        )
        
    def generate_settings_model_name_choices(self):
        """
        Generate dropdown choices for remote model names
        
        Input:
            None
        Output: 
            [(key, val)]:   A list of (key, value) pair, and add "✅" to keys if installed
        """
        
        # List model names (values)
        values = sorted(list(self.remote_models.keys()))
        
        # Generate dropdown choices
        res = []
        dict_installed_models = self.dict_installed_models()
        for val in values:
            if val in dict_installed_models:
                res.append((val + " ✅", val))
            else:
                res.append((val, val))
        
        # Return
        return(res)
        
    def generate_settings_model_tag_choices(self, name):
        """
        Generate dropdown choices for remote model tags
        
        Input:
            name:           Model name
        Output: 
            [(key, val)]:   A list of (key, value) pair, and add "✅" to keys if installed
        """
        
        # List model names (values)
        values = self.remote_models[name]
        
        # Generate dropdown choices
        res = []
        dict_installed_tags = self.dict_installed_models().get(name) if self.dict_installed_models().get(name) else []
        for val in values:
            if val in dict_installed_tags:
                res.append((val + " ✅", val))
            else:
                res.append((val, val))
        
        # Return
        return(res)
    
    def build_main(self):
        """
        Build main view
        
        Input:
            None
        Output: 
            None
        """
            
        # Header
        with gr.Column(
            elem_classes=["no-shrink", "main-max-width"]
        ):
            
            # Title
            logo = "gradio_api/file=" + self.current_path + "/images/logo.png"
            gr.Markdown(
                f"""
                <div style="display: flex; align-items: center; gap: 1px;">
                    <img src="{logo}" alt="Logo" style="height:35px; width: 35px;">
                    <h1 style="margin: 0;">llama OnDemand</h1>
                </div>
                """
            )
            #f"![Logo]({logo}) # Ollama OnDemand")
            
            # Model selector
            self.gr_main.model_dropdown = gr.Dropdown(
                choices=self.models,
                value=self.settings["model_selected"],
                interactive=True,
                show_label=False
            )
        
        # Body
        with gr.Column(elem_id="gr-chatbot-container"):
            
            # Main chatbot
            self.gr_main.chatbot = gr.Chatbot(
                height=None,
                show_label=False,
                type="messages",
                show_copy_button=True,
                editable="user",
                allow_tags=False,
                elem_id="gr-chatbot"
            )
            
        # Footer
        with gr.Column(
            elem_classes=["no-shrink", "main-max-width"]
        ):
            
            #Input field (multimodal)
            self.gr_main.user_input = gr.MultimodalTextbox(
                placeholder="Ask anything", 
                submit_btn=True,
                stop_btn=False,
                show_label=False,
                file_types=["image"],
                file_count="multiple",
                max_plain_text_length=10000
            )
    
    def build_left(self):
        """
        Build left sidebar
        
        Input:
            None
        Output: 
            None
        """
        
        with gr.Sidebar(width=350):

            # New Chat button
            self.gr_leftbar.new_btn = gr.Button("💬️ New Chat")
            #self.gr_leftbar.new_btn = gr.Button("New Chat", icon=self.current_path+"/images/new_chat.png")
            
            # Chat selector
            self.gr_leftbar.chat_selector = gr.HTML(
                value=self.generate_chat_selector(),
                elem_id="chat-list-container"
            )
            
            # Hidden elements (For customized JS responses)
            self.gr_leftbar.hidden_input_chatindex = gr.Number(visible=False, elem_id="hidden_input_chatindex")
            self.gr_leftbar.hidden_input_rename = gr.Textbox(visible=False, elem_id="hidden_input_rename")
            self.gr_leftbar.hidden_input_export = gr.Textbox(visible=False)
            self.gr_leftbar.hidden_btn_select = gr.Button(visible=False, elem_id="hidden_btn_select")
            self.gr_leftbar.hidden_btn_rename = gr.Button(visible=False, elem_id="hidden_btn_rename")
            self.gr_leftbar.hidden_btn_export = gr.Button(visible=False, elem_id="hidden_btn_export")
            self.gr_leftbar.hidden_btn_delete = gr.Button(visible=False, elem_id="hidden_btn_delete")

    
    def build_right(self):
        """
        Build right sidebar
        
        Input:
            None
        Output: 
            None
        """
        
        with gr.Sidebar(width=350, position="right", label="Settings", open=False):
            
            # Title
            gr.Markdown("## User Settings")
            
            # Table 1: Generation parameters
            with gr.Tab("Parameters"):
                
                self.generate_settings_component(\
                    name = "num_predict", 
                    component = gr.Number,
                    component_init = {
                        "label":                "(Maximum number of tokens)",
                        "minimum":              0,
                        "precision":            0      
                    }
                )
                
                self.generate_settings_component(\
                    name = "stop", 
                    component = gr.Textbox,
                    component_init = {
                        "label":                "(Stop sequence. Seperated by \",\")",
                    }
                )
                
                self.generate_settings_component(\
                    name = "temperature",
                    component = gr.Slider,
                    component_init = { 
                        "label":                "(Randomness)",
                        "minimum":              0,
                        "maximum":              2,
                        "show_reset_button":    False       
                    }
                )
                
                self.generate_settings_component(\
                    name = "top_p", 
                    component = gr.Slider,
                    component_init = {
                        "label":                "(Nucleus sampling)",
                        "minimum":              0,
                        "maximum":              1,
                        "show_reset_button":    False       
                    }
                )
                
                self.generate_settings_component(\
                    name = "top_k", 
                    component = gr.Number,
                    component_init = {
                        "label":                "(Considers only top K next tokens)",
                        "minimum":              0,
                        "precision":            0      
                    }
                )
                
                self.generate_settings_component(\
                    name = "presence_penalty", 
                    component = gr.Slider,
                    component_init = {
                        "label":                "(Penalty for repeating tokens)",
                        "minimum":              -2,
                        "maximum":              2,
                        "show_reset_button":    False       
                    }
                )
                
                self.generate_settings_component(\
                    name = "frequency_penalty", 
                    component = gr.Slider,
                    component_init = {
                        "label":                "(Penalty for frequent tokens)",
                        "minimum":              -2,
                        "maximum":              2,
                        "show_reset_button":    False       
                    }
                )
                
                self.generate_settings_component(\
                    name = "seed", 
                    component = gr.Number,
                    component_init = {
                        "label":                "(Random seed)",
                        "precision":            0      
                    }
                )
            
            # Table 2: Ollama Models
            with gr.Tab("Models"):
                
                gr.Markdown("### Ollama Model Directory")

                # Directory picker
                self.gr_rightbar.model_path_text = gr.Textbox(
                    value=self.settings["ollama_models"],
                    label="",
                    max_lines=1,
                    container=False,
                    interactive=True,
                    elem_id="dir-path",
                    #submit_btn="📁",      # TODO: Change this to an actual file picker
                )
                
                # Action buttons
                with gr.Row():
                    
                    # Save button
                    self.gr_rightbar.model_path_save = gr.Button(
                        "💾 Save",
                        min_width=0
                    )
                    self.gr_rightbar.model_path_reset = gr.Button(
                        "🔄 Reset",
                        min_width=0
                    )
                    
                    # Reset button
                
                gr.HTML("")
                
                gr.Markdown("### Install Models")
                
                # Initial check whether the path is writable
                self.gr_rightbar.is_model_path_writable = os.access(self.settings["ollama_models"], os.W_OK)

                # List remote models to install
                self.gr_rightbar.model_install_names = gr.Dropdown(
                    choices=self.generate_settings_model_name_choices(),
                    label="Model Name",
                    interactive=self.gr_rightbar.is_model_path_writable
                )
                self.gr_rightbar.model_install_tags = gr.Dropdown(
                    choices=self.generate_settings_model_tag_choices(self.gr_rightbar.model_install_names.value),
                    label="Model Tag",
                    interactive=self.gr_rightbar.is_model_path_writable
                )
                
                # Install / remove button
                with gr.Row():
                    
                    # Initial check which button to display
                    is_installed = self.gr_rightbar.model_install_names.value + ":" + self.gr_rightbar.model_install_tags.value in self.models
                    
                    # Generate buttons
                    self.gr_rightbar.model_install_btn = gr.Button("📥 Install Selected Model", 
                                                                    interactive=self.gr_rightbar.is_model_path_writable,
                                                                    visible=not is_installed)
                    self.gr_rightbar.model_remove_btn = gr.Button("❌ Remove Selected Model", 
                                                                    interactive=self.gr_rightbar.is_model_path_writable,
                                                                    visible=is_installed)
                
                # Status stream
                self.gr_rightbar.model_install_status = gr.Markdown("")
    
    def build_ui(self):
        """
        Build UI
        
        Input:
            None
        Output: 
            None
        """
        
        with gr.Blocks(
            css_paths=self.current_path+'/grblocks.css',
            title="Ollama OnDemand",
            head_paths=self.current_path+'/head.html'
        ) as self.demo:
            
            #----------------------------------------------------------
            # Create UI
            #----------------------------------------------------------
            
            # Build main view
            self.build_main()
                
            # Build left sidebar: Chat Sessions
            self.build_left()
                
            # Build right sidebar: User Settings
            self.build_right()
            
            #----------------------------------------------------------
            # Event handlers
            #----------------------------------------------------------
            
            # Register event handlers in main view
            self.register_main()
            
            # Register event handlers in left sidebar
            self.register_left()
            
            # Register event handlers in right sidebar
            self.register_right()

            #----------------------------------------------------------
            # Load UI
            #----------------------------------------------------------
            
            self.demo.load(
                fn=lambda : cs.load_chat(0),
                inputs=[],
                outputs=[self.gr_main.chatbot]
            )
    
    def launch(self):
        """
        Launch UI after it is built.
        
        Input:
            None
        Output: 
            None
        """
        
        self.demo.launch(
            server_name=self.args.host,
            server_port=self.args.port,
            root_path=self.args.root_path,
            allowed_paths=[self.current_path]
        )
    
    
    #------------------------------------------------------------------
    # Register UI
    #------------------------------------------------------------------
    
    # Workflows
    
    def workflow_after_streaming(self, event_handler):
        """
        After streaming finished workflow
        
        Input:
            event_handler:  Event handlers after input workflow
        Output: 
            None
        """
        return (
            event_handler.then(
                fn=self.update_chat_selector,       # Update chat title if needed
                inputs=[],
                outputs=[self.gr_leftbar.chat_selector]
            ).then(
                fn=lambda: self.enable_components(True), 
                                                    # Enable certain components
                inputs=[],
                outputs=[self.gr_leftbar.chat_selector, \
                         self.gr_leftbar.new_btn]
            ).then(
                fn=self.save_chat_history,          # Save chat history
                inputs=[],
                outputs=[]
            )
        )
    
    def workflow_basic_streaming(self, event_handler):
        """
        Basic streaming workflow
        
        Input:
            event_handler:  Event handlers (excluding before and after)
        Output: 
            None
        """
        return (
            self.workflow_after_streaming(
                event_handler.then(
                    fn=lambda: self.enable_components(False),
                                                        # Disable certain components
                    inputs=[],
                    outputs=[self.gr_leftbar.chat_selector, \
                             self.gr_leftbar.new_btn]
                ).then(
                    fn=self.stream_chat,                # Start streaming
                    inputs=[],
                    outputs=[self.gr_main.chatbot, self.gr_main.user_input]
                )
            )
        )
        
    def workflow_change_model_path(self, event_handler):
        """
        Workflow to handle model path change
        
        Input:
            event_handler:  Event handler reference
        Output: 
            None
        """
        
        error=gr.State("")
        
        event_handler(                                      # First disable components
            fn=lambda : [gr.update(interactive=False)]*8,
            inputs=[],
            outputs=[
                self.gr_main.model_dropdown,
                self.gr_rightbar.model_path_text,
                self.gr_rightbar.model_path_save,
                self.gr_rightbar.model_path_reset,
                self.gr_rightbar.model_install_names,
                self.gr_rightbar.model_install_tags,
                self.gr_rightbar.model_install_btn,
                self.gr_rightbar.model_remove_btn
            ]
        ).then(                                             # Then handle model path change
            fn=self.settings_model_path_change,
            inputs=[self.gr_rightbar.model_path_text],
            outputs=[
                error,
                self.gr_main.model_dropdown,
                self.gr_rightbar.model_path_text,
                self.gr_rightbar.model_path_save,
                self.gr_rightbar.model_path_reset,
                self.gr_rightbar.model_install_names,
                self.gr_rightbar.model_install_tags,
                self.gr_rightbar.model_install_btn,
                self.gr_rightbar.model_remove_btn
            ]
        ).then(                                             # Then raise error if exists
            fn=self.raise_error,
            inputs=[error],
            outputs=[]
        )
        
    def workflow_install_remove_model(self, event_handler, action):
        """
        Workflow to handle install & a remove model
        
        Input:
            event_handler:  Event handler reference
            action:         "install" or "remove"
        Output: 
            None
        """
        
        error = gr.State("")
        
        event_handler(                                      # First disable components
            fn=lambda : [gr.update(interactive=False)]*8,
            inputs=[],
            outputs=[
                self.gr_main.model_dropdown,
                self.gr_rightbar.model_path_text,
                self.gr_rightbar.model_path_save,
                self.gr_rightbar.model_path_reset,
                self.gr_rightbar.model_install_names,
                self.gr_rightbar.model_install_tags,
                self.gr_rightbar.model_install_btn,
                self.gr_rightbar.model_remove_btn
            ]
        ).then(                                             # Then install / remove model
            fn=self.settings_model_install_remove,
            inputs=[
                self.gr_rightbar.model_install_names, 
                self.gr_rightbar.model_install_tags,
                gr.State(action)
            ],
            outputs=[
                error,
                self.gr_rightbar.model_install_status
            ]
        ).then(                                             # Then update disabled components
            fn=self.settings_model_install_after,
            inputs=[],
            outputs=[
                self.gr_main.model_dropdown,
                self.gr_rightbar.model_path_text,
                self.gr_rightbar.model_path_save,
                self.gr_rightbar.model_path_reset,
                self.gr_rightbar.model_install_names,
                self.gr_rightbar.model_install_tags,
                self.gr_rightbar.model_install_btn,
                self.gr_rightbar.model_remove_btn
            ]
        ).then(                                             # Then raise error if exists
            fn=self.raise_error,
            inputs=[error],
            outputs=[]
        )
    
    def register_main(self):
        """
        Register event handlers in main view
        
        Input:
            None
        Output: 
            None
        """
            
        # Model selector
        self.gr_main.model_dropdown.change(
            fn=self.select_model,
            inputs=[self.gr_main.model_dropdown],
            outputs=[],
        )
        
        # Chatbot: Retry
        self.workflow_basic_streaming(
            self.gr_main.chatbot.retry(
                fn=self.retry,
                inputs=[],
                outputs=[self.gr_main.chatbot, self.gr_main.user_input]
            )
        )
        
        # Chatbot: Edit
        self.workflow_basic_streaming(
            self.gr_main.chatbot.edit(
                fn=self.edit,
                inputs=[],
                outputs=[self.gr_main.chatbot, self.gr_main.user_input]
            )
        )

        # User input: Submit new message
        self.workflow_basic_streaming(
            self.gr_main.user_input.submit(
                fn=self.new_message,
                inputs=[self.gr_main.user_input],
                outputs=[self.gr_main.chatbot, self.gr_main.user_input]
            )
        )
        
        # User input: Stop
        self.workflow_after_streaming( 
            self.gr_main.user_input.stop(
                fn=self.stop_stream_chat,
                inputs=[],
                outputs=[self.gr_main.chatbot, self.gr_main.user_input]
            )
        )
    
    def register_left(self):
        """
        Register event handlers in left sidebar
        
        Input:
            None
        Output: 
            None
        """
            
        # New chat button
        self.gr_leftbar.new_btn.click(
            fn=self.new_chat,
            inputs=[],
            outputs=[self.gr_leftbar.chat_selector, self.gr_main.chatbot]
        ).then(
            fn=self.save_chat_history,              # Save chat history
            inputs=[],
            outputs=[]
        )
        
        # Change selected chat
        self.gr_leftbar.hidden_btn_select.click(
            fn=self.select_chat,
            inputs=[self.gr_leftbar.hidden_input_chatindex],
            outputs=[self.gr_main.chatbot]
        )
        
        # Rename chat
        self.gr_leftbar.hidden_btn_rename.click(    # Do rename
            fn=self.rename_chat,
            inputs=[self.gr_leftbar.hidden_input_chatindex, self.gr_leftbar.hidden_input_rename],
            outputs=[]
        ).then(
            fn=self.save_chat_history,              # Save chat history
            inputs=[],
            outputs=[]
        )

        # Export chat
        self.gr_leftbar.hidden_btn_export.click(
            fn=self.export_chat,
            inputs=[self.gr_leftbar.hidden_input_chatindex],
            outputs=[self.gr_leftbar.hidden_input_export]
        ).then(
            fn=None,
            inputs=[],
            outputs=[self.gr_leftbar.hidden_input_export],
            js="(json) => trigger_json_download('chat_history.json', json)"
        )
        
        # Delete chat
        self.gr_leftbar.hidden_btn_delete.click(
            fn=self.delete_chat,                    # Do delete
            inputs=[self.gr_leftbar.hidden_input_chatindex],
            outputs=[self.gr_leftbar.chat_selector, self.gr_main.chatbot]
        ).then(
            fn=self.save_chat_history,              # Save chat history
            inputs=[],
            outputs=[]
        )
    
    def register_right(self):
        """
        Register event handlers in right sidebar
        
        Input:
            None
        Output: 
            None
        """
        
        # Change model path (hit enter)
        self.workflow_change_model_path(self.gr_rightbar.model_path_text.submit)
        
        # Change model path (click "save" button)
        self.workflow_change_model_path(self.gr_rightbar.model_path_save.click)
        
        # Reset model path
        self.workflow_change_model_path(
            self.gr_rightbar.model_path_reset.click(            # First update textbox to default
                fn=lambda : self.args.ollama_models,
                inputs=[],
                outputs=[self.gr_rightbar.model_path_text]
            ).then                                              # Then execute the workflow
        )
        
        # Change install model name
        self.gr_rightbar.model_install_names.change(
            fn=self.settings_update_model_tags,
            inputs=[self.gr_rightbar.model_install_names],
            outputs=[self.gr_rightbar.model_install_tags]
        ).then(                                                 # Force update when system trigger change
            fn=self.settings_update_model_buttons,
            inputs=[self.gr_rightbar.model_install_names,
                    self.gr_rightbar.model_install_tags],
            outputs=[self.gr_rightbar.model_install_btn,
                     self.gr_rightbar.model_remove_btn]
        )
        
        # Change install model tag (when user update)
        self.gr_rightbar.model_install_tags.input(
            fn=self.settings_update_model_buttons,
            inputs=[self.gr_rightbar.model_install_names,
                    self.gr_rightbar.model_install_tags],
            outputs=[self.gr_rightbar.model_install_btn,
                     self.gr_rightbar.model_remove_btn]
        )
        
        # Install selected models
        self.workflow_install_remove_model(
            event_handler = self.gr_rightbar.model_install_btn.click,
            action = "install"
        )
        
        # Remove selected models
        self.workflow_install_remove_model(
            event_handler = self.gr_rightbar.model_remove_btn.click,
            action = "remove"
        )


def main():
    
    app = OllamaOnDemandUI(get_args())
    app.build_ui()
    app.launch()

if __name__ == "__main__":
    main()
    