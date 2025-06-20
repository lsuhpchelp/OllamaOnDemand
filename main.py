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
        self.update_current_chat(0)                 # Load chat at 0 index. Also initialize:
                                                    #   self.chat_index     - Current chat index
                                                    #   self.chat_title     - Current chat title
                                                    #   self.chat_history   - Current chat history
        
        # Start Ollama server and save client(s)
        self.start_server()
        self.client = self.get_client()
        
        # Get model(s)
        self.models = self.get_model_list()
        self.model_selected = self.models[0]

    
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

        
    #------------------------------------------------------------------
    # Event handler
    #------------------------------------------------------------------
    
    def _stream_chat(self):
        """
        Stream chat (invoked by new/edit/retry).
        
        Input:
            None
        Output: 
            chat_history:       Current chat history
            user_input:         Update user input field to "" and button face
        """

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
            delta = delta.replace("<think>", "(Thinking...)").replace("</think>", "(/Thinking...)")
            self.chat_history[-1]["content"] += delta
            yield self.chat_history, gr.update(value="", submit_btn=False, stop_btn=True)
    
    def new_message(self, user_message):
        """
        New user message
        
        Input:
            user_message:       User's input
        Output: 
            chat_history:       Current chat history
            user_input:         Update user input field to "" and button face
        """

        # If currently not streaming, start streaming
        if not self.is_streaming:
            
            # Set streaming to True
            self.is_streaming = True
            
            # Append user message to chat history
            self.chat_history.append({"role": "user", "content": user_message["text"]})
            self.chat_history.append({"role": "assistant", "content": ""})
            yield self.chat_history, gr.update(value="", submit_btn=False, stop_btn=True)

            # Generate next chat results
            yield from self._stream_chat()
        
        self.is_streaming = False
        yield self.chat_history, gr.update(value="", submit_btn=True, stop_btn=False)
    
    def retry(self, retry_data: gr.RetryData):
        """
        New user message
        
        Input:
            retry_data:         Event instance (as gr.RetryData)
        Output: 
            chat_history:       Current chat history
            user_input:         Update user input field to "" and button face
        """

        # If currently not streaming, start streaming
        if not self.is_streaming:
            
            # Set to streaming and continue
            self.is_streaming = True
            
            # Append user message to chat history
            self.chat_history = self.chat_history[:retry_data.index+1]
            self.chat_history.append({"role": "assistant", "content": ""})
            yield self.chat_history, gr.update(value="", submit_btn=False, stop_btn=True)

            # Generate next chat results
            yield from self._stream_chat()
        
        self.is_streaming = False
        yield self.chat_history, gr.update(value="", submit_btn=True, stop_btn=False)
        
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
        self.model_selected = evt.value
            
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
            
            gr.Markdown(
                "# Ollama OnDemand",
                elem_id="no-shrink"
            )
            
            # Main
            with gr.Column(elem_id="main-column"):
                    
                # Model selector
                with gr.Row(elem_id="no-shrink"):
                    model_dropdown = gr.Dropdown(
                        choices=self.models,
                        value=self.model_selected,
                        interactive=True,
                        show_label=False
                    )
                
                # Main chatbot
                chatbot = gr.Chatbot(
                    show_label=False,
                    type="messages",
                    show_copy_button=True,
                    editable="user",
                    container=False,
                    elem_id="gr-chatbot"
                )
                
                # Input field (multimodal)
                with gr.Row(elem_id="no-shrink"):
                    user_input = gr.MultimodalTextbox(
                        placeholder="Type your message here…", 
                        submit_btn=True,
                        stop_btn=False,
                        show_label=False
                    )
                
            # Left sidebar: Chat Selection
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
                        del_btn_cancle = gr.Button("Cancel")
                
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
            # Register listeners
            #----------------------------------------------------------
            
            # New chat button
            new_btn.click(
                fn=self.new_chat,
                inputs=[],
                outputs=[chat_selector, chatbot]
            )

            # Delete chat button (along with confirmation dialog)
            del_btn.click(                          # Delete button: Toggle Confirmation dialog
                lambda: gr.update(visible=True),
                inputs=[],
                outputs=[del_btn_dialog]
            )
            del_btn_confirm.click(                  # Confirm delete: Do it and hide dialog
                fn=self.delete_chat,
                inputs=[],
                outputs=[chat_selector, chatbot]
            ).then(
                lambda: gr.update(visible=False),
                inputs=[],
                outputs=[del_btn_dialog]
            )                                       # Cancel delete: Hide dialog
            del_btn_cancle.click(
                lambda: gr.update(visible=False),
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
            chatbot.retry(
                fn=self.retry,                      # Retry handler
                inputs=[],
                outputs=[chatbot, user_input]
            ).then(
                fn=self.update_chat_selector,       # Then update chat title if needed
                inputs=[],
                outputs=[chat_selector]
            )

            # User input: Submit new message
            user_input.submit(
                fn=self.new_message,                # New message handler
                inputs=[user_input],
                outputs=[chatbot, user_input]
            ).then(
                fn=self.update_chat_selector,       # Then update chat title if needed
                inputs=[],
                outputs=[chat_selector]
            )
            
            # User input: Stop
            user_input.stop(
                fn=self.new_message,                # Stop streaming (run new_message again while self.is_streaming=True)
                inputs=[user_input],
                outputs=[chatbot, user_input]
            ).then(
                fn=self.update_chat_selector,       # Then update chat title if needed
                inputs=[],
                outputs=[chat_selector]
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
    