# Event listeners and workflows

import os
import json
import re
import gradio as gr
import chatsessions as cs
import multimodal as mm


class ListenerMixin:
    """Mixin class for event handler callbacks, listener registration and workflow methods."""
    
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
            ).then(
                fn=None,
                inputs=[],
                outputs=[],
                js="collapse_thinking()"
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
                self.gr_main.model_dropdown,
                self.gr_rightbar.model_path_text,
                self.gr_rightbar.model_path_save,
                self.gr_rightbar.model_path_reset,
                self.gr_rightbar.model_install_names,
                self.gr_rightbar.model_install_tags,
                self.gr_rightbar.model_install_btn,
                self.gr_rightbar.model_remove_btn
            ]
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
            outputs=[self.gr_rightbar.model_install_status]
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
        
        # User input: Change textarea height
        self.gr_main.user_input.change(
            fn=None,
            inputs=[],
            outputs=[],
            js="""
            function() {
                const container = document.getElementById('gr-chatbot-container');
                const header = document.getElementById('gr-main-header');
                const inputBox = document.getElementById('gr-user-input');
                if (container && inputBox && header) {
                    const inputHeight = inputBox.offsetHeight;
                    const headerHeight = header.offsetHeight;
                    container.style.height = `calc(100dvh - ${inputHeight + headerHeight + 70}px)`;
                }
            }
            """
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
        ).then(
            fn=None,
            inputs=[],
            outputs=[],
            js="collapse_thinking()"
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
        self.gr_rightbar.model_install_names.change(            # Force update when system trigger change
            fn=self.settings_update_model_tags,
            inputs=[self.gr_rightbar.model_install_names],
            outputs=[self.gr_rightbar.model_install_tags]
        ).then(
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
