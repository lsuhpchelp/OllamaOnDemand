# Process multimodal attachments for chat messages

import os
import gradio as gr
from binaryornot.check import is_binary

#======================================================================
#                            Functions 
#======================================================================

def format_chat(chat, is_streaming=True):
    """
    Process multimodal attachment for a single chat message.
    
    Input:
        chat:           An OpenAI style chat message dictionary (also serve as output)
        is_streaming:   True (formatting chat message for streaming) or False (formatting chat message for uploading)
    Output: 
        None
    """
        
    # Create "image" list
    chat["images"] = []
        
    # Loop over all uploaded files
    for file in chat["files"]:
        
        # Get extension
        ext = os.path.splitext(file)[1]
        
        # If extension is listed below, process accordingly
        if ext in filetypes.keys():
            
            filetypes[ext](chat, file, is_streaming)
        
        # If not listed
        else:
            
            # If the file is not binary (a text), process as text file
            if (not is_binary(file)):
                
                mm_text(chat, file, is_streaming)
            
            # Otherwise, it is an image, and just copy to "image" list
            else:
            
                chat["images"].append(file)
            
        
    # Delete "image" key if it is empty after processing (e.g., only ".txt" files are found)
    if (not chat["images"]):
        
        del chat["images"]
        
    # Delete "files" key if "files" is the same as "images" (i.e., all attachments are images)
    elif (chat["images"] == chat["files"]):
        
        del chat["files"]
    
def mm_text(chat, path, is_streaming=True):
    """
    Process a text file.
    
    Input:
        chat:           An OpenAI style chat message dictionary (also serve as output)
        path:           File path
        is_streaming:   True (formatting chat message for streaming) or False (formatting chat message for uploading)
    Output:
            None
    """
    
    # If formatting for streaming, attach the file to the end of user message
    if (is_streaming):
        
        try:
        
            # Get file name
            name = os.path.split(path)[1]
            
            # Get content
            with open(path, "r") as f:
                content = f.read()
            
            # Attach to the end of user message
            chat["content"] += f"""
            
---

File name: [{name}]

Content:

{content}

            """
            
        except:
            
            gr.Warning("Opening file failed! Please try again!", title="Error")


#======================================================================
#                       List of file types 
#======================================================================

# A dictionary of supported file types other than images
#   Keys: A string of file extension name
#   Vals: A function reference defining how to format chat message for each file type, which has:
#       Input:
#           chat:           An OpenAI style chat message dictionary (also serve as output)
#           path:           File path
#           is_streaming:   True (formatting chat message for streaming) or False (formatting chat message for uploading)
filetypes = {

}