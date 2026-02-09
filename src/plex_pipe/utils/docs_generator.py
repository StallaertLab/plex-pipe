from __future__ import annotations

import inspect
import sys
from pathlib import Path

# Ensure the package is in the path so we can import it relative to this script
# (Adjust parents count if folder structure changes)
sys.path.append(str(Path(__file__).parents[2]))

from pydantic import BaseModel
from pydantic_core import PydanticUndefined

# Importing the package triggers the @register decorators
from plex_pipe.processors import REGISTRY


def generate_docs() -> str:
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


def main() -> None:
    """Generates and writes the documentation to the default path."""
    # ensures UTF-8 encoding and avoids shell redirection issues
    output_path = Path(__file__).parents[3] / "docs" / "usage" / "processors.md"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    content = generate_docs()
    if output_path.exists():
        with open(output_path, encoding="utf-8") as f:
            if f.read() == content:
                return

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(content)

    print(f"Generated documentation at: {output_path}")


if __name__ == "__main__":
    main()
