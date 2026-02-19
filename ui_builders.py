# UI building methods

import os
import html
import json
import gradio as gr
import chatsessions as cs
import multimodal as mm


class UIBuilderMixin:
    """Mixin class for UI building methods."""
    
    #------------------------------------------------------------------
    # Build UI
    #------------------------------------------------------------------
            
    def generate_chat_selector(self, interactive=True):
        """
        Build chat selector (HTML code)
        
        Input:
            interactive:            Whether the code is responsive to events (Default: True)
        Output: 
            html_chat_selector:     Chat selector HTML code
        """
        
        titles = cs.get_chat_titles()
        html_chat_selector = ""
        
        if interactive:
        
            for i, title in enumerate(titles):
                active = "active-chat" if i == self.chat_index else ""
                title = html.escape(title)
                html_chat_selector += f"""
                <div class='chat-entry {active}' onclick="select_chat_js({i})" id='chat-entry-{i}'>
                    <span class='chat-title' id='chat-title-{i}' title='{title}'>{title}</span>
                    <input class='chat-title-input custom-hidden' id='chat-title-input-{i}' autocomplete='off'
                           onkeydown="rename_chat_confirm_js(event, {i})"
                           onblur="rename_chat_cancel_js({i})" 
                            onclick="event.stopPropagation()" />
                    <button class='menu-btn' onclick="event.stopPropagation(); open_menu({i})">⋯</button>
                    <div class='chat-menu' id='chat-menu-{i}'>
                        <button onclick="event.stopPropagation(); rename_chat_js({i})">Rename</button>
                        <button onclick="event.stopPropagation(); export_chat_js({i})">Export</button>
                        <button onclick="event.stopPropagation(); delete_chat_js({i})">Delete</button>
                    </div>
                </div>

                """
                
        else:
        
            for i, title in enumerate(titles):
                title = html.escape(title)
                html_chat_selector += f"""
                <div class='chat-entry'>
                    <span class='chat-title' title='{title}'>{title}</span>
                    <button class='menu-btn'>⋯</button>
                    <div class='chat-menu' id='chat-menu-{i}'>
                        <button>Rename</button>
                        <button>Export</button>
                        <button>Delete</button>
                    </div>
                </div>
                """
        
        return html_chat_selector
            
    def generate_settings_component(self, name, component, component_init):
        """
        Build each setting component.
        
        Input:
            name:           Name of the parameter. Must be the same as Ollama Python's parameter list
            component:      Gradio component method reference
            component_init: Gradio component method initialization arguments
        Output: 
            None
        """
        
        # Check user set it to use model default value
        if (self.settings.get("options") and name in self.settings.get("options")):
            default = False
        else:
            default = True
        
        # If component is gr.Markdown, then just build it
        if (component == gr.Markdown):
        
            # Render markdown
            component(**component_init)
        
        # Otherwise, build UI components
        else:
        
            with gr.Row(elem_classes = ["param-item"]):
                
                # Display name
                gr.Markdown("**" + name + "**")
                
                # Default checkbox
                self.gr_rightbar.settings_defaults[name] = \
                    gr.Checkbox(label="(Use default)", 
                                interactive=True, 
                                container=False, 
                                value=default,
                                min_width=0)
                    
            # Build adjusting component
            value = self.settings.get("options").get(name) if self.settings.get("options") else 0
            self.gr_rightbar.settings_components[name] = component(
                value = value,
                visible = not default, 
                interactive = True, 
                **component_init
            )
            
            # Register checkbox behavior
            self.gr_rightbar.settings_defaults[name].change(
                fn = lambda arg_value, arg_is_default: self.settings_param_default_change(name, arg_value, arg_is_default),
                inputs = [self.gr_rightbar.settings_components[name], self.gr_rightbar.settings_defaults[name]],
                outputs = [self.gr_rightbar.settings_components[name]]
            )
            
            # Register adjusting component behavior
            self.gr_rightbar.settings_components[name].change(
                fn = lambda arg_value: self.settings_param_value_change(name, arg_value),
                inputs = [self.gr_rightbar.settings_components[name]],
                outputs = []
            )
        
    def generate_settings_model_name_choices(self):
        """
        Generate dropdown choices for remote model names
        
        Input:
            None
        Output: 
            [(key, val)]:   A list of (key, value) pair, and add "✅" to keys if installed
        """
        
        # List model names (values)
        values = sorted(list(self.remote_models.keys()))
        
        # Generate dropdown choices
        res = []
        dict_installed_models = self.dict_installed_models()
        for val in values:
            if val in dict_installed_models:
                res.append((val + " ✅", val))
            else:
                res.append((val, val))
        
        # Return
        return(res)
        
    def generate_settings_model_tag_choices(self, name):
        """
        Generate dropdown choices for remote model tags
        
        Input:
            name:           Model name
        Output: 
            [(key, val)]:   A list of (key, value) pair, and add "✅" to keys if installed
        """
        
        # List model names (values)
        values = self.remote_models[name]
        
        # Generate dropdown choices
        res = []
        dict_installed_tags = self.dict_installed_models().get(name) if self.dict_installed_models().get(name) else []
        for val in values:
            if val in dict_installed_tags:
                res.append((val + " ✅", val))
            else:
                res.append((val, val))
        
        # Return
        return(res)
    
    def build_main(self):
        """
        Build main view
        
        Input:
            None
        Output: 
            None
        """
            
        # Header
        with gr.Row(
            elem_id="gr-main-header",
            elem_classes=["no-shrink", "main-max-width"]
        ):
            
            # Title
            logo = "gradio_api/file=" + self.current_path + "/images/logo.png"
            gr.Markdown(
                f"""
                <div style="display: flex; align-items: center; gap: 1px;">
                    <img src="{logo}" alt="Logo" style="height:40px; width: 40px;">
                    <h2 style="margin-top: 10px;" class="mobile-header">llama OnDemand</h2>
                </div>
                """
            )
            
            # Model selector
            self.gr_main.model_dropdown = gr.Dropdown(
                choices=self.list_installed_models(formatted=True),
                value=self.settings["model_selected"],
                interactive=True,
                show_label=False,
                container=False,
                min_width=0,
                elem_id="gr-model-selector"
            )
        
        # Body
        with gr.Column(elem_id="gr-chatbot-container"):
            
            # Main chatbot
            self.gr_main.chatbot = gr.Chatbot(
                height=None,
                show_label=False,
                type="messages",
                show_copy_button=True,
                group_consecutive_messages=False,
                editable="user",
                allow_tags=True,
                elem_id="gr-chatbot"
            )
            
        # Footer
        with gr.Column(
            elem_classes=["no-shrink", "main-max-width"]
        ):
            
            #Input field (multimodal)
            self.gr_main.user_input = gr.MultimodalTextbox(
                placeholder="Ask anything", 
                submit_btn=True,
                stop_btn=False,
                show_label=False,
                file_types=["image", "text"] + list(mm.filetypes.keys()),
                file_count="multiple",
                max_lines=10,
                max_plain_text_length=10000,
                elem_id="gr-user-input"
            )
    
    def build_left(self):
        """
        Build left sidebar
        
        Input:
            None
        Output: 
            None
        """
        
        with gr.Sidebar(width=350, position="left", open=False) as self.gr_leftbar.leftbar:

            # New Chat button
            self.gr_leftbar.new_btn = gr.Button("💬️ New Chat")
            
            # Chat selector
            self.gr_leftbar.chat_selector = gr.HTML(
                value=self.generate_chat_selector(),
                elem_id="chat-list-container"
            )
            
            # Hidden elements (For customized JS responses)
            self.gr_leftbar.hidden_input_chatindex = gr.Number(elem_id="hidden_input_chatindex", elem_classes=["custom-hidden"])
            self.gr_leftbar.hidden_input_rename = gr.Textbox(elem_id="hidden_input_rename", elem_classes=["custom-hidden"])
            self.gr_leftbar.hidden_input_export = gr.Textbox(elem_classes=["custom-hidden"])
            self.gr_leftbar.hidden_btn_select = gr.Button(elem_id="hidden_btn_select", elem_classes=["custom-hidden"])
            self.gr_leftbar.hidden_btn_rename = gr.Button(elem_id="hidden_btn_rename", elem_classes=["custom-hidden"])
            self.gr_leftbar.hidden_btn_export = gr.Button(elem_id="hidden_btn_export", elem_classes=["custom-hidden"])
            self.gr_leftbar.hidden_btn_delete = gr.Button(elem_id="hidden_btn_delete", elem_classes=["custom-hidden"])

    
    def build_right(self):
        """
        Build right sidebar
        
        Input:
            None
        Output: 
            None
        """
        
        with gr.Sidebar(width=350, position="right", label="Settings", open=False) as self.gr_rightbar.rightbar:
            
            # Title
            gr.Markdown("## User Settings")
            
            # Table 1: Ollama Parameters
            with gr.Tab("Parameters", elem_classes=["settings-padding"]):
            
                with gr.Column(elem_classes=["param-list"]):
            
                    # Read parameter setting JSON file
                    with open(self.current_path+'/usersettings_params.json', "r", encoding="utf-8") as f:
                        params = json.load(f)
                        
                    # Generate parameters
                    for param in params:
                        self.generate_settings_component(
                            name = param["name"], 
                            component = getattr(gr, param["component"]),
                            component_init = param["component_init"]
                        )
            
            # Table 2: Ollama Models
            with gr.Tab("Models", elem_classes=["settings-padding"]):
                
                gr.Markdown("### Ollama Model Directory")

                # Directory picker
                self.gr_rightbar.model_path_text = gr.Textbox(
                    value=self.settings["ollama_models"],
                    label="",
                    max_lines=1,
                    container=False,
                    interactive=True,
                    elem_id="dir-path",
                    #submit_btn="📁",      # TODO: Change this to an actual file picker
                )
                
                # Action buttons
                with gr.Row():
                    
                    # Save button
                    self.gr_rightbar.model_path_save = gr.Button(
                        "💾 Save",
                        min_width=0
                    )
                    self.gr_rightbar.model_path_reset = gr.Button(
                        "🔄 Reset",
                        min_width=0
                    )
                    
                    # Reset button
                
                gr.HTML("")
                
                gr.Markdown("### Install Models")
                
                # Initial check whether the path is writable
                self.gr_rightbar.is_model_path_writable = os.access(self.settings["ollama_models"], os.W_OK)

                # List remote models to install
                self.gr_rightbar.model_install_names = gr.Dropdown(
                    choices=self.generate_settings_model_name_choices(),
                    label="Model Name",
                    interactive=self.gr_rightbar.is_model_path_writable
                )
                self.gr_rightbar.model_install_tags = gr.Dropdown(
                    choices=self.generate_settings_model_tag_choices(self.gr_rightbar.model_install_names.value),
                    label="Model Tag",
                    interactive=self.gr_rightbar.is_model_path_writable
                )
                
                # Install / remove button
                with gr.Row():
                    
                    # Initial check which button to display
                    is_installed = self.gr_rightbar.model_install_names.value + ":" + self.gr_rightbar.model_install_tags.value in self.models
                    
                    # Generate buttons
                    self.gr_rightbar.model_install_btn = gr.Button("📥 Install Selected Model", 
                                                                    interactive=self.gr_rightbar.is_model_path_writable,
                                                                    visible=not is_installed)
                    self.gr_rightbar.model_remove_btn = gr.Button("❌ Remove Selected Model", 
                                                                    interactive=self.gr_rightbar.is_model_path_writable,
                                                                    visible=is_installed)
                
                # Status stream
                self.gr_rightbar.model_install_status = gr.Markdown("")
    
    def build_ui(self):
        """
        Build UI
        
        Input:
            None
        Output: 
            None
        """
        
        # Set page icon
        set_icon = f"<link rel='icon' type='image/png' href='gradio_api/file={self.current_path}/images/logo.png'>\n\n"
        
        with gr.Blocks(
            css_paths   = self.current_path+'/grblocks.css',
            title       = "Ollama OnDemand",
            head        = set_icon,
            head_paths  = self.current_path+'/head.html'
        ) as self.demo:
            
            #----------------------------------------------------------
            # Create UI
            #----------------------------------------------------------
            
            # Build main view
            self.build_main()
                
            # Build left sidebar: Chat Sessions
            self.build_left()
                
            # Build right sidebar: User Settings
            self.build_right()
            
            #----------------------------------------------------------
            # Event handlers
            #----------------------------------------------------------
            
            # Register event handlers in main view
            self.register_main()
            
            # Register event handlers in left sidebar
            self.register_left()
            
            # Register event handlers in right sidebar
            self.register_right()

            #----------------------------------------------------------
            # Load UI
            #----------------------------------------------------------
        
            # Initialize page on load
            init_html = """
                function() {
                
                    // Expand left bar if not on mobile device
                    const leftbar = document.querySelector(".sidebar:not(.right)");
                    const expand_btn = leftbar.querySelector("button");
                    if (leftbar && expand_btn && window.innerWidth > 768) {
                        expand_btn.click();
                    }
                    
                    // Collapse all thinking tags
                    collapse_thinking();
                    
                }
            """
            
            # Load UI
            self.demo.load(
                fn=lambda : self.chat_history_display(),
                inputs=[],
                outputs=[self.gr_main.chatbot]
            ).then(
                fn=None,
                inputs=[],
                outputs=[],
                js=init_html
            )
    
    def launch(self):
        """
        Launch UI after it is built.
        
        Input:
            None
        Output: 
            None
        """
        
        self.demo.launch(
            server_name=self.args.host,
            server_port=self.args.port,
            root_path=self.args.root_path,
            allowed_paths=[self.current_path]
        )
