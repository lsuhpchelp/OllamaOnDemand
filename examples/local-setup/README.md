# Ollama OnDemand — Local Deployment

This guide explains how to build and run Ollama OnDemand on a local machine or standalone server node using Singularity.

---

## Table of Contents

1. [Requirements](#1-requirements)
2. [Build the Container](#2-build-the-container)
3. [Run the Container](#3-run-the-container)
4. [GPU Support](#4-gpu-support)
5. [Command-Line Options](#5-command-line-options)

---

## 1. Requirements

- [Singularity](https://sylabs.io/) installed on your system
- An NVIDIA or AMD GPU is strongly recommended for reasonable inference performance

---

## 2. Build the Container

> **Important:** The build must be run from inside the `container/` directory so that the `%files` section can copy the project files correctly.

```bash
# CPU / NVIDIA GPU
cd container
sudo singularity build ollamaondemand.sif singularity.def

# AMD GPU (ROCm)
cd container
sudo singularity build ollamaondemand-rocm.sif singularity-rocm.def
```

---

## 3. Run the Container

Once the container is built, launch it with:

```bash
# CPU only
singularity run /path/to/ollamaondemand.sif

# NVIDIA GPU
singularity run --nv /path/to/ollamaondemand.sif

# AMD GPU (ROCm)
singularity run --rocm /path/to/ollamaondemand-rocm.sif
```

The web interface will be available at `http://localhost:7860` by default.

---

## 4. GPU Support

| Hardware | Singularity flag | Definition file | Output image |
|---|---|---|---|
| CPU only | _(none)_ | `singularity.def` | `ollamaondemand.sif` |
| NVIDIA (CUDA) | `--nv` | `singularity.def` | `ollamaondemand.sif` |
| AMD (ROCm) | `--rocm` | `singularity-rocm.def` | `ollamaondemand-rocm.sif` |

---

## 5. Command-Line Options

Pass options directly after the `.sif` image name:

```bash
singularity run --nv ollamaondemand.sif [OPTIONS]
```

| Option | Default | Description |
|---|---|---|
| `--host` | `0.0.0.0` | Host for the Gradio web server |
| `--port` | `7860` | Port for the Gradio web server |
| `--root-path` | _(none)_ | Root path / subpath for the web interface |
| `-w`, `--workdir` | `~/.ollama/ondemand` | Directory for chat history, settings, and cache |
| `--ollama-host` | `127.0.0.1:11434` | Address of the Ollama backend server |
| `--ollama-models` | `~/.ollama/models` | Path to the Ollama model directory |
| `--title-model` | `gemma3:4b` | Small model used for auto-generating chat titles |
| `--model-filter` | `remotemodels_filter.json` | Path to a JSON file that filters which remote models are shown in the UI. See `remotemodels_filter.json` for instructions |
| `--debug` | _(off)_ | Enable debug mode |
| `-v`, `--version` | | Print version and exit |

To print the full help message, run:

```bash
singularity run /path/to/ollamaondemand.sif --help
```

### Example

```bash
singularity run --nv ollamaondemand.sif \
    --port 8080 \
    --workdir ~/ollama_ondemand \
    --ollama-models ~/models/ollama \
    --title-model gemma3:4b
```

---

## Author

**Dr. Jason Li** — Louisiana State University HPC  
jasonli3@lsu.edu

