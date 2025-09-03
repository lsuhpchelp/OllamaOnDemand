# Command-line arguments

import argparse
import getpass
import os

__version__ = "1.0.0"

def get_args():
    
    parser = argparse.ArgumentParser(
        description="Ollama OnDemand launcher", 
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )

    #------------------------------------------------------------------
    # Group 0: Default options
    #------------------------------------------------------------------
    
    parser.add_argument(
        "--debug", action="store_true",
        help="Enable debug mode."
    )

    parser.add_argument(
        "--version", "-v",
        help="Show Ollama OnDemand's version number.",
        action="version",
        version=f"Ollama OnDemand {__version__}"
    )

    #------------------------------------------------------------------
    # Group 1: Ollama Ondemand web service
    #------------------------------------------------------------------
    group_server = parser.add_argument_group( 
            "Ollama OnDemand server settings", 
            "Settings related to Ollama OnDemand app web server."
        )

    # Define your command-line options here
    group_server.add_argument(
        "--host", type=str, default="0.0.0.0",
        help="Host for Ollama OnDemand web service."
    )
    
    group_server.add_argument(
        "--port", type=int, default=7860,
        help="Port for Ollama OnDemand web service."
    )
    
    group_server.add_argument(
        "--root-path", type=str, default="",
        help="Root path for web interface."
    )
    
    group_server.add_argument(
        "--workdir", "-w", type=str, default="/home/"+getpass.getuser()+"/.ollama/ollamaondemand",
        help="Ollama Ondemand work directory for data storage."
    )

    #------------------------------------------------------------------
    # Group 2: Ollama server settings
    #------------------------------------------------------------------
    group_ollama = parser.add_argument_group( 
            "Ollama server settings", 
            "Settings related to Ollama server running as backend."
        )
    
    group_ollama.add_argument(
        "--ollama-host", type=str, default="127.0.0.1:11434",
        help="Ollama server address."
    )
    
    group_ollama.add_argument(
        "--ollama-models", type=str, default="/home/"+getpass.getuser()+"/.ollama/models",
        help="Path to Ollama models."
    )

    return parser.parse_args()

