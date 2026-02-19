# Event listeners and workflows

import gradio as gr


class ListenerMixin:
    """Mixin class for event listener registration and workflow methods."""
    
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
