"""General utilities for configuration loading and dynamic path handling."""

import copy
import os
import platform
from pathlib import Path
from typing import Any

import yaml

from plex_pipe.config.config_schema import AnalysisConfig


def load_workstation_config(config_path: str | Path) -> dict[str, Any]:
    """Loads workstation-specific configuration from a YAML file.

    Args:
        config_path: Path to the YAML configuration file.

    Returns:
        A dictionary containing the workstation configuration.

    Raises:
        KeyError: If the 'workstations' key is missing in the configuration.
    """
    with open(config_path) as file:
        config = yaml.safe_load(file)

    # Handle 'workstations' separately
    if "workstations" in config:
        hostname = platform.node()
        workstation_config = config.get("workstations", {}).get(hostname, {})

        return workstation_config

    else:
        raise KeyError("'workstations' key not found in the configuration file.")


def load_config(settings_path: str | Path) -> AnalysisConfig:
    """Loads analysis settings from a YAML file.

    Args:
        settings_path: Path to the YAML settings file.

    Returns:
        The validated AnalysisConfig object.
    """
    with open(settings_path) as file:
        settings = yaml.safe_load(file)

    # expand placeholders
    settings = expand_pipeline(settings)

    # Validate and get the "blueprint" object
    config = AnalysisConfig.model_validate(settings)

    # create dirs necessary for the analysis
    for p in [
        config.analysis_dir,
        config.log_dir_path,
        config.roi_info_file_path.parent,
        config.roi_dir_tif_path,
        config.roi_dir_output_path,
    ]:
        os.makedirs(p, exist_ok=True)

    return config


def contains_placeholder(obj: Any, placeholder: str = "${input}") -> bool:
    """Recursively checks if the placeholder appears anywhere in the object.

    Args:
        obj: The object to search (dict, list, or string).
        placeholder: The placeholder string to look for. Defaults to "${input}".

    Returns:
        True if the placeholder is found, False otherwise.
    """
    if isinstance(obj, dict):
        return any(contains_placeholder(v, placeholder) for v in obj.values())
    if isinstance(obj, list):
        return any(contains_placeholder(v, placeholder) for v in obj)
    return isinstance(obj, str) and placeholder in obj


def replace_placeholders(obj: Any, mapping: dict[str, Any]) -> Any:
    """Recursively substitutes ${key} with mapping[key] in strings.

    Args:
        obj: The object to process (dict, list, or string).
        mapping: A dictionary mapping placeholder keys to replacement values.

    Returns:
        The object with placeholders replaced.
    """
    if isinstance(obj, dict):
        return {k: replace_placeholders(v, mapping) for k, v in obj.items()}
    if isinstance(obj, list):
        return [replace_placeholders(v, mapping) for v in obj]
    if isinstance(obj, str):
        out = obj
        for k, v in mapping.items():
            out = out.replace("${" + k + "}", str(v))
        return out
    return obj


def expand_pipeline(
    cfg: dict[str, Any], section: str = "additional_elements"
) -> dict[str, Any]:
    """Expands pipeline steps containing list inputs and placeholders.

    If a step has a list as input and contains the "${input}" placeholder,
    it is expanded into multiple steps, one for each input item.

    Args:
        cfg: The configuration dictionary.
        section: The section key to expand. Defaults to "additional_elements".

    Returns:
        The configuration dictionary with the section expanded.
    """
    expanded = []
    for step in cfg.get(section, []):
        inputs = step.get("input")
        if isinstance(inputs, list) and contains_placeholder(step, "${input}"):
            for inp in inputs:
                inst = copy.deepcopy(step)
                inst["input"] = inp
                inst = replace_placeholders(inst, {"input": inp})
                expanded.append(inst)
        else:
            expanded.append(step)
    cfg[section] = expanded
    return cfg
