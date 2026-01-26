import sys
from pathlib import Path

# Add the 'src' directory to sys.path so we can import the generator
# Assuming hooks.py is in docs/, the root is one level up
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root / "src"))


def on_pre_build(config):
    """Generate the processors documentation before the build starts."""
    from plex_pipe.utils.docs_generator import main as generate_docs

    print("Running dynamic docs generator...")
    generate_docs()
