# Command-line arguments

import argparse

__version__ = "0.1.0"

def get_args():
    
    parser = argparse.ArgumentParser(
        description="Ollama OnDemand launcher", 
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )

    # Define your command-line options here
    parser.add_argument(
        "--host", type=str, default="0.0.0.0",
        help="Host for the Gradio app."
    )
    
    parser.add_argument(
        "--port", type=int, default=7860,
        help="Port for the Gradio app."
    )
    
    parser.add_argument(
        "--root-path", type=str, default="/",
        help="Root path for web interface."
    )
    
    parser.add_argument(
        "--ollama-host", type=str, default="127.0.0.1:11434",
        help="Ollama server address."
    )
    
    parser.add_argument(
        "--model", type=str, default="llama3.2",
        help="Model to load with Ollama."
    )
    
    parser.add_argument(
        "--debug", action="store_true",
        help="Enable debug mode"
    )

    parser.add_argument(
        "--version", "-v",
        action="version",
        version=f"Ollama OnDemand {__version__}"
    )

    return parser.parse_args()

