# Chat sessions management

chats = [
    [
        ("Hi there!", "Hello! How can I help you today?"),
        ("Can you summarize the news?", "Sure! Here's a brief summary of today's top news...")
    ],
    [
        ("What is the capital of France?", "The capital of France is Paris."),
        ("Thanks!", "You're welcome!")
    ],
    [
        ("Explain quantum entanglement", 
         "Quantum entanglement is a physical phenomenon where particles remain connected such that the state of one affects the other, no matter the distance.")
    ]
]

def load_chat(index):
    """
    Load chat at given index.
    
    Input:
        index:          Chat index
    Output: 
        chat_history:   List of chat (Gradio chatbox compatible)
    """
    return chats[index]
    
def new_chat():
    """
    New chat.
    
    Input:
        None
    Output: 
        chat_history:   List of chat (Gradio chatbox compatible)
    """
    chats.insert(0, [])
    return chats[0]

def get_chat_titles():
    """
    Get list of chat titles.
    
    Input:
        None
    Output: 
        chat_titles: List of chat titles
    """
    return [ chat[0][0][:40]+"..." if chat else f"Chat {i+1}" for i, chat in enumerate(chats) ]
