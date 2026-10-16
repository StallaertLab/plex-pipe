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
uv pip install "plex_pipe[all]"
```

Without uv, `pip install "plex_pipe[all]"` in any Python 3.12–3.14 environment does the same.

The `[all]` extra pulls in every optional feature: segmentation (Cellpose,
InstanSeg, and PyTorch), the napari GUI, Jupyter support, and Globus transfer.

To check the installation on example data, `plex_pipe.setup_example("plexpipe_example")` downloads the images and writes a ready-to-use config and ROIs; the short script that runs the pipeline on them is in the [README](https://github.com/plexpipe/plex-pipe#try-it-on-example-data).

Using an NVIDIA GPU? See [GPU support](#gpu-support-nvidia-cuda) below.

---
### Run the pipeline & follow the tutorials

Use this if you want to run the provided analysis notebooks and explore the example workflows:

```bash
# Clone the repository to get the notebooks and source
git clone https://github.com/plexpipe/plex-pipe.git
cd plex-pipe

# Install with all optional features
uv sync --extra all
```

Using an NVIDIA GPU? See [GPU support](#gpu-support-nvidia-cuda) below.

The first notebook downloads the example data (an archive of about 116 MB) with `fetch_example()`. The archive is downloaded once into your user cache folder (on macOS `~/Library/Caches/plex_pipe`, on Linux `~/.cache/plex_pipe`) and reused afterwards; it is safe to delete, and the next call downloads it again. To keep it somewhere else, for example on an HPC system with a small home directory, set the `PLEX_PIPE_DATA_DIR` environment variable. To see where it is on your machine:

```bash
uv run python -c "import pooch; print(pooch.os_cache('plex_pipe'))"
```

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

**With a clone of the repository:** instead of the manual install, `uv sync --extra all-cuda` installs a CUDA 12.6 build of PyTorch on Windows and Linux.

!!! warning "`pip install plex_pipe[all-cuda]` does not install CUDA PyTorch"
    The CUDA build comes only with `uv sync --extra all-cuda` in a clone. Installed with `pip` or `uv pip install`, `plex_pipe[all-cuda]` installs the same packages as `plex_pipe[all]`, with the CPU-only PyTorch on Windows. Install the CUDA build of PyTorch yourself as shown above. To check which build you have:

    ```bash
    python -c "import torch; print(torch.__version__, torch.cuda.is_available())"
    ```

    `+cpu False` means CPU only; a CUDA build on a working NVIDIA setup prints a `+cu…` version and `True`.
