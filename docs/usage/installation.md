# Installation Guide

## uv Setup

We recommend using [uv](https://docs.astral.sh/uv/) for high-performance environment management.

---
### Minimal installation (library only)

Use this if you want to import `plex-pipe` into your own scripts.

```bash
# Create a virtual environment
uv venv --python 3.12

# Install for CPU-only
uv pip install "plex_pipe[all-cpu] @ git+https://github.com/StallaertLab/plex-pipe.git"

# OR: Install with GPU support (requires CUDA 12.6 compatible drivers)
uv pip install "plex_pipe[all-gpu] @ git+https://github.com/StallaertLab/plex-pipe.git"
```

---
### Full setup (with example notebooks)

Use this if you want to run the provided analysis notebooks and explore the example workflows:

```bash
# Clone the repository to get the notebooks and source
git clone https://github.com/StallaertLab/plex-pipe.git
cd plex-pipe
# Build the environment based on your hardware:

# For CPU-only:
uv sync --extra all-cpu

# OR: Install with GPU support (requires CUDA 12.6 compatible drivers)
uv sync --extra all-gpu
```

!!! note Windows Encoding Fix
    To avoid UnicodeDecodeError when running interactive notebooks on Windows, you must enable Python's UTF-8 mode. Create a file named .env in the project root with this line:

    ```yaml
    PYTHONUTF8=1
    ```

---
## Conda Step-by-Step Setup

This guide covers the setup for **PlexPipe** with GPU support. Following these steps in order is critical to ensure that the segmentation engines (InstanSeg, Cellpose) can access your hardware acceleration.

Install [Miniconda](https://docs.conda.io/en/latest/miniconda.html) or [Anaconda](https://www.anaconda.com/).

### 1. Create a Clean Environment
Open your terminal (PowerShell or Anaconda Prompt) and create a fresh environment.

```bash
conda create -n plex-pipe-gpu python=3.12 git -c conda-forge -y
conda activate plex-pipe-gpu
```

---
### 2. Identify and Install PyTorch (CUDA Check)
Before installing, you must check which CUDA version your driver supports. Run the following command:

```bash
nvidia-smi
```
Look at the top-right corner of the table for "CUDA Version: XX.X".

Install [pytorch-cuda](https://pytorch.org/get-started/locally/) version that matches your CUDA version. For example for CUDA 12.8:

```bash
pip3 install torch torchvision --index-url https://download.pytorch.org/whl/cu128
```

---

### 3. Install Segmentation Libraries

```bash
pip install cellpose instanseg-torch
```

---

### 3. Install Napari
We install napari with the [all] extra to ensure the GUI and Qt backend are included, followed by instanseg.

```bash
pip install "napari[all]"
```

---

### 4. Clone and Install PlexPipe
Instead of installing directly, clone the repository to your computer so you can access the provided examples and notebooks.

#### Navigate to where you want to keep the code (e.g., analysis-pipelines)
```bash
cd analysis-pipelines
```

#### Clone the repository
```bash
git clone https://github.com/StallaertLab/plex-pipe.git
cd plex-pipe
```

#### Install in editable mode (this links the folder to your environment)
```bash
pip install -e .
```
