# Examples

This directory contains ready-to-use deployment examples for Ollama OnDemand. Choose the scenario that best fits your environment.

## Contents

| Directory | Description |
|---|---|
| [`ood-app/`](ood-app/) | Open OnDemand batch-connect app template for HPC clusters |
| [`local-setup/`](local-setup/) | Instructions for running Ollama OnDemand on a local machine |

---

## Which example should I use?

- **HPC cluster with Open OnDemand** — use [`ood-app/`](ood-app/). It provides a complete batch-connect app template that submits a Slurm job, finds a free port, and starts the container automatically.
- **Local / standalone machine** — use [`local-setup/`](local-setup/). It explains how to build the Singularity container and run it directly on your workstation or a single server node.

---

## Author

**Dr. Jason Li** — Louisiana State University HPC  
jasonli3@lsu.edu
