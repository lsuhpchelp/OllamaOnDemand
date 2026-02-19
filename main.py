# =============================
# Ollama OnDemand
# Author: Dr. Jason Li (jasonli3@lsu.edu)
# =============================

import os
import requests
import subprocess
import time
import ollama
        
# Set Gradio temp files directory before loading Gradio
# (Fix an issue Gradio will create temp folders upon loading)
from arg import get_args
args = get_args()
os.environ["GRADIO_TEMP_DIR"] = args.workdir + "/cache"
import gradio as gr

from utils import UtilsMixin
from ui_builders import UIBuilderMixin
from listeners import ListenerMixin

#======================================================================
#                           Main UI class
#======================================================================

class GradioComponents:
    """An empty class used to deposit Gradio components."""
    pass

class OllamaOnDemandUI(UtilsMixin, UIBuilderMixin, ListenerMixin):
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
        
        # Current path
        self.current_path = os.path.dirname(os.path.abspath(__file__))
        
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
        
        # Clean up orphaned cached files
        self.cleanup_cache()
        
        # User settings
        self.settings = self.load_settings()
        
        # Use default model path if:
        #   1) User did not customize model path, or
        #   2) Model path not writable and not a legal model path
        if (not self.settings.get("ollama_models") or \
            not os.access(self.settings.get("ollama_models"), os.W_OK) and \
            not self.is_model_path(self.settings.get("ollama_models"))):
            self.settings["ollama_models"] = self.args.ollama_models
            self.save_settings()
        
        # Start Ollama server and save client(s)
        self.start_server()
        self.client = self.get_client()
        
        # Get models
        self.models = self.list_installed_models()          # Installed models (List)
        self.remote_models = self.dict_remote_models()      # Remote models (Dict)
        if (not self.settings.get("model_selected") in self.models):
            self.settings["model_selected"] = self.models[0]
        
        # Gradio components deposit
        self.gr_main = GradioComponents()           # Main view
        self.gr_leftbar = GradioComponents()        # Left sidebar
        self.gr_rightbar = GradioComponents()       # Right sidebar
        self.gr_rightbar.settings_components = {}   # User settings: Setting components
        self.gr_rightbar.settings_defaults = {}     # User settings: Default checkbox
        
        # Compile regular expression for think tag replacement for display
        self.think_tags = {
            "head":    "<div class='thinking-block'><details open class='thinking'><summary><i><b>(Thinking...)</b></summary>\n\n<br>",
            "tail":    "</i></details></div><br>\n\n"
        }

    
    #------------------------------------------------------------------
    # Server connection
    #------------------------------------------------------------------
        
    def start_server(self, raise_error=True):
        """
        Start Ollama Server
        
        Input:
            None
        Output:
            None (raise error) or error message (return for future use)
        """
        
        # Define environment variables
        env = os.environ.copy()
        env["OLLAMA_HOST"] = self.args.ollama_host
        env["OLLAMA_MODELS"] = self.settings["ollama_models"]
        env["OLLAMA_SCHED_SPREAD"] = "1"

        # Start the Ollama server
        print("Starting Ollama server on " + self.args.ollama_host)
        self.server_process = subprocess.Popen(
            ["ollama", "serve"],
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        
        # Wait until the server starts
        url = "http://" + self.args.ollama_host if not self.args.ollama_host.startswith(("http://", "https://")) else self.args.ollama_host
        for _ in range(60): 
            
            try:
                if requests.get(url).ok:
                    print("Ollama server is running")
                    return ""
            except:
                pass
            print("Waiting for Ollama server to start...")
            time.sleep(1)
            
        else:
            
            if (raise_error):
                raise RuntimeError("Ollama server failed to start in 1 min. Something is wrong.")
            else:
                return("Ollama server failed to start in 1 min. Something is wrong.")
            
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


def main():
    
    app = OllamaOnDemandUI(args)
    app.build_ui()
    app.launch()

if __name__ == "__main__":
    main()
    