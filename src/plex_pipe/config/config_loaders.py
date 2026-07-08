"""General utilities for configuration loading and dynamic path handling."""

import copy
import os
import platform
from pathlib import Path
from typing import Any

import yaml
from loguru import logger
from pydantic import ValidationError

from plex_pipe.config.config_migrations import (
    CURRENT_SCHEMA_VERSION,
    migrate_to_current,
)
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

    Raises:
        ValueError: If the config is a newer schema than this build understands,
            or if it fails validation (raised with a human-readable message).
    """
    with open(settings_path) as file:
        settings = yaml.safe_load(file)

    # Version check + in-memory migration of older configs (writes nothing to
    # disk; logs a hint pointing at migrate_config if a migration happened).
    settings, _ = migrate_to_current(settings)

    # expand placeholders
    settings = expand_pipeline(settings)

    # Validate and get the "blueprint" object
    try:
        config = AnalysisConfig.model_validate(settings)
    except ValidationError as exc:
        raise ValueError(_format_validation_error(settings_path, exc)) from exc

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


def _format_validation_error(
    settings_path: str | Path, exc: ValidationError
) -> str:
    """Turn a Pydantic ValidationError into a short, human-readable message.

    Args:
        settings_path: The config file that failed, for context.
        exc: The Pydantic validation error.

    Returns:
        A plain-text summary listing each problem as ``section.field: message``.
    """
    lines = [f"Config '{settings_path}' is not valid for schema "
             f"v{CURRENT_SCHEMA_VERSION}:"]
    for err in exc.errors():
        location = ".".join(str(part) for part in err["loc"]) or "<root>"
        lines.append(f"  - {location}: {err['msg']}")
    lines.append(
        "If this is an older config, migrate it first: "
        "plex_pipe.migrate_config(<path>)."
    )
    return "\n".join(lines)


def migrate_config(
    in_path: str | Path, out_path: str | Path | None = None
) -> Path | None:
    """Read an old config, migrate it to the current schema, and write it out.

    Writes the upgraded config to a **new** file by default (never overwrites
    the original unless ``out_path`` is explicitly set to the same path).

    Args:
        in_path: Path to the config file to migrate.
        out_path: Where to write the migrated config. Defaults to
            ``<stem>_v<CURRENT>.<suffix>`` next to the input.

    Returns:
        The path written, or ``None`` if the config was already current.
    """
    in_path = Path(in_path)
    with open(in_path) as file:
        raw = yaml.safe_load(file)

    migrated, start_version = migrate_to_current(raw)

    if start_version == CURRENT_SCHEMA_VERSION:
        logger.info(
            f"{in_path} is already schema v{CURRENT_SCHEMA_VERSION}; "
            f"nothing to migrate."
        )
        return None

    if out_path is None:
        out_path = in_path.with_name(
            f"{in_path.stem}_v{CURRENT_SCHEMA_VERSION}{in_path.suffix}"
        )
    out_path = Path(out_path)

    with open(out_path, "w") as file:
        yaml.safe_dump(migrated, file, sort_keys=False)

    logger.info(
        f"Migrated {in_path} (schema v{start_version} -> "
        f"v{CURRENT_SCHEMA_VERSION}) -> {out_path}"
    )
    return out_path


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
