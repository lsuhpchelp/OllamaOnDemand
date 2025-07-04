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
import gradio as gr
from arg import get_args
import chatsessions as cs
import usersettings as us

#======================================================================
#                           Main UI class
#======================================================================

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
        
        # Start Ollama server and save client(s)
        self.start_server()
        self.client = self.get_client()
        
        # Get model(s)
        self.models = self.get_model_list()
        self.model_selected = self.settings["model_selected"] if self.settings["model_selected"] in self.models else self.models[0]

    
    #------------------------------------------------------------------
    # Server connection
    #------------------------------------------------------------------
        
    def start_server(self):
        """Start Ollama Server"""
        
        # Define environment variables
        env = os.environ.copy()
        env["OLLAMA_HOST"] = self.args.ollama_host
        env["OLLAMA_MODELS"] = self.args.ollama_models
        env["OLLAMA_SCHED_SPREAD"] = self.args.ollama_spread_gpu

        # Start the Ollama server
        print("Starting Ollama server on " + self.args.ollama_host)
        process = subprocess.Popen(
            ["ollama", "serve"],
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        
        # Wait until the server starts
        for _ in range(60): 
            try:
                if requests.get(self.args.ollama_host).ok:
                    print("Ollama server is running")
                    break
            except:
                pass
            print("Waiting for Ollama server to start...")
            time.sleep(1)
        else:
            raise RuntimeError("Ollama server failed to start in 1 min. Something is wrong.")
            
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
    
    def get_model_list(self):
        """
        Get list of models.
        
        Input:
            None
        Output: 
            models: List of all model names
        """
        
        models = [model.model for model in self.client.list().models]
        return models if models else ["(No model is found. Create a model to continue...)"]
                    
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

            # Generate next chat results
            response = self.client.chat(
                model = self.model_selected,
                messages = self.chat_history,
                stream = True
            )

            # Stream results in chunks while not interrupted
            for chunk in response:
                if not self.is_streaming:
                    break
                delta = chunk.get("message", {}).get("content", "")
                self.chat_history[-1]["content"] += delta
                yield self.chat_history, gr.update(value="", submit_btn=False, stop_btn=True)
        
        # Once finished, set streaming to False
        self.is_streaming = False
        
        # Final update components
        yield self.chat_history, gr.update(value="", submit_btn=True, stop_btn=False)
    
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
        yield self.chat_history, gr.update(value="", submit_btn=True, stop_btn=False)
    
    def new_message(self, user_message):
        """
        When a new message is submitted, set chatbot & input field before start streaming
        
        Input:
            user_message:       User's input
        Output: 
            chat_history:       Current chat history
            user_input:         Update user input field to "" and button face
        """
        
        # Append user message to chat history
        self.chat_history.append({"role": "user", "content": user_message["text"]})
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
        
        # Append user message to chat history
        self.chat_history[:] = self.chat_history[:retry_data.index+1]
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
        if self.chat_title == "":
            
            # Generate a chat title, but do not alter chat_history
            response = self.client.chat(
                model = self.model_selected,
                messages = self.chat_history + \
                    [ { "role": "user", 
                        "content": "Summarize this entire conversation with less than six words. Be objective and formal (Don't use first person expression). No punctuation."} ],
                stream = False
            )
            
            # Set new title
            new_title = response['message']['content']
            new_title = re.sub(r"<think>.*?</think>", "", new_title, flags=re.DOTALL).strip()
            self.chat_title = new_title
            cs.set_chat_title(self.chat_index, new_title)
            
        return gr.update(choices=cs.get_chat_titles(), value=cs.get_chat_titles()[self.chat_index])
    
    def select_model(self, evt: gr.SelectData):
        """
        Change selected model.
        
        Input:
            evt:            Event instance (as gr.SelectData) 
        Output: 
            None
        """
        
        # Change selected model
        self.model_selected = evt.value
        
        # Save user settings
        self.settings["model_selected"] = evt.value
        self.save_settings()
            
    def select_chat(self, evt: gr.SelectData):
        """
        Change selected chat.
        
        Input:
            evt:            Event instance (as gr.SelectData) 
        Output: 
            chat_history:   Chat history
        """
        
        # Update current chat
        self.update_current_chat(evt.index)
        
        # Return chat history to chatbot
        return self.chat_history
        
    # Register New Chat button
    def new_chat(self):
        """
        Change selected chat.
        
        Input:
            None
        Output: 
            chat_selector:  Chat selector update
            chat_history:   Chat history
        """
        
        # Update current chat
        self.update_current_chat(-1)
        
        # Return updated chat selector and current chat
        return gr.update(choices=cs.get_chat_titles(), value=cs.get_chat_titles()[0]), self.chat_history

    def delete_chat(self):
        """
        Delete the current chat and update UI.
        
        Input:
            None
        Output:
            chat_selector:  Chat selector update
            chat_history:   Chat history
        """
        
        # Delegate deletion to chatsessions
        cs.delete_chat(self.chat_index)
        
        # Adjust selection: try to select next, else previous, else show blank
        num_chats = len(cs.get_chat_titles())
        if num_chats == 0:
            return self.new_chat()
        else:
            if self.chat_index >= num_chats:
                self.chat_index = num_chats - 1  # Move to previous if at end
            self.update_current_chat(self.chat_index)
        
        return gr.update(choices=cs.get_chat_titles(), value=cs.get_chat_titles()[self.chat_index]), self.chat_history
    
    
    #------------------------------------------------------------------
    # Build UI
    #------------------------------------------------------------------
    
    def build_ui(self):
        """
        Build UI
        
        Input:
            None
        Output: 
            None
        """

        with gr.Blocks(
            css_paths=os.path.dirname(os.path.abspath(__file__))+'/grblocks.css',
            title="Ollama OnDemand"
        ) as self.demo:
            
            #----------------------------------------------------------
            # Create UI
            #----------------------------------------------------------
            
            # Header
            with gr.Column(
                elem_classes=["no-shrink", "main-max-width"]
            ):
                
                # Title
                gr.Markdown("# Ollama OnDemand")
                
                # Model selector
                model_dropdown = gr.Dropdown(
                    choices=self.models,
                    value=self.model_selected,
                    interactive=True,
                    show_label=False
                )
            
            # Body
            with gr.Column(elem_id="gr-chatbot-container"):
                
                # Main chatbot
                chatbot = gr.Chatbot(
                    height=None,
                    show_label=False,
                    type="messages",
                    show_copy_button=True,
                    editable="user",
                    allow_tags=True,
                    elem_id="gr-chatbot"
                )
                
            # Footer
            with gr.Column(
                elem_classes=["no-shrink", "main-max-width"]
            ):
                
                #Input field (multimodal)
                user_input = gr.MultimodalTextbox(
                    placeholder="Ask anything", 
                    submit_btn=True,
                    stop_btn=False,
                    show_label=False
                )
                
            # Left sidebar: Chat Sessions
            with gr.Sidebar(width=410):

                # New chat and delete chat
                with gr.Row():
                    
                    # New Chat button
                    new_btn = gr.Button("New")
                    
                    # Delete Chat button
                    del_btn = gr.Button("Delete")
                
                # Confirmation "dialog"
                with gr.Group(visible=False) as del_btn_dialog:
                    gr.Markdown(
                        '<b>Are you sure you want to delete selected chat?</b>', \
                        elem_id="del-button-dialog"
                    )
                    with gr.Row():
                        del_btn_confirm = gr.Button("Yes", variant="stop")
                        del_btn_cancel = gr.Button("Cancel")
                
                # Chat selector
                chat_selector = gr.Radio(
                    choices=cs.get_chat_titles(),
                    show_label=False,
                    type="index",
                    value=cs.get_chat_titles()[0], 
                    interactive=True,
                    elem_id="chat-selector"
                )
            
            #----------------------------------------------------------
            # Event handler workflows
            #----------------------------------------------------------
            
            # After streaming finished workflow:
            def after_streaming_workflow(event_handler):
                return (
                    event_handler.then(
                        fn=self.update_chat_selector,       # Update chat title if needed
                        inputs=[],
                        outputs=[chat_selector]
                    ).then(
                        fn=lambda: [gr.update(interactive=True)] * 3,
                                                            # Re-enable disabled components
                        inputs=[],
                        outputs=[chat_selector, new_btn, del_btn]
                    ).then(
                        fn=self.save_chat_history,          # Save chat history
                        inputs=[],
                        outputs=[]
                    )
                )
            
            # Basic streaming workflow:
            def basic_streaming_workflow(event_handler):
                return (
                    after_streaming_workflow(
                        event_handler.then(
                            fn=lambda: [gr.update(interactive=False)] * 3,
                                                                # Disable certain components
                            inputs=[],
                            outputs=[chat_selector, new_btn, del_btn]
                        ).then(
                            fn=self.stream_chat,                # Start streaming
                            inputs=[],
                            outputs=[chatbot, user_input]
                        )
                    )
                )
            
            #----------------------------------------------------------
            # Event handlers
            #----------------------------------------------------------
            
            # New chat button
            new_btn.click(
                fn=self.new_chat,
                inputs=[],
                outputs=[chat_selector, chatbot]
            ).then(
                fn=self.save_chat_history,              # Save chat history
                inputs=[],
                outputs=[]
            )

            # Delete chat button
            del_btn.click(                              # Toggle confirmation dialog
                fn=lambda: gr.update(visible=True),
                inputs=[],
                outputs=[del_btn_dialog]
            )
            
            # Delete chat: Confirm
            del_btn_confirm.click(
                fn=self.delete_chat,                    # Do delete
                inputs=[],
                outputs=[chat_selector, chatbot]
            ).then(
                fn=lambda: gr.update(visible=False),    # Hide dialog
                inputs=[],
                outputs=[del_btn_dialog]
            ).then(
                fn=self.save_chat_history,              # Save chat history
                inputs=[],
                outputs=[]
            )
            
            # Delete chat: Cancel
            del_btn_cancel.click(                       # Hide dialog
                fn=lambda: gr.update(visible=False),
                inputs=[],
                outputs=[del_btn_dialog]
            )
            
            # Chat selector
            chat_selector.select(
                fn=self.select_chat,
                inputs=[],
                outputs=[chatbot]
            )
            
            # Model selector
            model_dropdown.select(
                fn=self.select_model,
                inputs=[],
                outputs=[],
            )
            
            # Chatbot: Retry
            basic_streaming_workflow(
                chatbot.retry(
                    fn=self.retry,
                    inputs=[],
                    outputs=[chatbot, user_input]
                )
            )

            # User input: Submit new message
            basic_streaming_workflow(
                user_input.submit(
                    fn=self.new_message,
                    inputs=[user_input],
                    outputs=[chatbot, user_input]
                )
            )
            
            # User input: Stop
            after_streaming_workflow( 
                user_input.stop(
                    fn=self.stop_stream_chat,
                    inputs=[],
                    outputs=[chatbot, user_input]
                )
            )

            #----------------------------------------------------------
            # Load UI
            #----------------------------------------------------------
            
            self.demo.load(
                fn=lambda : cs.load_chat(0),
                inputs=[],
                outputs=[chatbot]
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
            root_path=self.args.root_path
        )


def main():
    
    app = OllamaOnDemandUI(get_args())
    app.build_ui()
    app.launch()

if __name__ == "__main__":
    main()
    