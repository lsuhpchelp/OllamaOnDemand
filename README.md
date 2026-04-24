# Ollama OnDemand

<p align="center">
  <img src="images/logo.png" alt="Ollama OnDemand Logo" height="80">
</p>

A ChatGPT-style web interface for running large language models (LLMs) on HPC clusters. Built on [Gradio](https://www.gradio.app/) and [Ollama](https://ollama.com/), Ollama OnDemand is designed from the ground up for HPC environments and natively supports [Open OnDemand](https://openondemand.org/) subpath routing.

---

## Table of Contents

1. [Features](#1-features)
2. [Requirements](#2-requirements)
3. [Installation](#3-installation)
   - [3.1 Build the container](#31-build-the-container)
   - [3.2 Run the container](#32-run-the-container)
4. [Command-Line Options](#4-command-line-options)
   - [4.1 Example](#41-example)
5. [Deployment](#5-deployment)
   - [5.1 HPC / Open OnDemand Deployment](#51-hpc--open-ondemand-deployment)
   - [5.2 Local Deployment](#52-local-deployment)
6. [Directory Layout](#6-directory-layout)
7. [License](#7-license)
8. [Author](#8-author)

---

## 1. Features

- **Multi-session chat** — Create, rename, export, and delete independent chat conversations. Chat titles are auto-generated using a small background model.
- **Multimodal inputs** — Attach images, plain-text files, and PDFs to your messages. PDFs are automatically converted to images for vision-capable models.
- **Thinking / reasoning model support** — `<think>` blocks from reasoning models are rendered in a collapsible panel so the final answer stays readable.
- **In-UI model management** — Install or remove models from [ollama.com](https://ollama.com) directly from the Settings panel, with live download progress. Supports read-only shared model directories (admin-maintained model pools).
- **Customizable inference parameters** — Fine-tune temperature, top-p, top-k, context window, GPU layers, Mirostat, and many more parameters per session without touching the command line.
- **Persistent state** — Chat history and user settings are saved to a configurable work directory and restored on the next launch.
- **HPC-ready container** — Ships with an official [Singularity](https://sylabs.io/) recipe built on top of the `ollama/ollama` Docker image, including Miniforge Python and all required Python packages.
- **Open OnDemand integration** — A ready-to-use OOD batch-connect app template is included (`examples/ood-app`).

---

## 2. Requirements

- [Singularity](https://sylabs.io/) (used to build and run the container)
- GPU access is strongly recommended for reasonable inference performance.

---

## 3. Installation

Ollama OnDemand is distributed as a Singularity container. A definition file is provided at `container/singularity.def` and bundles Ollama, Miniforge Python, and all required Python packages.

### 3.1 Build the container

> **Important:** The build must be run from inside the `container/` directory so that the `%files` section can copy the project files correctly.

```bash
cd container
sudo singularity build ollamaondemand.sif singularity.def
```

### 3.2 Run the container

```bash
singularity run --nv ollamaondemand.sif [OPTIONS]
```

The `--nv` flag enables NVIDIA GPU access. See [Section 4](#4-command-line-options) for the full list of available options.

---

## 4. Command-Line Options

Pass options directly after the `.sif` image name:

```bash
singularity run --nv ollamaondemand.sif [OPTIONS]
```

| Option | Default | Description |
|---|---|---|
| `--host` | `0.0.0.0` | Host for the Gradio web server |
| `--port` | `7860` | Port for the Gradio web server |
| `--root-path` | _(none)_ | Root path / subpath for the web interface (required for Open OnDemand) |
| `-w`, `--workdir` | `~/.ollama/ondemand` | Directory where Ollama OnDemand stores chat history, settings, and cache |
| `--ollama-host` | `127.0.0.1:11434` | Address of the Ollama backend server |
| `--ollama-models` | `~/.ollama/models` | Path to the Ollama model directory |
| `--title-model` | `gemma3:4b` | Small model used for fast auto-generation of chat titles |
| `--debug` | _(off)_ | Enable debug mode |
| `-v`, `--version` | | Print version and exit |

### 4.1 Example

```bash
singularity run --nv ollamaondemand.sif \
    --port 8080 \
    --workdir /scratch/$USER/ollama_ondemand \
    --ollama-models /shared/models/ollama \
    --title-model gemma3:4b
```

---

## 5. Deployment

### 5.1 HPC / Open OnDemand Deployment

A complete Open OnDemand batch-connect app template is located in `examples/ood-app/`. It is designed as a starting point — each HPC system is configured differently, so some adaptation will be required.

#### Key files

| File | Purpose |
|---|---|
| `manifest.yml` | App metadata (name, category, description) |
| `form.yml.erb` | Job submission form (allocation, queue, duration, work directory) |
| `submit.yml.erb` | Slurm submission parameters |
| `template/script.sh.erb` | Batch script: finds a free port, starts the Singularity container |
| `view.html.erb` | Connect button shown to the user once the job is running |

#### Minimal setup steps

1. Copy `examples/ood-app/` to your OOD apps directory.
2. Edit `form.yml.erb`: set your cluster name and update the queue/partition list.
3. Edit `template/script.sh.erb`: set the path to `ollamaondemand.sif` and the shared model directory (if any).
4. Edit `manifest.yml`: replace `[INSERT ORGANIZATION NAME]` with your institution name in the Terms of Use section.

### 5.2 Local Deployment

To run Ollama OnDemand locally, build the Singularity container (see [Section 3](#3-installation)) and run it with:

```bash
singularity run /path/to/ollamaondemand.sif
```

To read help information about all available command-line arguments, run:

```bash
singularity run /path/to/ollamaondemand.sif --help
```

---

## 6. Directory Layout

```
Ollama OnDemand/
├── main.py               # Application entry point and Gradio UI
├── arg.py                # Command-line argument definitions
├── chatsessions.py       # Chat session management (load/save/CRUD)
├── usersettings.py       # User settings persistence
├── usersettings.json     # Inference parameter definitions for the Settings panel
├── multimodal.py         # Multimodal file handling (images, text, PDF)
├── remotemodels.py       # Fetches available models from ollama.com
├── grblocks.css          # Custom Gradio CSS
├── head.html             # Custom HTML injected into the page <head>
├── images/
│   └── logo.png          # App logo
├── container/
│   └── singularity.def   # Singularity container recipe
└── examples/
    ├── local-setup/      # Notes for a local / standalone setup
    └── ood-app/          # Open OnDemand batch-connect app template
```

---

## 7. License

See [LICENSE](LICENSE) for details.

---

## 8. Author

**Dr. Jason Li** — Louisiana State University HPC  
jasonli3@lsu.edu
