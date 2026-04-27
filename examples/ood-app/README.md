# Ollama OnDemand — HPC / Open OnDemand Deployment

This directory contains a complete [Open OnDemand](https://openondemand.org/) batch-connect app template for deploying Ollama OnDemand on an HPC cluster. It is designed as a starting point — each HPC system is configured differently, so some adaptation will be required.

---

## Table of Contents

1. [Key Files](#1-key-files)
2. [Minimal Setup Steps](#2-minimal-setup-steps)
3. [GPU Support](#3-gpu-support)
4. [Notes](#4-notes)

---

## 1. Key Files

| File | Purpose |
|---|---|
| `manifest.yml` | App metadata (name, category, description) |
| `form.yml.erb` | Job submission form (allocation, queue, duration, work directory) |
| `submit.yml.erb` | Slurm submission parameters |
| `view.html.erb` | Connect button shown to the user once the job is running |
| `template/script.sh.erb` | The main script to run after job starts: finds a free port to start Ollama server, then starts the web service |

---

## 2. Minimal Setup Steps

1. **Copy the app directory** to your OOD apps directory (typically `/var/www/ood/apps/sys/` or a per-user apps path).
2. **Edit `form.yml.erb`**: set your cluster name and update the queue/partition list, and add additional options appropriate to your HPC system.
3. **Edit `submit.yml.erb`**: set your job submission script. In this sample app, Slurm is set up as the job scheduler.
4. **Edit `manifest.yml`**: set app information as appropriate to your HPC system.
5. **Edit `template/script.sh.erb`**: set the path to the Ollama OnDemand container, adjust other Ollama OnDemand command-line options, and edit other parts of the script as appropriate to your HPC system.

---

## 3. GPU Support

The batch script uses `singularity run --nv` which targets **NVIDIA CUDA GPUs** by default.

**For AMD GPUs (ROCm):** replace `--nv` with `--rocm` in `template/script.sh.erb`, and ensure you built the container using the dedicated AMD recipe:

```bash
cd container
singularity build ollamaondemand-rocm.sif singularity-rocm.def
```

---

## 4. Notes

- The `template/script.sh.erb` script automatically finds a free port for the Gradio web server and passes the correct `--root-path` to Ollama OnDemand so it works behind the Open OnDemand reverse proxy.
- The script also unsets `ROCR_VISIBLE_DEVICES` to work around a known conflict on some cluster configurations.
- For the full list of Ollama OnDemand command-line options, see the [main README](../../README.md#4-command-line-options) or run:

  ```bash
  singularity run /path/to/ollamaondemand.sif --help
  ```

---

## Author

**Dr. Jason Li** — Louisiana State University HPC  
jasonli3@lsu.edu

