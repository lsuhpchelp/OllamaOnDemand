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
        
        # Gradio components deposit
        self.gr_main = GradioComponents()           # Main view
        self.gr_leftbar = GradioComponents()        # Left sidebar
        self.gr_rightbar = GradioComponents()       # Right sidebar
        
        # Setup Gradio temp files directory
        os.environ["GRADIO_TEMP_DIR"] = self.args.workdir + "/cache"

    
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
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
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
        
        models = sorted([model.model for model in self.client.list().models])
        return models if models else ["(No model is found. Pull a model to continue...)"]
                    
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
                self.chat_history[-1]["content"] += chunk.message.content
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
                model = self.model_selected,
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
        return self.chat_history
        
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
            return gr.update(value=self.generate_chat_selector()), self.chat_history
            
        # Otherwise, keep current chat index and reload
        else:
        
            self.update_current_chat(self.chat_index)
            return gr.update(value=self.generate_chat_selector()), self.chat_history
    
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
        
    
    #------------------------------------------------------------------
    # Build UI
    #------------------------------------------------------------------
    
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
            gr.Markdown("# Ollama OnDemand")
            
            # Model selector
            self.gr_main.model_dropdown = gr.Dropdown(
                choices=self.models,
                value=self.model_selected,
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
                allow_tags=True,
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
                file_count="multiple"
            )
            
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
            self.gr_leftbar.new_btn = gr.Button("New Chat", icon=os.path.dirname(os.path.abspath(__file__))+"/images/new_chat.png")
            
            # Chat selector
            self.gr_leftbar.chat_selector = gr.HTML(
                value=self.generate_chat_selector(),
                elem_id="chat-list-container"
            )
            
            # Hidden elements
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
            pass
    
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
            title="Ollama OnDemand",
            head_paths=os.path.dirname(os.path.abspath(__file__))+'/head.html'
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
            root_path=self.args.root_path
        )
    
    
    #------------------------------------------------------------------
    # Register UI
    #------------------------------------------------------------------
    
    # Workflows
    
    def enable_components(self, interactive=True):
        """
        Enable or disable components.
        
        Input:
            interactive:    Whether components are interactive
        Output: 
            chat_selector:
            new_btn:
            del_btn:
        """
        
        return gr.update(value=self.generate_chat_selector(interactive)), \
               gr.update(interactive=interactive)
    
    def after_streaming_workflow(self, event_handler):
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
                                                    # Disable certain components
                inputs=[],
                outputs=[self.gr_leftbar.chat_selector, \
                         self.gr_leftbar.new_btn]
            ).then(
                fn=self.save_chat_history,          # Save chat history
                inputs=[],
                outputs=[]
            )
        )
    
    def basic_streaming_workflow(self, event_handler):
        """
        Basic streaming workflow
        
        Input:
            event_handler:  Event handlers (excluding before and after)
        Output: 
            None
        """
        return (
            self.after_streaming_workflow(
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
    
    def register_main(self):
        """
        Register event handlers in main view
        
        Input:
            None
        Output: 
            None
        """
            
        #----------------------------------------------------------
        # Event handlers
        #----------------------------------------------------------
            
        # Model selector
        self.gr_main.model_dropdown.select(
            fn=self.select_model,
            inputs=[],
            outputs=[],
        )
        
        # Chatbot: Retry
        self.basic_streaming_workflow(
            self.gr_main.chatbot.retry(
                fn=self.retry,
                inputs=[],
                outputs=[self.gr_main.chatbot, self.gr_main.user_input]
            )
        )
        
        # Chatbot: Edit
        self.basic_streaming_workflow(
            self.gr_main.chatbot.edit(
                fn=self.edit,
                inputs=[],
                outputs=[self.gr_main.chatbot, self.gr_main.user_input]
            )
        )

        # User input: Submit new message
        self.basic_streaming_workflow(
            self.gr_main.user_input.submit(
                fn=self.new_message,
                inputs=[self.gr_main.user_input],
                outputs=[self.gr_main.chatbot, self.gr_main.user_input]
            )
        )
        
        # User input: Stop
        self.after_streaming_workflow( 
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


def main():
    
    app = OllamaOnDemandUI(get_args())
    app.build_ui()
    app.launch()

if __name__ == "__main__":
    main()
    