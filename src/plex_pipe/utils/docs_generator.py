from __future__ import annotations

import inspect
import re
import sys
from pathlib import Path

# Ensure the package is in the path so we can import it relative to this script
# (Adjust parents count if folder structure changes)
sys.path.append(str(Path(__file__).parents[2]))

from pydantic import BaseModel
from pydantic_core import PydanticUndefined

from plex_pipe.object_quantification.metrics import METRIC_REGISTRY

# Importing the package triggers the @register decorators
from plex_pipe.processors import REGISTRY


def generate_processors_docs() -> str:
    """Generates Markdown documentation for all registered processors."""

    output = ["# Available Processors"]
    output.append(
        "Processors are modular operations used within [Step 04: Image Processing](../analysis_steps/04_image_processing.md)."
    )
    output.append("")
    output.append("---")

    # Iterate over Kinds (e.g., image_enhancer, object_segmenter)
    for kind in sorted(REGISTRY.keys()):
        processors = REGISTRY[kind]
        if not processors:
            continue

        # Section Header
        output.append("")
        output.append("---")
        output.append(f"## {kind.replace('_', ' ').title()}s")
        output.append("")
        output.append("---")
        output.append("")
        output.append("---")
        output.append("")

        # Iterate over Processors in that Kind
        for name in sorted(processors.keys()):
            entry = processors[name]
            cls = entry.processor_class
            params_model = entry.param_model

            output.append(f"### `{name}`")
            output.append("")

            # 1. Class Docstring
            doc = inspect.getdoc(cls)
            if doc:
                output.append(doc)
                output.append("")

            output.append('<details markdown="1">')
            output.append("<summary><b>Technical Specs</b></summary>")
            output.append("")
            # 2. Inputs/Outputs
            inputs = getattr(cls, "EXPECTED_INPUTS", "Variable")
            outputs = getattr(cls, "EXPECTED_OUTPUTS", "Variable")

            if inputs is None:
                inputs = "Variable"
            if outputs is None:
                outputs = "Variable"

            output.append(f"*   **Inputs**: {inputs}")
            output.append(f"*   **Outputs**: {outputs}")

            # 3. Parameters (from Pydantic fields)
            # Check if it has actual fields (ignore empty/default models)
            if (
                params_model
                and params_model is not BaseModel
                and params_model.model_fields
            ):
                output.append("*   **Parameters**:")

                for field_name, field_info in params_model.model_fields.items():
                    desc = field_info.description or "No description."

                    # Format default value
                    default_val = field_info.get_default()
                    default_str = ""
                    if default_val is not None and default_val != PydanticUndefined:
                        default_str = f"default=`{default_val}`"

                    # Format type
                    # Clean up "typing." prefix for cleaner docs
                    type_name = str(field_info.annotation).replace("typing.", "")

                    output.append(
                        f"    *   `{field_name}` ({type_name}{default_str}): {desc}"
                    )
            else:
                output.append("*   **Parameters**: None.")

            output.append("</details>")
            output.append("---")
            output.append("")

    return "\n".join(output)


def generate_metrics_docs() -> str:
    """Generates a Markdown table for the quantification metrics."""
    output = [""]
    output.append("| Feature Name | Source / Implementation | Description |")
    output.append("| :--- | :--- | :--- |")

    for name, metric in METRIC_REGISTRY.items():
        if metric.is_extra:
            source = f"Custom: `{metric.func.__name__}`"
            desc = (
                metric.func.__doc__.split("\n")[0]
                if metric.func.__doc__
                else "No description."
            )
        else:
            source = f"Skimage: `{metric.func}`"
            desc = "Standard intensity property from `skimage.measure.regionprops`."
        output.append(f"| **{name}** | {source} | {desc} |")

    return "\n".join(output)


def update_file_with_markers(
    file_path: Path, content: str, start_marker: str, end_marker: str
):
    """Replaces content between markers or appends it if markers are missing."""
    if not file_path.exists():
        print(f"Warning: {file_path} not found. Skipping update.")
        return

    with open(file_path, encoding="utf-8") as f:
        original_content = f.read()

    new_section = f"{start_marker}\n\n{content}\n\n{end_marker}"

    if start_marker in original_content and end_marker in original_content:
        pattern = re.compile(f"{start_marker}.*?{end_marker}", re.DOTALL)
        updated_content = pattern.sub(new_section, original_content)
    else:
        updated_content = original_content + "\n\n" + new_section

    if original_content.strip() != updated_content.strip():
        with open(file_path, "w", encoding="utf-8", newline="") as f:
            f.write(updated_content)
        print(f"Updated: {file_path.name}")
    else:
        # If we hit this, mkdocs serve will NOT refresh the browser
        print(f"No changes detected in {file_path.name}")


def main() -> None:
    docs_dir = Path(__file__).parents[3] / "docs"

    # 1. Lazy Update for Processors ---
    proc_path = docs_dir / "usage" / "processors.md"
    new_proc_content = generate_processors_docs()

    # Read existing content to check for differences
    current_proc_content = ""
    if proc_path.exists():
        current_proc_content = proc_path.read_text(encoding="utf-8")

    # Only write if the content is truly different
    if new_proc_content.strip() != current_proc_content.strip():
        proc_path.write_text(new_proc_content, encoding="utf-8")
        print(f"Generated: {proc_path}")
    else:
        print(f"No changes detected in {proc_path.name}")

    # 2. Update Quantification (In-place Injection)
    quant_path = docs_dir / "analysis_steps" / "05_quantification.md"
    metrics_content = generate_metrics_docs()
    update_file_with_markers(
        quant_path, metrics_content, "<!-- METRICS_START -->", "<!-- METRICS_END -->"
    )


if __name__ == "__main__":
    main()
