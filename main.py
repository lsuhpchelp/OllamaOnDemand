# =============================
# Ollama OnDemand
# Author: Dr. Jason Li (jasonli3@lsu.edu)
# =============================

import os
import gradio as gr
import requests
import json
import subprocess
from arg import get_args
import chathistory as ch

# Read command line options (Global)
args = get_args()
if args.debug:
    print(f"Launching with args: {args}")


#==============================================================
#                        Functions
#==============================================================

def get_ollama_models():
    """Get list of local Ollama models."""
    try:
        resp = requests.get(f"{args.ollama_host}/api/tags")
        resp.raise_for_status()
        data = resp.json()
        # tags is a list of {"name": ...}, e.g., "llama3:latest"
        return [m["name"] for m in data.get("models", [])]
    except Exception as e:
        # Fallback to a default if API fails
        return ["llama3.2"]


def stream_chat_with_ollama(user_message, chat_history, selected_model, idx):
    chat_history = chat_history or []
    messages = []
    
    for user, bot in chat_history:
        messages.append({"role": "user",      "content": user})
        messages.append({"role": "assistant", "content": bot})
    messages.append({"role": "user", "content": user_message})
    chat_history.append((user_message, ""))

    response = requests.post(
        f"{args.ollama_host}/v1/chat/completions",
        json={
            "model": selected_model,
            "messages": messages,
            "stream": True
        },
        stream=True
    )
    response.raise_for_status()

    for line in response.iter_lines():
        if not line:
            continue
        text = line.decode("utf-8")
        if text.startswith("data: "):
            text = text[len("data: "):]
        if text.strip() == "[DONE]":
            break
        chunk = json.loads(text)
        delta = chunk["choices"][0]["delta"].get("content", "")
        # Standardize think tag replacement
        delta = delta.replace("<think>", "(Thinking...)").replace("</think>", "(/Thinking...)")
        chat_history[-1] = (user_message, chat_history[-1][1] + delta)
        yield chat_history, "", selected_model  # pass selected_model back to retain state

        # ✅ Save updated history to ch.chats
        ch.chats[idx] = chat_history

#==============================================================
#                        Create UI
#==============================================================
    
def createUI():
    """
    Create UI.
    
    Input: None
    Output: UI demo
    """
    
    # Fetch models at startup
    available_models = get_ollama_models()
    default_model = available_models[0] if available_models else args.model


    with gr.Blocks() as demo:
        
        #--------------------------------------------------------------
        # Create UI
        #--------------------------------------------------------------

        gr.Markdown("# Ollama OnDemand")
        
        with gr.Row():
            
            # Sidebar (like ChatGPT)
            with gr.Column(scale=1, min_width=220):
                chats_state = gr.State([[]])
                idx_state = gr.State(0)
                chat_btns = []
                with gr.Column():
                    for i, chat in enumerate(ch.chats):
                        title = chat[0][0][:30] + "..." if chat else f"Chat {i+1}"
                        btn = gr.Button(value=title, visible=True)
                        chat_btns.append(btn)
                new_btn = gr.Button("New Chat")
                del_btn = gr.Button("Delete Chat")
                
            # Right column: Chat UI
            with gr.Column(scale=3, min_width=400):
                model_dropdown = gr.Dropdown(
                    choices=available_models,
                    value=default_model,
                    label="Select Model",
                    interactive=True
                )
                chatbot = gr.Chatbot()
                user_input = gr.Textbox(placeholder="Type your message here…", show_label=False)
                clear_btn = gr.Button("Clear")

                user_input.submit(
                    fn=stream_chat_with_ollama,
                    inputs=[user_input, chatbot, model_dropdown, idx_state],
                    outputs=[chatbot, user_input, model_dropdown]
                )
                clear_btn.click(lambda: ([], "", default_model), None, [chatbot, user_input, model_dropdown])
        
        #--------------------------------------------------------------
        # Update UI
        #--------------------------------------------------------------
            
        # function to update selected chat button
        def update_button_styles(selected_idx):
            updates = []
            for i in range(len(chat_btns)):
                style = "primary" if i == selected_idx else "secondary"
                updates.append(gr.update(variant=style))
            return updates
            
        # Update chat buttons and chat
        for i, btn in enumerate(chat_btns):
            btn.click(
                fn=lambda _, i=i: ch.load_chat(i),
                inputs=[],
                outputs=[chatbot, idx_state]
            ).then(
                fn=update_button_styles,
                inputs=[idx_state],
                outputs=chat_btns
            ).then(
                lambda: "", None, user_input
            )
            
        
                
        
    return demo


def main():
    
    # Create UI
    demo = createUI()
    
    # Launch
    demo.launch(
        server_name=args.host,
        server_port=args.port,
        root_path=args.root_path
    )

if __name__ == "__main__":
    main()
    