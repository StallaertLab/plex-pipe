# Installation Guide

## uv Setup

We recommend using [uv](https://docs.astral.sh/uv/) for high-performance environment management.

---
### Use plex-pipe in my own scripts

Use this if you want to import `plex-pipe` into your own scripts.

```bash
# Create a virtual environment
uv venv --python 3.12

# Install plex-pipe with all optional features
uv pip install "plex_pipe[all] @ git+https://github.com/StallaertLab/plex-pipe.git"
```

The `[all]` extra pulls in every optional feature: segmentation (Cellpose,
InstanSeg, and PyTorch), the napari GUI, Jupyter support, and Globus transfer.

Using an NVIDIA GPU? See [GPU support](#gpu-support-nvidia-cuda) below.

---
### Run the pipeline & follow the tutorials

Use this if you want to run the provided analysis notebooks and explore the example workflows:

```bash
# Clone the repository to get the notebooks and source
git clone https://github.com/StallaertLab/plex-pipe.git
cd plex-pipe

# Install with all optional features
uv sync --extra all
```

Using an NVIDIA GPU? See [GPU support](#gpu-support-nvidia-cuda) below.

!!! note Windows Encoding Fix
    To avoid UnicodeDecodeError when running interactive notebooks on Windows, you must enable Python's UTF-8 mode. Create a file named .env in the project root with this line:

    ```yaml
    PYTHONUTF8=1
    ```

---
### GPU support (NVIDIA CUDA)

Both installation methods above install **PyTorch from PyPI**, which provides the
right build for your platform automatically:

- **Linux + NVIDIA** — the PyPI build is already CUDA-enabled; nothing extra to do.
- **macOS (Apple Silicon)** — you get the CPU + **Metal/MPS** build; use the GPU with
  `device="mps"`. There is no CUDA on Apple hardware.
- **Windows + NVIDIA** — the PyPI build is **CPU-only**. To use your GPU, install a
  CUDA build of torch yourself (after either install method above).

**Windows CUDA install:** to check your driver's CUDA version run the following command:

```bash
nvidia-smi
```
Look at the top-right corner of the table for "CUDA Version: XX.X".

Install [pytorch-cuda](https://pytorch.org/get-started/locally/) version that matches your CUDA version. For example for CUDA 12.8:

```bash
uv pip install torch torchvision --index-url https://download.pytorch.org/whl/cu128 --reinstall
```
