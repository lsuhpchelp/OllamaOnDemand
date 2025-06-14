# Chat sessions management

chats = [
    { 
        "title": "News summary",
        "history": 
            [
                ("Hi there!", "Hello! How can I help you today?"),
                ("Can you summarize the news?", "Sure! Here's a brief summary of today's top news...")
            ]
    },
    { 
        "title": "Capital of France",
        "history": 
        [
            ("What is the capital of France?", "The capital of France is Paris."),
            ("Thanks!", "You're welcome!")
        ]
    },
    { 
        "title": "Quantum entanglement",
        "history": 
        [
            ("Explain quantum entanglement", 
             "Quantum entanglement is a physical phenomenon where particles remain connected such that the state of one affects the other, no matter the distance.")
        ]
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
    chats.insert(0, { "title": "", "history": [] })
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
