# Process multimodal attachments for chat messages

import os
import pathlib
import gradio as gr
import pymupdf
from binaryornot.check import is_binary

DEFAULT_CONVERT_IMAGE_FORMAT = ".png"

#======================================================================
#                            Call Functions 
#======================================================================

def format_chat_stream(chat):
    """
    Process multimodal attachment for a single chat message. For streaming with Ollama server.
    
    Input:
        chat:           An OpenAI style chat message dictionary
    Output: 
        [chat,...]:     A list of chat messages (possibly more than one, as pure text will be submitted as separated messages)
    """
    
    # Create a temporary chat message for return
    chat_tmp = chat.copy()
    
    # Proceed only if "files" key exists
    if (chat_tmp.get("files")):
        
        # Loop over all uploaded files
        for file in chat_tmp["files"]:
            
            # Get extension
            ext = os.path.splitext(file)[1].lower()
            
            # If extension is explicitly listed, process with indicated handler
            if (ext in filetypes.keys()):
                
                # Only process when handler exists
                if (filetypes[ext].get("stream")):
                
                    filetypes[ext]["stream"](chat_tmp, file)
            
            # If not listed
            else:
                
                # If the file is not binary (a text), process as text file
                if (not is_binary(file)):
                    
                    mm_text_stream(chat_tmp, file)
                
                # Otherwise, it is an image, process as an image
                else:
                
                    mm_image(chat_tmp, file)
    
    # Prepare return values
    res = [chat_tmp]
    
    # Expand content["txt"] if exists
    if (chat_tmp.get("txt")):
        
        for txt_msg in chat_tmp["txt"]:
            
            res.append({
                "role":     "user", 
                "content":  txt_msg
            })
            
    # Return result as a list
    return(res)

def format_chat_upload(chat):
    """
    Process multimodal attachment for a single chat message. For upload.
    
    Input:
        chat:           An OpenAI style chat message dictionary
    Output: 
        chat:           An OpenAI style chat message dictionary (formatted for upload)
    """
    
    # Create a temporary chat message for return
    chat_tmp = chat.copy()
    
    # Proceed only if "files" key exists
    if (chat_tmp.get("files")):
        
        # Loop over all uploaded files
        for file in chat_tmp["files"]:
            
            # Get extension
            ext = os.path.splitext(file)[1].lower()
            
            # If extension is explicitly listed, process with indicated handler
            if (ext in filetypes.keys()):
                
                # Only process when handler exists
                if (filetypes[ext].get("upload")):
                
                    filetypes[ext]["upload"](chat_tmp, file)
            
            # If not listed
            else:
                
                # If the file is binary (an image), process as an image
                if (is_binary(file)):
                
                    mm_image(chat_tmp, file)
        
        # "images" and "files", only keep one
        # Delete "files" if it is the same as "images" (only image files are uploaded); otherwise, delete "images"
        if (chat_tmp.get("images")):
            if (chat_tmp["images"] == chat_tmp["files"]):
                del chat_tmp["files"]
            else:
                del chat_tmp["images"]
            
    # Return result as a list
    return(chat_tmp)


#======================================================================
#                            File Handlers
#======================================================================
    
def mm_text_stream(chat, path):
    """
    Process a text file. For streaming with Ollama server.
    
    Input:
        chat:           An OpenAI style chat message dictionary (also serve as output)
        path:           File path
    Output:
        None
    """
    
    try:
    
        # Get file name
        name = os.path.split(path)[1]
        
        # Get content
        with open(path, "r") as f:
            content = f.read()
            
        # Create message
        txt_msg = f"""
File name: [{name}]

Content:

{content}

        """
        
        # Append message to content["txt"] list (create this list if it does not exist)
        # This list will be processed in the end to create separated user messages.
        if (chat.get("txt")):
            
            chat["txt"].append(txt_msg)
            
        else:
            
            chat["txt"] = [txt_msg]
        
    except:
        
        gr.Warning("Opening file failed! Please try again!", title="Error")
    
def mm_image(chat, path):
    """
    Process an image file. For both streaming and upload.
    
    Input:
        chat:           An OpenAI style chat message dictionary (also serve as output)
        path:           File path
    Output:
        None
    """
    
    # Append file path to chat["images"]
    if (chat.get("images")):
        
        chat["images"].append(path)
    
    else:
    
        chat["images"] = [path]
    
def mm_pdf_stream(chat, path):
    """
    Process a pdf file. For streaming with Ollama server.
    
    Input:
        chat:           An OpenAI style chat message dictionary (also serve as output)
        path:           File path
    Output:
        None
    """
    
    # Obtain all converted images during upload stage
    directory = pathlib.Path(os.path.split(path)[0])
    images = directory.glob(f"*{DEFAULT_CONVERT_IMAGE_FORMAT}")
    
    # Attach images to chat["images"] (Create if it does not exist)
    if (chat.get("images")):
        chat["images"] += sorted([str(file.resolve()) for file in images])
    else:
        chat["images"] = sorted([str(file.resolve()) for file in images])
    
def mm_pdf_upload(chat, path):
    """
    Process a pdf file. For upload.
    
    Input:
        chat:           An OpenAI style chat message dictionary (also serve as output)
        path:           File path
    Output:
        None
    """
        
    # Convert the .pdf file to images and store in the same directory
    try:
        
        pdf = pymupdf.open(path)
        
        i = 0
        for page in pdf:
            image_path = path + f".{i:04d}{DEFAULT_CONVERT_IMAGE_FORMAT}"
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
#   Vals: A dictionary of function reference defining how to format chat message for each file type, which has:
#       Input:
#           chat:           An OpenAI style chat message dictionary (also serve as output)
#           path:           File path
#           is_streaming:   True (formatting chat message for streaming) or False (formatting chat message for uploading)
filetypes = {
    ".pdf":     {
        "stream":   mm_pdf_stream,
        "upload":   mm_pdf_upload
    }
}