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
import chathistory as ch
import threading

# Stop event
stop_event = threading.Event()

# Read command line options (Global)
args = get_args()
if args.debug:
    print(f"Launching with args: {args}")


#==============================================================
#                        Functions
#==============================================================

def start_server():
    """Start Ollama Server"""
    
    # Define environment variables
    env = os.environ.copy()
    env["OLLAMA_HOST"] = args.ollama_host
    env["OLLAMA_MODELS"] = args.ollama_models

    # Start the Ollama server
    print("Starting Ollama server on " + args.ollama_host)
    process = subprocess.Popen(
        ["ollama", "serve"],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    
    # Wait until the server starts
    for _ in range(60): 
        try:
            if requests.get(args.ollama_host).ok:
                print("Ollama server is running")
                break
        except:
            pass
        print("Waiting for Ollama server to start...")
        time.sleep(1)
    else:
        raise RuntimeError("Ollama server failed to start in 1 min. Something is wrong.")
        
    # Return Ollama client
    return ollama.Client(host=args.ollama_host)

def list_models(client):
    """
    Get list of models.
    
    Input:  client - Client object
    Output: models - List of all model names
    """
    
    models = client.list().models
    return [model.model for model in models]


def stream_chat(client):
    """
    Stream chat.
    
    Input:  client          - Client object
    Output: stream_chat_gr  - Gradio function that yields/streams [chatbot, user_input]
    """
    
    def stream_chat_gr(user_message, chat_history, selected_model, idx, is_streaming):

        # Continue only if it is streaming
        if is_streaming:
            
            # Convert Gradio chat history format to Ollama
            chat_history = chat_history or []
            messages = []
            for user, bot in chat_history:
                messages.append({"role": "user",      "content": user})
                messages.append({"role": "assistant", "content": bot})
            messages.append({"role": "user", "content": user_message})
            chat_history.append((user_message, ""))

            # Generate next chat results
            response = client.chat(
                model=selected_model,
                messages=messages,
                stream=True
            )

            # Stream results in chunks
            for chunk in response:
                if stop_event.is_set():
                    break
                delta = chunk.get("message", {}).get("content", "")
                delta = delta.replace("<think>", "(Thinking...)").replace("</think>", "(/Thinking...)")
                chat_history[-1] = (user_message, chat_history[-1][1] + delta)
                ch.chats[idx] = chat_history
                yield chat_history, "", gr.update(value="⏹"), True
    
        yield chat_history, "", gr.update(value="➤"), False
    
    return stream_chat_gr

#==============================================================
#                        Create UI
#==============================================================
    
def createUI(client):
    """
    Create UI.
    
    Input:  client - Client object
    Output: UI demo
    """
    
    # Fetch models at startup
    available_models = list_models(client)
    available_models = available_models if available_models else ["(No model is found. Create a model to continue...)"]
    selected_model = available_models[0]


    with gr.Blocks(css="""

        /* Fix icon button size */
        #icon-button {
            width: 60px;
            min-width: 60px;
            max-width: 60px;
            height: 100%;
        }
        
        /* Chat selector label 100% wide */
        #chat-selector label {
            display: block;
            width: 100%;
            margin-bottom: 4px;
        }
        
    """) as demo:
        
        # States
        idx_state = gr.State(0)             # Selected chat session
        is_streaming = gr.State(False)      # Is streaming (for submit/interrupt button)
        
        #--------------------------------------------------------------
        # Create UI
        #--------------------------------------------------------------

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
                def get_chat_titles():
                    return [ chat[0][0][:30]+"..." if chat else f"Chat {i+1}" for i, chat in enumerate(ch.chats) ]
                chat_titles = get_chat_titles()
                chat_selector = gr.Radio(
                    choices=chat_titles,
                    show_label=False,
                    type="index",
                    value=chat_titles[0], 
                    interactive=True,
                    elem_id="chat-selector"
                )
                
            # Right column: Chat UI
            with gr.Column(scale=3, min_width=400):
                
                # Model dropdown
                model_dropdown = gr.Dropdown(
                    choices=available_models,
                    value=selected_model,
                    label="Select Model",
                    interactive=True
                )
                
                # Main chatbox
                chatbot = gr.Chatbot()
                
                # User input textfield and buttons
                with gr.Row():
                    user_input = gr.Textbox(placeholder="Type your message here…", show_label=False)
                    submit_btn = gr.Button(value="➤", elem_id="icon-button", interactive=True)
                
                def submit_or_interrupt_event(is_streaming_val):
                    if is_streaming_val:
                        stop_event.set()
                        return gr.update(value="➤"), False
                    else:
                        stop_event.clear()
                        return gr.update(value="⏹"), True
                    
                user_input.submit(
                    fn=submit_or_interrupt_event,
                    inputs=[is_streaming],
                    outputs=[submit_btn, is_streaming]
                ).then(
                    fn=stream_chat(client),
                    inputs=[user_input, chatbot, model_dropdown, idx_state, is_streaming],
                    outputs=[chatbot, user_input, submit_btn, is_streaming]
                )
                        
                submit_btn.click(
                    fn=submit_or_interrupt_event,
                    inputs=[is_streaming],
                    outputs=[submit_btn, is_streaming]
                ).then(
                    fn=stream_chat(client),
                    inputs=[user_input, chatbot, model_dropdown, idx_state, is_streaming],
                    outputs=[chatbot, user_input, submit_btn, is_streaming]
                )

        
        #--------------------------------------------------------------
        # Update UI
        #--------------------------------------------------------------
        
        # Register Chat Selector behavior
        def select_chat(evt: gr.SelectData):
            return ch.load_chat(evt.index)
        chat_selector.select(
            fn=select_chat,
            inputs=[],
            outputs=[chatbot, idx_state]
        )
        
        # Register New Chat button
        def new_chat():
            ch.new_chat()
            chat_titles = get_chat_titles()
            return gr.update(choices=chat_titles, value=chat_titles[0]), *ch.load_chat(0)
        new_btn.click(
            fn=new_chat,
            inputs=[],
            outputs=[chat_selector, chatbot, idx_state]
        )

               
        # Load first chat session
        demo.load(
            fn=ch.load_chat,
            inputs=[idx_state],
            outputs=[chatbot, idx_state]
        )
            
    return demo
    
    
def main():
    
    # Start Ollama server
    client = start_server()
    
    # Create UI
    demo = createUI(client)
    
    # Launch
    demo.launch(
        server_name=args.host,
        server_port=args.port,
        root_path=args.root_path
    )

if __name__ == "__main__":
    
    main()
    