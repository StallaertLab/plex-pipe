"""Schema versioning and migration for ``AnalysisConfig`` YAML files.

``schema_version`` is a **migration-generation counter**: a plain integer that
is *independent of the plex_pipe package version*. It increments by one only
when the config-file format changes in a way that would stop an older file from
loading. A config with **no** ``schema_version`` key is treated as version 0
(``LEGACY_VERSION`` — the pre-versioning format).

Migrations are ``dict -> dict`` transforms applied to the raw parsed YAML
**before** Pydantic validation, because an old file will not validate against
the current model. Each migration converts version ``N`` to ``N + 1``;
:func:`migrate_to_current` composes the chain to bring any older file up to
:data:`CURRENT_SCHEMA_VERSION` (e.g. v0 -> v2 runs v0->v1 then v1->v2).

Adding a new schema version (the contributor rule):

1. bump :data:`CURRENT_SCHEMA_VERSION`;
2. write ``migrate_v{N}_to_v{N+1}(raw)`` and register it in :data:`MIGRATIONS`;
3. add a test with a fixture config at the old version.
"""

from __future__ import annotations

import copy
from collections.abc import Callable

from loguru import logger

#: The schema version this build of plex_pipe reads/writes.
CURRENT_SCHEMA_VERSION = 1

#: The implicit version of a config that has no ``schema_version`` key.
LEGACY_VERSION = 0


def _detect_version(raw: dict) -> int:
    """Read the integer ``schema_version`` from a raw config dict.

    A missing key means :data:`LEGACY_VERSION` (0). Kept as a single helper so the
    comparison logic lives in one place: the only place that would need to change
    if the versioning scheme ever moved away from plain integers.

    Args:
        raw: The raw config dictionary (parsed YAML).

    Returns:
        The schema version as an integer.

    Raises:
        ValueError: If ``schema_version`` is present but not an integer.
    """
    version = raw.get("schema_version", LEGACY_VERSION)
    if not isinstance(version, int) or isinstance(version, bool):
        raise ValueError(
            f"`schema_version` must be an integer, got {version!r} "
            f"({type(version).__name__}). Schema versions are plain "
            f"incrementing integers (1, 2, 3, ...)."
        )
    return version


def needs_migration(version: int) -> bool:
    """Return True if a config at ``version`` is behind the current schema."""
    return version < CURRENT_SCHEMA_VERSION


# Legacy category names for the image-enhancement step, unified to the current
# ``image_enhancer`` on migration.
_LEGACY_ENHANCER_CATEGORIES = ("image_filter", "image_transformer")

# SAM2-only fields in the legacy ``core_detection`` section that have no home in
# the current ``roi_definition`` schema (SAM2 core detection is now a separate,
# optional step). They are dropped on migration.
_LEGACY_SAM_FIELDS = (
    "min_area",
    "max_area",
    "min_iou",
    "min_st",
    "min_int",
    "frame",
)

# Channel/marker list fields in roi_cutting that a legacy config may leave blank
# (a bare ``key:`` parses to ``None``); normalized to ``[]`` so persisted
# migrated files are clean. (The schema also coerces None->[] at load time.)
_ROI_CUTTING_LIST_FIELDS = (
    "include_channels",
    "exclude_channels",
    "use_markers",
    "ignore_markers",
)


def _rename_key(d: dict, old: str, new: str) -> None:
    """Rename ``d[old]`` to ``d[new]`` in place, only if safe.

    A no-op if ``old`` is absent or ``new`` already exists (so it is safe to run
    on an already-migrated dict).
    """
    if old in d and new not in d:
        d[new] = d.pop(old)


def migrate_v0_to_v1(raw: dict) -> dict:
    """Migrate a legacy (unversioned) config to schema v1.

    Structural changes from the pre-versioning format, verified against a real
    legacy config (``tests/example_data/legacy_config_v0.yaml``):

    * ``general``: ``local_analysis_dir`` -> ``analysis_dir``;
      ``remote_analysis_dir`` is dropped (it now belongs in the Globus config).
    * section ``core_detection`` -> ``roi_definition``; ``core_info_file_path``
      -> ``roi_info_file_path``; the SAM2-only fields (:data:`_LEGACY_SAM_FIELDS`)
      are dropped.
    * section ``core_cutting`` -> ``roi_cutting``; ``cores_dir_tif`` ->
      ``roi_dir_tif``; ``cores_dir_output`` -> ``roi_dir_output``;
      ``core_cleanup_enabled`` -> ``roi_cleanup_enabled``; blank channel/marker
      lists (``None``) -> ``[]``.
    * ``additional_elements``: category ``image_filter``/``image_transformer``
      -> ``image_enhancer``; ring-builder params ``outer``/``inner`` ->
      ``rad_bigger``/``rad_smaller``.
    * ``quant``: ``qc_to_layer`` -> ``qc_to_table``.

    Dropped fields (``remote_analysis_dir``, the SAM2 params) are logged at
    WARNING level so nothing disappears silently. Written defensively: every
    rename is skipped when the target already exists, so running this on
    already-v1-shaped input is a safe no-op.

    Args:
        raw: The raw legacy config dictionary (mutated in place and returned).

    Returns:
        The upgraded dictionary, stamped with ``schema_version = 1``.
    """
    dropped: list[str] = []

    # general: collapse local/remote analysis dirs into a single analysis_dir.
    general = raw.get("general")
    if isinstance(general, dict):
        if "analysis_dir" not in general and "local_analysis_dir" in general:
            general["analysis_dir"] = general["local_analysis_dir"]
        if "remote_analysis_dir" in general:
            dropped.append(
                f"general.remote_analysis_dir="
                f"{general['remote_analysis_dir']!r} "
                f"(put it in the Globus config if still needed)"
            )
        general.pop("local_analysis_dir", None)
        general.pop("remote_analysis_dir", None)

    # core_detection -> roi_definition (+ field rename, drop SAM2 fields).
    if "core_detection" in raw and "roi_definition" not in raw:
        raw["roi_definition"] = raw.pop("core_detection")
    roi_def = raw.get("roi_definition")
    if isinstance(roi_def, dict):
        _rename_key(roi_def, "core_info_file_path", "roi_info_file_path")
        for field in _LEGACY_SAM_FIELDS:
            if field in roi_def:
                dropped.append(f"roi_definition.{field}={roi_def[field]!r}")
                roi_def.pop(field)

    # core_cutting -> roi_cutting (+ field renames).
    if "core_cutting" in raw and "roi_cutting" not in raw:
        raw["roi_cutting"] = raw.pop("core_cutting")
    roi_cut = raw.get("roi_cutting")
    if isinstance(roi_cut, dict):
        _rename_key(roi_cut, "cores_dir_tif", "roi_dir_tif")
        _rename_key(roi_cut, "cores_dir_output", "roi_dir_output")
        _rename_key(roi_cut, "core_cleanup_enabled", "roi_cleanup_enabled")
        # Blank channel/marker lists (bare `key:` -> None) become [].
        for list_field in _ROI_CUTTING_LIST_FIELDS:
            if list_field in roi_cut and roi_cut[list_field] is None:
                roi_cut[list_field] = []

    # additional_elements: category rename + ring-builder param rename.
    for step in raw.get("additional_elements") or []:
        if not isinstance(step, dict):
            continue
        if step.get("category") in _LEGACY_ENHANCER_CATEGORIES:
            step["category"] = "image_enhancer"
        if step.get("category") == "mask_builder" and step.get("type") == "ring":
            params = step.get("parameters")
            if isinstance(params, dict):
                _rename_key(params, "outer", "rad_bigger")
                _rename_key(params, "inner", "rad_smaller")

    # quant: qc_to_layer -> qc_to_table.
    for task in raw.get("quant") or []:
        if isinstance(task, dict):
            _rename_key(task, "qc_to_layer", "qc_to_table")

    if dropped:
        logger.warning(
            "Schema v0->v1 migration dropped fields with no place in the "
            "current schema: " + "; ".join(dropped)
        )

    raw["schema_version"] = 1
    return raw


#: Migration functions keyed by the version they migrate *from*.
#: Add ``1: migrate_v1_to_v2`` here when a v2 schema is introduced.
MIGRATIONS: dict[int, Callable[[dict], dict]] = {
    0: migrate_v0_to_v1,
}


def migrate_to_current(raw: dict) -> tuple[dict, int]:
    """Bring a raw config dict up to :data:`CURRENT_SCHEMA_VERSION`.

    Applies the registered migrations in sequence (v0->v1->v2->...) until the
    config reaches the current version. Operates on a deep copy, so the caller's
    dict is never mutated.

    Args:
        raw: The raw config dictionary (parsed YAML).

    Returns:
        A tuple ``(migrated_dict, start_version)`` where ``start_version`` is the
        version the config was at before migration.

    Raises:
        ValueError: If the config is newer than this build understands, or if a
            migration step is missing or misbehaves.
    """
    raw = copy.deepcopy(raw)
    start_version = _detect_version(raw)

    if start_version > CURRENT_SCHEMA_VERSION:
        raise ValueError(
            f"This config is schema v{start_version}, but this build of "
            f"plex_pipe understands only up to v{CURRENT_SCHEMA_VERSION}. "
            f"Upgrade plex_pipe to read it."
        )

    version = start_version
    while version < CURRENT_SCHEMA_VERSION:
        migrate = MIGRATIONS.get(version)
        if migrate is None:
            raise ValueError(
                f"No migration registered from schema v{version} to "
                f"v{version + 1}. This is a plex_pipe bug — please report it."
            )
        raw = migrate(raw)
        new_version = _detect_version(raw)
        if new_version != version + 1:
            raise ValueError(
                f"Migration from schema v{version} left schema_version="
                f"{new_version} (expected {version + 1})."
            )
        version = new_version

    if start_version < CURRENT_SCHEMA_VERSION:
        logger.info(
            f"Config migrated in memory: schema v{start_version} -> "
            f"v{CURRENT_SCHEMA_VERSION}. To upgrade the file on disk, run "
            f"plex_pipe.migrate_config(<path>)."
        )
    return raw, start_version
