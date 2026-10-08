"""Schema versioning and migration for ``AnalysisConfig`` YAML files.

``schema_version`` is written as ``"MAJOR.MINOR"`` (e.g. ``"2.0"``; quote it in
YAML so ``2.10`` is not read as the number 2.1). It is *independent of the
plex_pipe package version*:

* **MAJOR** changes when the config-file format changes in a way that would
  stop an older file from loading (keys moved, renamed or removed). Each MAJOR
  step has a migration.
* **MINOR** changes when optional keys are added. Older files still load
  unchanged; the MINOR number lets an *older* plex_pipe warn that a newer
  config may contain settings it does not know (and would ignore).

A config with **no** ``schema_version`` key is treated as version 0.0
(``LEGACY_VERSION``, the pre-versioning format). A bare integer, as written
by schema 1 (``schema_version: 1``), is read as ``1.0``.

Migrations are ``dict -> dict`` transforms applied to the raw parsed YAML
**before** Pydantic validation, because an old file will not validate against
the current model. Each migration converts MAJOR ``N`` to ``N + 1``;
:func:`migrate_to_current` composes the chain to bring any older file up to
:data:`CURRENT_SCHEMA_VERSION` (e.g. 0 -> 2 runs v0->v1 then v1->v2).

Changing the config format (the contributor rule):

* Breaking change: bump the MAJOR of :data:`CURRENT_SCHEMA_VERSION` (MINOR back
  to 0), write ``migrate_v{N}_to_v{N+1}(raw)``, register it in
  :data:`MIGRATIONS`, and add a test with a fixture config at the old version.
* New optional key with a default: bump the MINOR only; no migration needed.
* Either way: add an entry to ``docs/configuration/schema_changelog.md`` and
  update ``schema_version`` in the example configs.
"""

from __future__ import annotations

import copy
import re
from collections.abc import Callable

from loguru import logger

#: Version as a ``(major, minor)`` pair.
SchemaVersion = tuple[int, int]

#: The schema version this build of plex_pipe reads/writes.
CURRENT_SCHEMA_VERSION: SchemaVersion = (2, 0)

#: The implicit version of a config that has no ``schema_version`` key.
LEGACY_VERSION: SchemaVersion = (0, 0)

_VERSION_RE = re.compile(r"^(\d+)(?:\.(\d+))?$")


def format_version(version: SchemaVersion) -> str:
    """Format a ``(major, minor)`` pair as written in YAML, e.g. ``"2.0"``."""
    return f"{version[0]}.{version[1]}"


#: :data:`CURRENT_SCHEMA_VERSION` as written in YAML, e.g. ``"2.0"``.
CURRENT_SCHEMA_VERSION_STR = format_version(CURRENT_SCHEMA_VERSION)


def parse_version(value: object) -> SchemaVersion:
    """Parse a ``schema_version`` value into ``(major, minor)``.

    Accepts ``"2.0"`` (preferred), ``"2"``, the integer ``1`` written by
    schema 1, and an unquoted YAML number such as ``2.0``.

    Raises:
        ValueError: If the value is not a ``MAJOR.MINOR`` version.
    """
    if isinstance(value, bool):
        match = None
    elif isinstance(value, int):
        match = _VERSION_RE.match(str(value))
    elif isinstance(value, float):
        match = _VERSION_RE.match(repr(value))
    elif isinstance(value, str):
        match = _VERSION_RE.match(value.strip())
    else:
        match = None
    if match is None:
        raise ValueError(
            f"`schema_version` must be \"MAJOR.MINOR\" (e.g. "
            f"\"{CURRENT_SCHEMA_VERSION_STR}\"), got {value!r} "
            f"({type(value).__name__})."
        )
    return int(match[1]), int(match[2] or 0)


def _detect_version(raw: dict) -> SchemaVersion:
    """Read ``schema_version`` from a raw config dict as ``(major, minor)``.

    A missing key means :data:`LEGACY_VERSION` (0.0). Kept as a single helper
    so version parsing lives in one place.

    Args:
        raw: The raw config dictionary (parsed YAML).

    Returns:
        The schema version as ``(major, minor)``.

    Raises:
        ValueError: If ``schema_version`` is present but not a valid version.
    """
    if "schema_version" not in raw:
        return LEGACY_VERSION
    return parse_version(raw["schema_version"])


def needs_migration(version: SchemaVersion) -> bool:
    """Return True if a config at ``version`` is an older MAJOR than current."""
    return version[0] < CURRENT_SCHEMA_VERSION[0]


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


# Channel selection settings that moved from ``roi_cutting`` to ``channels``
# in schema 2.0.
_CHANNEL_SELECTION_FIELDS = (
    "include_channels",
    "exclude_channels",
    "use_markers",
    "ignore_markers",
    "earliest_round_markers",
)


def migrate_v1_to_v2(raw: dict) -> dict:
    """Migrate a schema-1 config to schema 2.0.

    Schema 2.0 groups everything about which images are used, and under which
    marker names, in a new top-level ``channels`` section:

    * ``roi_cutting`` -> ``channels``: ``include_channels``,
      ``exclude_channels``, ``use_markers``, ``ignore_markers`` (and
      ``earliest_round_markers`` if present).
    * ``general`` -> ``channels``: ``file_naming`` (if present);
      ``channel_manifest`` -> ``manifest`` (if present).

    The new section is placed right after ``general``. Written defensively: a
    key already present in ``channels`` is kept, and running this on
    2.0-shaped input is a safe no-op.

    Args:
        raw: The raw schema-1 config dictionary (mutated and returned).

    Returns:
        The upgraded dictionary, stamped with ``schema_version = "2.0"``.
    """
    channels = raw.get("channels")
    if not isinstance(channels, dict):
        channels = {}

    roi_cut = raw.get("roi_cutting")
    if isinstance(roi_cut, dict):
        for field in _CHANNEL_SELECTION_FIELDS:
            if field in roi_cut:
                value = roi_cut.pop(field)
                channels.setdefault(field, value)

    general = raw.get("general")
    if isinstance(general, dict):
        if "file_naming" in general:
            channels.setdefault("file_naming", general.pop("file_naming"))
        if "channel_manifest" in general:
            channels.setdefault("manifest", general.pop("channel_manifest"))

    if channels:
        # rebuild so that `channels` sits right after `general` when written out
        reordered: dict = {}
        for key, value in raw.items():
            if key == "channels":
                continue
            reordered[key] = value
            if key == "general":
                reordered["channels"] = channels
        if "channels" not in reordered:
            reordered["channels"] = channels
        raw.clear()
        raw.update(reordered)

    raw["schema_version"] = "2.0"
    return raw


#: Migration functions keyed by the MAJOR version they migrate *from*.
MIGRATIONS: dict[int, Callable[[dict], dict]] = {
    0: migrate_v0_to_v1,
    1: migrate_v1_to_v2,
}


def migrate_to_current(raw: dict) -> tuple[dict, SchemaVersion]:
    """Bring a raw config dict up to :data:`CURRENT_SCHEMA_VERSION`.

    Applies the registered migrations in sequence (v0->v1->v2->...) until the
    config reaches the current MAJOR version. Operates on a deep copy, so the
    caller's dict is never mutated. The returned dict always carries
    ``schema_version`` as a ``"MAJOR.MINOR"`` string.

    A config with the current MAJOR but a newer MINOR loads with a warning: it
    may contain optional settings this build does not know, which would be
    ignored.

    Args:
        raw: The raw config dictionary (parsed YAML).

    Returns:
        A tuple ``(migrated_dict, start_version)`` where ``start_version`` is the
        ``(major, minor)`` the config was at before migration.

    Raises:
        ValueError: If the config is a newer MAJOR than this build understands,
            or if a migration step is missing or misbehaves.
    """
    raw = copy.deepcopy(raw)
    start_version = _detect_version(raw)
    current_major = CURRENT_SCHEMA_VERSION[0]

    if start_version[0] > current_major:
        raise ValueError(
            f"This config is schema {format_version(start_version)}, but this "
            f"build of plex_pipe understands only up to "
            f"{CURRENT_SCHEMA_VERSION_STR}. Upgrade plex_pipe to read it."
        )

    version = start_version
    while version[0] < current_major:
        migrate = MIGRATIONS.get(version[0])
        if migrate is None:
            raise ValueError(
                f"No migration registered from schema {version[0]} to "
                f"{version[0] + 1}. This is a plex_pipe bug — please report it."
            )
        raw = migrate(raw)
        new_version = _detect_version(raw)
        if new_version[0] != version[0] + 1:
            raise ValueError(
                f"Migration from schema {format_version(version)} left "
                f"schema_version={format_version(new_version)} "
                f"(expected {version[0] + 1}.x)."
            )
        version = new_version

    if version[0] == current_major and version[1] > CURRENT_SCHEMA_VERSION[1]:
        logger.warning(
            f"This config is schema {format_version(version)}, newer than this "
            f"build of plex_pipe ({CURRENT_SCHEMA_VERSION_STR}). It may contain "
            f"settings this build does not know, which would be ignored. "
            f"Consider upgrading plex_pipe."
        )

    # canonical form for the model (e.g. an unquoted YAML 2.0 becomes "2.0")
    raw["schema_version"] = format_version(version)

    if needs_migration(start_version):
        logger.info(
            f"Config migrated in memory: schema {format_version(start_version)} "
            f"-> {CURRENT_SCHEMA_VERSION_STR}. To upgrade the file on disk, run "
            f"plex_pipe.migrate_config(<path>)."
        )
    return raw, start_version
