# =============================
# Ollama OnDemand
# Author: Dr. Jason Li (jasonli3@lsu.edu)
# =============================

import os
import requests
import json
import subprocess
import time
import re
import ollama
import chatsessions as cs
import multimodal as mm
        
# Set Gradio temp files directory before loading Gradio
# (Fix an issue Gradio will create temp folders upon loading)
from arg import get_args
args = get_args()
os.environ["GRADIO_TEMP_DIR"] = args.workdir + "/cache"
import gradio as gr

from utils import UtilsMixin
from ui_builders import UIBuilderMixin
from listeners import ListenerMixin

#======================================================================
#                           Main UI class
#======================================================================

class GradioComponents:
    """An empty class used to deposit Gradio components."""
    pass

class OllamaOnDemandUI(UtilsMixin, UIBuilderMixin, ListenerMixin):
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
        
        # Clean up orphaned cached files
        self.cleanup_cache()
        
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
        
        # Compile regular expression for think tag replacement for display
        self.think_tags = {
            "head":    "<div class='thinking-block'><details open class='thinking'><summary><i><b>(Thinking...)</b></summary>\n\n<br>",
            "tail":    "</i></details></div><br>\n\n"
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
            None (raise error) or error message (return for future use)
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
        url = "http://" + self.args.ollama_host if not self.args.ollama_host.startswith(("http://", "https://")) else self.args.ollama_host
        for _ in range(60): 
            
            try:
                if requests.get(url).ok:
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
        
            # Make a copy of options for pre-processing
            options = self.settings.get("options").copy() if self.settings.get("options") else {}
            
            # Pre-process "stop" sequence
            if (options.get("stop")):
                options["stop"] = options["stop"].split(",")
            
            # Pre-process "think" option
            think = None
            if ("think" in options):
                think = options["think"]
                del options["think"]
                if (isinstance(think, str) and self.settings["model_selected"].split(":")[0] != "gpt-oss"):
                    think = True
                    
            # Pre-process "keep_alive" option
            keep_alive = None
            if ("keep_alive" in options):
                keep_alive = options["keep_alive"]
                del options["keep_alive"]

            # Generate next chat results
            response = self.client.chat(
                model = self.settings["model_selected"],
                messages = self.chat_history_stream(),      # Using formatted chat history for streaming
                stream = True,
                think = think,
                keep_alive = keep_alive,
                options = options
            )
            
            # Try to stream
            try:
            
                # Reset thinking flag
                is_thinking = False

                # Stream results in chunks while not interrupted
                for chunk in response:
                
                    # Breake if interrupted
                    if not self.is_streaming:
                        break
                    
                    # Handle reasoning
                    
                    # If "thinking" attribute is not empty, always put it in "thinking"
                    if (chunk.message.thinking):
                    
                        self.chat_history[-1]["thinking"] += chunk.message.thinking
                        
                    # Otherwise, check "content" attribute
                    else:
                    
                        # If "is_thinking" is on
                        if (is_thinking):
                        
                            # Append "content" to "thinking"
                            self.chat_history[-1]["thinking"] += chunk.message.content or ""
                            
                            # If "thinking" ends with "</think>", turn off "is_thinking".
                            #   Following chunks will be added to "content"
                            if (self.chat_history[-1]["thinking"].rstrip()[-8:] == "</think>"):
                            
                                is_thinking = False
                                self.chat_history[-1]["thinking"] = self.chat_history[-1]["thinking"].rstrip()[:-8]
                            
                        # If "is_thinking" is off
                        else:
                        
                            # Append "content" to "content"
                            self.chat_history[-1]["content"] += chunk.message.content or ""
                            
                            # If "content" starts with "<think>", turn on "is_thinking" and move "content" to "thinking". 
                            #   Following chunks will be added to "thinking"
                            if (self.chat_history[-1]["content"].lstrip()[:7] == "<think>"):
                            
                                is_thinking = True
                                self.chat_history[-1]["thinking"] = self.chat_history[-1]["content"].lstrip()[7:]
                                self.chat_history[-1]["content"] = ""
                    
                    # Yield results
                    #yield self.chat_history, gr.update(value="", submit_btn=False, stop_btn=True)
                    yield self.chat_history_display(), gr.update(value="", submit_btn=False, stop_btn=True)
            
            # If error occurs
            except Exception as error: 
                
                self.chat_history[-1]["content"] = "[Error] An error has occurred! Please see error message and and try again!"
                gr.Warning(str(error), title="Error")
                yield self.chat_history_display(), gr.update(value="", submit_btn=False, stop_btn=True)
        
        # Once finished, set streaming to False
        self.is_streaming = False
        
        # If assistant's response does not contain "thinking", delete the attribute
        if (not self.chat_history[-1]["thinking"]):
            del self.chat_history[-1]["thinking"]
        
        # Final update components
        yield self.chat_history_display(), gr.update(value="", submit_btn=True, stop_btn=False)
    
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
        yield self.chat_history_display(), gr.update(value="", submit_btn=True, stop_btn=False)
    
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
        # If attachments exist (multimodal)
        if len(user_input["files"]) > 0:
            
            # If any non-image is uploaded, process them first
            user_message = {
                "role":     "user", 
                "content":  user_input["text"],
                "files":    user_input["files"]
            }
            
            # Process the attachments for any non-image
            user_message = mm.format_chat_upload(user_message)
            
        # No attachment
        else:
            user_message = {
                "role":     "user", 
                "content":  user_input["text"]
            }
            
        # Append user message to history
        self.chat_history.append(user_message)
        self.chat_history.append({"role": "assistant", "content": "", "thinking": ""})
            
        # Set streaming to True
        self.is_streaming = True
        
        # Update components
        yield self.chat_history_display(), gr.update(value="", submit_btn=False, stop_btn=True)
    
    def retry(self, retry_data: gr.RetryData):
        """
        When retry request is sent, set chatbot & input field before start streaming
        
        Input:
            retry_data:         Event instance (as gr.RetryData)
        Output: 
            chat_history:       Current chat history
            user_input:         Update user input field to "" and button face
        """
        
        # Find the correct index
        (i, index) = (0, retry_data.index)
        while (i <= index):
            if (self.chat_history[i].get("images")):
                index -= 1
            elif (self.chat_history[i].get("files")):
                index -= len(self.chat_history[i]["files"])
            i += 1
        
        # Revert to previous user message
        self.chat_history[:] = self.chat_history[:index+1]
        self.chat_history.append({"role": "assistant", "content": "", "thinking": ""})
            
        # Set to streaming and continue
        self.is_streaming = True
        
        # Update components
        yield self.chat_history_display(), gr.update(value="", submit_btn=False, stop_btn=True)
    
    def edit(self, edit_data: gr.EditData):
        """
        When edit request is sent, set chatbot & input field before start streaming
        
        Input:
            edit_data:          Event instance (as gr.EditData)
        Output: 
            chat_history:       Current chat history
            user_input:         Update user input field to "" and button face
        """
        
        # Find the correct index
        (i, index) = (0, edit_data.index)
        while (i <= index):
            if (self.chat_history[i].get("images")):
                index -= 1
            elif (self.chat_history[i].get("files")):
                index -= len(self.chat_history[i]["files"])
            i += 1
        
        # Revert to edited user message
        self.chat_history[:] = self.chat_history[:index+1]
        self.chat_history[-1]["content"] = edit_data.value
        self.chat_history.append({"role": "assistant", "content": "", "thinking": ""})
            
        # Set to streaming and continue
        self.is_streaming = True
        
        # Update components
        yield self.chat_history_display(), gr.update(value="", submit_btn=False, stop_btn=True)
        
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
        return self.chat_history_display()
        
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
            return gr.update(value=self.generate_chat_selector()), self.chat_history_display()
            
        # Otherwise, keep current chat index and reload
        else:
        
            self.update_current_chat(self.chat_index)
            return gr.update(value=self.generate_chat_selector()), self.chat_history_display()
    
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
                self.settings["ollama_models"] = model_path_old
                
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
                    self.settings["ollama_models"] = model_path_old
                    
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
        
        # Raise error
        if (error):
            gr.Warning(error, title="Error")
        
        # Get model install name and tag lists
        choices_names = self.generate_settings_model_name_choices()
        choices_tags = self.generate_settings_model_tag_choices(choices_names[0][1])
        is_installed = choices_names[0][1]+":"+choices_tags[0][1] in self.models
        
        # Return
        return [gr.update(choices=self.list_installed_models(formatted=True), value=self.models[0], interactive=True),     # Model selector
                gr.update(value=self.settings["ollama_models"], interactive=True),          # Model path textbox
                gr.update(interactive=True),                                                # Model path save button
                gr.update(interactive=True),                                                # Model path reset button
                gr.update(choices=choices_names, value=choices_names[0][1], 
                          interactive=self.gr_rightbar.is_model_path_writable),             # Model install name list
                gr.update(choices=choices_tags, value=choices_tags[0][1], 
                          interactive=self.gr_rightbar.is_model_path_writable),             # Model install tag list
                gr.update(visible=not is_installed, 
                          interactive=self.gr_rightbar.is_model_path_writable),             # Model install button
                gr.update(visible=is_installed,
                          interactive=self.gr_rightbar.is_model_path_writable)]             # Model remove button
                
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
            status:             Status stream
        """
        
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
                    yield status
                    
            elif (action == "remove"):
            
                # Remove selected model
                self.client.delete(name+":"+tag)
                
            else:
            
                gr.Warning("Invalid action!", title="Error")
            
            # Update model list
            self.models = self.list_installed_models()
                
            # Reset user settings
            self.settings["model_selected"] = self.models[0]
            
        except Exception as e:
            
            # Raise error
            gr.Warning(str(e), title="Error")
                
        # Return
        yield ""
               
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
        
        # Get model install name and tag lists
        choices_names = self.generate_settings_model_name_choices()
        choices_tags = self.generate_settings_model_tag_choices(choices_names[0][1])
        is_installed = choices_names[0][1]+":"+choices_tags[0][1] in self.models
                
        # Return
        return [gr.update(choices=self.list_installed_models(formatted=True), \
                          value=self.settings["model_selected"], \
                          interactive=True),                                                # Model selector
                gr.update(interactive=True),                                                # Model path textbox
                gr.update(interactive=True),                                                # Model path save button
                gr.update(interactive=True),                                                # Model path reset button
                gr.update(choices=choices_names, value=choices_names[0][1], 
                          interactive=self.gr_rightbar.is_model_path_writable),             # Model install name list
                gr.update(choices=choices_tags, value=choices_tags[0][1], 
                          interactive=self.gr_rightbar.is_model_path_writable),             # Model install tag list
                gr.update(visible=not is_installed, 
                          interactive=self.gr_rightbar.is_model_path_writable),             # Model install button
                gr.update(visible=is_installed,
                          interactive=self.gr_rightbar.is_model_path_writable)]             # Model remove button


def main():
    
    app = OllamaOnDemandUI(args)
    app.build_ui()
    app.launch()

if __name__ == "__main__":
    main()
    