# Chat sessions management

import os
import json

chats = [
    {
        "title": "New Chat",
        "history": []
    }
]

def load_chat(index):
    """
    Load chat at given index.
    
    Input:
        index:          Chat index
    Output: 
        chat_history:   List of chat (Gradio chatbox compatible)
    """
    return chats[index]["history"]
    
def new_chat():
    """
    New chat.
    
    Input:
        None
    Output: 
        chat_history:   List of chat (Gradio chatbox compatible)
    """
    chats.insert(0, { "title": "New Chat", "history": [] })
    return chats[0]["history"]

def delete_chat(index):
    """
    Delete chat session at the specified index.
    
    Input:
        index: Index of chat session to delete
    Output:
        None
    """
    if 0 <= index < len(chats):
        del chats[index]

def set_chat_title(index, title):
    """
    Set chat session title at index.
    
    Input:
        index:  Index of chat session
        title:  New title
    Output: 
        None
    """
    chats[index]["title"] = title

def get_chat_title(index):
    """
    Get chat session title at index.
    
    Input:
        index:  Index of chat session
    Output: 
        title:  Chat title
    """
    return(chats[index]["title"])

def get_chat_titles():
    """
    Get list of chat titles.
    
    Input:
        None
    Output: 
        chat_titles: List of chat titles
    """
    return [ chat["title"] if chat["title"] else f"New Chat {i+1}" for i, chat in enumerate(chats) ]

def save_chats(workdir):
    """
    Save chat history in work directory.
    
    Input:
        workdir:    Work directory
    Output: 
        None
    """

    try:
        
        # Create work directory if it does not exist
        os.makedirs(workdir, exist_ok=True)

        # Dump chats if it is accessible.
        file_path = os.path.join(workdir, "chats.json")
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(chats, f, indent=2, ensure_ascii=False)
            
    except Exception:
        pass

def load_chats(workdir):
    """
    Load chat history in work directory.
    
    Input:
        workdir:    Work directory
    Output: 
        None
    """
    global chats

    try:

        # Load chats if exists
        file_path = os.path.join(workdir, "chats.json")
        with open(file_path, "r", encoding="utf-8") as f:
            chats = json.load(f)
            
    except Exception:
        pass