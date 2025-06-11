# Chat history management

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

# Load chat
def load_chat(index):
    return chats[index], index
    
# New chat
def new_chat():
    chats.insert(0, [])
    return chats[0], 0
