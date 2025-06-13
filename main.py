# =============================
# Ollama OnDemand
# Author: Dr. Jason Li (jasonli3@lsu.edu)
# =============================

import os
import gradio as gr
import requests
import json
import subprocess
import time
import ollama
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
        self.chat_titles = cs.get_chat_titles()     # List of chat titles
        self.update_current_chat(0)                 # Load chat at 0 index. Also initialize:
                                                    #   self.chat_index     - Current chat index
                                                    #   self.chat_history   - List of chat (Gradio chatbot compatible)
                                                    #   self.messages       - List of chat (Ollama compatible)
        
        # Start Ollama server and save client(s)
        self.start_server()
        self.client = self.get_client()
        
        # Get model(s)
        self.models = self.get_model_list()
        self.model_selected = self.models[0]
        
        # Read css file
        with open(os.path.dirname(os.path.abspath(__file__))+'/grblocks.css') as f:
            self.css = f.read()

    
    #------------------------------------------------------------------
    # Server connection
    #------------------------------------------------------------------
        
    def start_server(self):
        """Start Ollama Server"""
        
        # Define environment variables
        env = os.environ.copy()
        env["OLLAMA_HOST"] = self.args.ollama_host
        env["OLLAMA_MODELS"] = self.args.ollama_models
        env["OLLAMA_SCHED_SPREAD"] = self.args.ollama_ngpus

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
        Update current chat index, history (Gradio), and messages (Ollama) to given index.
        
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
            
        else:
        
            # Update chat index
            self.chat_index = chat_index
            
            # Update chat history
            self.chat_history = cs.load_chat(chat_index)
            
        # Update messages
        self.messages = []
        for user, bot in self.chat_history:
            self.messages.append({"role": "user",      "content": user})
            self.messages.append({"role": "assistant", "content": bot})

        
    #------------------------------------------------------------------
    # Event handler
    #------------------------------------------------------------------
    
    def stream_chat(self):
        """
        Stream chat.
        
        Input:
            None
        Output: 
            stream_chat_gr: Gradio function that yields/streams [chatbot, user_input, submit_button_face]
        """
        
        def stream_chat_gr(user_message):

            # Continue only if it is streaming (not interrupted)
            if self.is_streaming:
                
                # Append user message to chat history and messages
                self.chat_history.append((user_message, ""))
                self.messages.append({"role": "user", "content": user_message})

                # Generate next chat results
                response = self.client.chat(
                    model=self.model_selected,
                    messages=self.messages,
                    stream=True
                )

                # Stream results in chunks while not interrupted
                for chunk in response:
                    if not self.is_streaming:
                        break
                    delta = chunk.get("message", {}).get("content", "")
                    delta = delta.replace("<think>", "(Thinking...)").replace("</think>", "(/Thinking...)")
                    self.chat_history[-1] = (user_message, self.chat_history[-1][1] + delta)
                    #cs.chats[self.chat_index] = self.chat_history
                    yield self.chat_history, "", gr.update(value="⏹")
                
                # Add complete AI response to self.messages
                self.messages.append({"role": "assistant", "content": self.chat_history[-1][1]})
            
            self.is_streaming = False
            yield self.chat_history, "", gr.update(value="➤")
        
        return stream_chat_gr
    
    def submit_or_interrupt_event(self):
        """
        Handles the button face of submit / interrupt button.
        
        Input:
            None
        Output: 
            submit_button_face: Gradio update method to update button face ("value" property)
        """
        
        if self.is_streaming:
            self.is_streaming = False
            return gr.update(value="➤")
        else:
            self.is_streaming = True
            return gr.update(value="⏹")
    
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
            chat_history:   List of chat (Gradio chatbot compatible)
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
            chat_history:   List of chat (Gradio chatbot compatible)
        """
        
        # Update current chat
        self.update_current_chat(-1)
        
        # Update chat titles
        self.chat_titles = cs.get_chat_titles()
        
        # Return updated chat selector and current chat
        return gr.update(choices=self.chat_titles, value=self.chat_titles[0]), self.chat_history
    
    
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

        with gr.Blocks(css=self.css) as self.demo:
            
            #----------------------------------------------------------
            # Create UI
            #----------------------------------------------------------

            gr.Markdown("# Ollama OnDemand")
            
            with gr.Row():
                
                # Left column: Chat Selection
                with gr.Column(scale=1, min_width=220):

                    # New chat and delete chat
                    with gr.Row():
                        
                        # New Chat button
                        new_btn = gr.Button("New Chat")
                        
                        # Delete Chat button
                        del_btn = gr.Button("Delete Chat")
                    
                    # Chat buttons
                    chat_selector = gr.Radio(
                        choices=self.chat_titles,
                        show_label=False,
                        type="index",
                        value=self.chat_titles[0], 
                        interactive=True,
                        elem_id="chat-selector"
                    )
                    
                # Right column: Chat UI
                with gr.Column(scale=3, min_width=400):
                    
                    # Model dropdown
                    model_dropdown = gr.Dropdown(
                        choices=self.models,
                        value=self.model_selected,
                        label="Select Model",
                        interactive=True
                    )
                    model_dropdown.select(
                        fn=self.select_model,
                        inputs=[],
                        outputs=[],
                    )
                    
                    # Main chatbot
                    chatbot = gr.Chatbot()
                    
                    # User input textfield and buttons
                    with gr.Row():
                        
                        user_input = gr.Textbox(placeholder="Type your message here…", show_label=False)
                        submit_btn = gr.Button(value="➤", elem_id="icon-button", interactive=True)
                        
                        user_input.submit(
                            fn=self.submit_or_interrupt_event,
                            inputs=[],
                            outputs=[submit_btn]
                        ).then(
                            fn=self.stream_chat(),
                            inputs=[user_input],
                            outputs=[chatbot, user_input, submit_btn]
                        )
                        submit_btn.click(
                            fn=self.submit_or_interrupt_event,
                            inputs=[],
                            outputs=[submit_btn]
                        ).then(
                            fn=self.stream_chat(),
                            inputs=[user_input],
                            outputs=[chatbot, user_input, submit_btn]
                        )
            
            #----------------------------------------------------------
            # Update UI (for some widgets created in sequence)
            #----------------------------------------------------------
            
            # New chat button
            new_btn.click(
                fn=self.new_chat,
                inputs=[],
                outputs=[chat_selector, chatbot]
            )
            
            # Chat selector
            chat_selector.select(
                fn=self.select_chat,
                inputs=[],
                outputs=[chatbot]
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
    