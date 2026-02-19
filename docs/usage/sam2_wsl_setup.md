# Setting up SAM2 on WSL

The **Segment Anything Model 2 (SAM2)** is required for automatic core detection in PlexPipe. Since SAM2 does not natively support Windows, Windows users must run it via the Windows Subsystem for Linux (WSL).

## Prerequisites

1.  **Windows 10 or 11**
2.  **NVIDIA GPU** (Recommended for performance, though CPU execution is possible but slow).

## Step 1: Install WSL

Open PowerShell as Administrator and run:

```powershell
wsl --install
```

Restart your computer if prompted. By default, this installs Ubuntu.

## Step 2: Set up the Python Environment in WSL

1.  Open your WSL terminal (search for "Ubuntu" in the Start menu).
2.  Update packages and install Python/Pip:

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install python3 python3-pip python3-venv git -y
```

3.  Create a virtual environment for SAM2:

```bash
python3 -m venv ~/sam2_env
source ~/sam2_env/bin/activate
```

## Step 3: Install SAM2

Follow the official installation instructions from the SAM2 repository. Typically, this involves:

1.  Installing PyTorch (check pytorch.org for the command matching your CUDA version).
2.  Installing SAM2:

```bash
pip install git+https://github.com/facebookresearch/sam2.git
```

## Step 4: Configure PlexPipe

When running the Core Detection widget in PlexPipe on Windows:

1.  Locate the path to your python executable inside WSL. It is usually:
    `/home/<username>/sam2_env/bin/python`
2.  Provide this path to the widget when prompted or in the configuration settings.
