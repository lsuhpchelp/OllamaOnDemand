# Process multimodal attachments for chat messages

import os
import pathlib
import gradio as gr
import pymupdf
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
    
    # Create a temporary chat message for return
    chat_tmp = chat.copy()
    
    # Proceed if "files" key exists
    if (chat_tmp.get("files")):
        
        # Loop over all uploaded files
        for file in chat_tmp["files"]:
            
            # Get extension
            ext = os.path.splitext(file)[1].lower()
            
            # If extension is listed below, process accordingly
            if ext in filetypes.keys():
                
                filetypes[ext](chat_tmp, file, is_streaming)
            
            # If not listed
            else:
                
                # If the file is not binary (a text), process as text file
                if (not is_binary(file)):
                    
                    mm_text(chat_tmp, file, is_streaming)
                
                # Otherwise, it is an image, and just copy to "image" list
                else:
                
                    mm_image(chat_tmp, file, is_streaming)
        
        # If "images" is the same as "files" (all attachments are images):
        #   - Delete "files" (store as pure images)
        # If not:
        #   - Delete "images" if only when uploading (not streaming)
        if (chat_tmp.get("images")):
            if (chat_tmp["images"] == chat_tmp["files"]):
                del chat_tmp["files"]
            else:
                if (not is_streaming):
                    del chat_tmp["images"]
            
    # Return result as a list
    return([chat_tmp])
    
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
    
def mm_image(chat, path, is_streaming=True):
    """
    Process an image file.
    
    Input:
        chat:           An OpenAI style chat message dictionary (also serve as output)
        path:           File path
        is_streaming:   True (formatting chat message for streaming) or False (formatting chat message for uploading)
    Output:
            None
    """
    
    # Append file path to chat["images"]
    if (chat.get("images")):
        
        chat["images"].append(file)
    
    else:
    
        chat["images"] = [file]
    
def mm_pdf(chat, path, is_streaming=True):
    """
    Process a pdf file.
    
    Input:
        chat:           An OpenAI style chat message dictionary (also serve as output)
        path:           File path
        is_streaming:   True (formatting chat message for streaming) or False (formatting chat message for uploading)
    Output:
            None
    """
    
    # Convert .pdf to what image format
    ext = ".png"
    
    # If formatting for streaming, add the converted images to "images" list
    if (is_streaming):
        
        directory = pathlib.Path(os.path.split(path)[0])
        images = directory.glob(f"*{ext}")
        
        if (chat.get("images")):
            chat["images"] += sorted([str(file.resolve()) for file in images])
        else:
            chat["images"] = sorted([str(file.resolve()) for file in images])
        
    # if not streaming (uploading), convert the .pdf file to images and store in the same directory
    else:
        
        try:
            
            pdf = pymupdf.open(path)
            
            i = 0
            for page in pdf:
                image_path = path + f".{i:04d}{ext}"
                image = page.get_pixmap(dpi=300)
                image.save(image_path)
                i += 1
            
        except:
            
            gr.Warning("Fail to process PDF file! Please try again later!", title="Error")


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
    ".pdf":     mm_pdf
}