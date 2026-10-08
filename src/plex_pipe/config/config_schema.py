from __future__ import annotations

import operator
from functools import reduce
from pathlib import Path
from typing import (
    TYPE_CHECKING,
    Annotated,
    Literal,
)

from pydantic import (
    BaseModel,
    Field,
    create_model,
    field_validator,
    model_validator,
)

from plex_pipe.config.config_migrations import CURRENT_SCHEMA_VERSION_STR
from plex_pipe.io.channel_manifest import (
    DEFAULT_EARLIEST_ROUND_MARKERS,
    DEFAULT_PRESET,
    NAMING_PRESETS,
    check_selection_rules,
)
from plex_pipe.ops.registry import REGISTRY, Kind

if TYPE_CHECKING:
    from spatialdata import SpatialData

from loguru import logger

###################################################################
# Top-Level Configuration Models
###################################################################


#: Naming presets accepted in ``channels.file_naming``, built from the registered
#: presets (``plex_pipe.io.channel_manifest.NAMING_PRESETS``), the same way
#: pipeline steps are built from the processor REGISTRY.
if TYPE_CHECKING:
    FileNamingPreset = str
else:
    FileNamingPreset = Literal[tuple(NAMING_PRESETS)]

#: Preset used when neither ``file_naming`` nor ``manifest`` is set.
DEFAULT_FILE_NAMING = DEFAULT_PRESET


def _reject_moved_keys(section: str, data: object, moved: dict[str, str]) -> None:
    """Fail clearly when a key that moved to ``channels`` is still in ``section``.

    Without this, the old key would be silently ignored (the models don't
    reject unknown keys), and e.g. an ``ignore_markers`` list would quietly
    stop working.
    """
    if not isinstance(data, dict):
        return
    found = [key for key in moved if key in data]
    if found:
        where = ", ".join(f"'{k}' -> channels: {moved[k]}" for k in found)
        raise ValueError(
            f"In schema 2.0 these settings moved from '{section}:' to the "
            f"'channels:' section: {where}. Move them in your config YAML file, "
            f"or run plex_pipe.migrate_config(<path>) on a schema-1 file."
        )


class GeneralSettings(BaseModel):
    """Configuration for general analysis settings."""

    image_dir: str
    analysis_name: str
    analysis_dir: str
    log_dir: Path | None = None

    @model_validator(mode="before")
    @classmethod
    def _no_channel_keys(cls, data: object) -> object:
        _reject_moved_keys(
            "general",
            data,
            {"file_naming": "file_naming", "channel_manifest": "manifest"},
        )
        return data


class ChannelSettings(BaseModel):
    """Which images are used, and under which marker names.

    The channel manifest (every input file with its marker and round) comes
    from exactly one of:

    * ``file_naming``: a naming preset that reads marker and round from the
      file names in ``general.image_dir`` (default ``celldive``), or
    * ``manifest``: path to a CSV listing every file with its marker and round
      (see :func:`plex_pipe.io.channel_manifest.read_manifest` for the format).

    The selection rules are then applied on top of the manifest; see
    ``docs/configuration/channel-selection.md``.
    """

    file_naming: FileNamingPreset | None = None
    manifest: str | None = None
    earliest_round_markers: list[str] = Field(
        default_factory=lambda: list(DEFAULT_EARLIEST_ROUND_MARKERS)
    )
    include_channels: list[str] = Field(default_factory=list)
    exclude_channels: list[str] = Field(default_factory=list)
    use_markers: list[str] = Field(default_factory=list)
    ignore_markers: list[str] = Field(default_factory=list)

    @field_validator("file_naming", "manifest", mode="before")
    @classmethod
    def _blank_to_none(cls, v: object) -> object:
        """Treat a blank YAML value (``key:`` or ``""``) as not set."""
        if v is None or (isinstance(v, str) and not v.strip()):
            return None
        return v

    @field_validator(
        "earliest_round_markers",
        "include_channels",
        "exclude_channels",
        "use_markers",
        "ignore_markers",
        mode="before",
    )
    @classmethod
    def _none_to_empty_list(cls, v: object) -> object:
        """Treat a blank YAML key (parsed as ``None``) as an empty list.

        Hand-authored configs commonly leave these as a bare ``key:``, which YAML
        parses to ``None``; that means the same as "no channels/markers here".
        """
        return [] if v is None else v

    @model_validator(mode="after")
    def _resolve_channel_source(self) -> ChannelSettings:
        """Require at most one channel source; default to the Cell DIVE preset.

        Raises:
            ValueError: If both ``file_naming`` and ``manifest`` are set.
        """
        if self.file_naming is not None and self.manifest is not None:
            raise ValueError(
                "Set either 'file_naming' (a naming preset) or "
                "'manifest' (a CSV path) under 'channels:', not both. "
                f"Got file_naming={self.file_naming!r}, "
                f"manifest={self.manifest!r}."
            )
        if self.manifest is None and self.file_naming is None:
            self.file_naming = DEFAULT_FILE_NAMING
        return self

    @model_validator(mode="after")
    def _no_contradicting_rules(self) -> ChannelSettings:
        """Reject selection settings that ask for and reject the same thing.

        Raises:
            ValueError: See :func:`plex_pipe.io.channel_manifest.check_selection_rules`.
        """
        check_selection_rules(
            self.include_channels,
            self.exclude_channels,
            self.use_markers,
            self.ignore_markers,
        )
        return self


class RoiDefinitionSettings(BaseModel):
    """Configuration for ROI definition."""

    detection_image: str
    roi_info_file_path: str | None = None
    im_level: float | None = None


class RoiCuttingSettings(BaseModel):
    """Configuration for ROI cutting and processing."""

    roi_dir_tif: str | None = None
    roi_dir_output: str | None = None
    margin: int | None = 0
    mask_value: int | None = 0
    transfer_cleanup_enabled: bool | None = False
    roi_cleanup_enabled: bool | None = False

    @model_validator(mode="before")
    @classmethod
    def _no_channel_keys(cls, data: object) -> object:
        _reject_moved_keys(
            "roi_cutting",
            data,
            {
                key: key
                for key in (
                    "include_channels",
                    "exclude_channels",
                    "use_markers",
                    "ignore_markers",
                    "earliest_round_markers",
                )
            },
        )
        return data


class QcSettings(BaseModel):
    """Configuration for Quality Control settings."""

    prefix: str


DEFAULT_morphological_properties = [
    "label",
    "centroid",
    "area",
    "eccentricity",
    "solidity",
    "perimeter",
    "euler_number",
]

DEFAULT_intensity_properties = ["mean", "median"]


class QuantTask(BaseModel):
    """Configuration for a quantification task."""

    name: str
    masks: dict[str, str]
    layer_connection: str | None = None
    morphological_properties: list[str] = DEFAULT_morphological_properties
    intensity_properties: list[str] = DEFAULT_intensity_properties
    markers_to_quantify: list[str] | None = None
    qc_to_table: bool = False

    @field_validator("morphological_properties")
    @classmethod
    def ensure_label_in_features(cls, v: list[str]) -> list[str]:
        """Ensures that 'label' is included in morphological properties.

        Args:
            v: List of morphological properties.

        Returns:
            The list with 'label' included.
        """
        if "label" not in v:
            v.append("label")
        return v


class StorageSettings(BaseModel):
    """Configuration for storage settings."""

    chunk_size: list[int] | None = [1, 512, 512]
    max_pyramid_level: int | None = 4
    downscale: int | None = 2


###################################################################
# Pipeline Step Models (for 'additional_elements')
###################################################################
class BaseStep(BaseModel):
    """Base configuration for a pipeline step."""

    category: Kind
    type: str
    input: str | list[str]
    output: str | list[str]
    keep: bool = True


def create_step_models() -> list[type[BaseModel]]:
    """Dynamically creates Pydantic models for each registered processor.

    Returns:
        A list of dynamically created Pydantic models representing pipeline steps.
    """
    all_step_models = []
    for kind, processors in REGISTRY.items():
        for name, entry in processors.items():
            # 3. Create a unique model for each specific step, e.g., "RingStep"
            model_name = f"{name.capitalize()}Step"

            step_model = create_model(
                model_name,
                # It must have this specific category and type
                category=(Literal[kind], ...),
                type=(Literal[name], ...),
                # Its parameters must match the processor's Params model
                parameters=(entry.param_model, Field(default={})),
                # It inherits the common fields from BaseStep
                __base__=BaseStep,
            )
            all_step_models.append(step_model)
    return all_step_models


# 4. PipelineStep is a Union of all dynamically generated models
if TYPE_CHECKING:
    PipelineStep = BaseStep
else:
    step_models = create_step_models()
    PipelineStep = BaseStep if not step_models else reduce(operator.or_, step_models)


class AnalysisConfig(BaseModel):
    """The root model for the entire plex_pipe analysis configuration.

    This class acts as the main entry point for parsing and validating the
    complete YAML configuration file. ``schema_version`` is ``"MAJOR.MINOR"``
    (see ``config_migrations.py``); the loader migrates older files so that its
    MAJOR equals the current one before this model is validated.
    """

    schema_version: str = CURRENT_SCHEMA_VERSION_STR
    general: GeneralSettings
    channels: ChannelSettings = Field(default_factory=ChannelSettings)
    roi_definition: RoiDefinitionSettings
    roi_cutting: RoiCuttingSettings
    additional_elements: list[Annotated[PipelineStep, Field(discriminator="type")]]
    qc: QcSettings
    quant: list[QuantTask]
    sdata_storage: StorageSettings

    analysis_dir: Path = Path(".")
    temp_dir: Path = Path(".")
    log_dir_path: Path = Path(".")
    roi_info_file_path: Path = Path(".")
    roi_dir_tif_path: Path = Path(".")
    roi_dir_output_path: Path = Path(".")

    @field_validator("channels", mode="before")
    @classmethod
    def _blank_channels_section(cls, v: object) -> object:
        """A bare ``channels:`` in YAML (``None``) means all defaults."""
        return {} if v is None else v

    @model_validator(mode="after")
    def _resolve_paths(self) -> AnalysisConfig:
        """Resolves paths and sets default values based on the analysis directory.

        Returns:
            The updated configuration object with resolved paths.
        """
        base_dir_str = self.general.analysis_dir
        analysis_dir = Path(base_dir_str) / self.general.analysis_name
        self.analysis_dir = analysis_dir

        # Define defaults
        defaults = {
            "log_dir": analysis_dir / "logs",
            "roi_info_file_path": analysis_dir / "rois.pkl",
            "roi_dir_tif": analysis_dir / "temp",
            "roi_dir_output": analysis_dir / "rois",
            "temp_dir": analysis_dir / "temp",
        }

        # Populate final Path objects
        self.log_dir_path = Path(self.general.log_dir or defaults["log_dir"])

        self.roi_info_file_path = Path(
            self.roi_definition.roi_info_file_path or defaults["roi_info_file_path"]
        )

        self.roi_dir_tif_path = Path(
            self.roi_cutting.roi_dir_tif or defaults["roi_dir_tif"]
        )

        self.roi_dir_output_path = Path(
            self.roi_cutting.roi_dir_output or defaults["roi_dir_output"]
        )

        self.temp_dir = defaults["temp_dir"]

        return self

    def validate_pipeline(self, sdata: SpatialData) -> None:
        """Validates the pipeline's data flow against a SpatialData object.

        This method checks that for every step:
        1. All required inputs exist.
        2. Inputs can be from the initial SpatialData object or outputs of prior steps.

        Args:
            sdata: The SpatialData object to validate against.

        Raises:
            ValueError: If an input is not found at any stage.
        """
        # Start with the set of layers available in the initial sdata object.
        available_layers = set(sdata.images) | set(sdata.labels)

        for i, step in enumerate(self.additional_elements):
            # Normalize step inputs to a list for consistent processing
            inputs = [step.input] if isinstance(step.input, str) else step.input

            # Check if all inputs for the current step are available
            for required_input in inputs:
                if required_input not in available_layers:
                    msg = f"Pipeline validation failed at step {i} ('{step.type}'):\n \
                        Input '{required_input}' not found.\n \
                        Available layers: {sorted(available_layers)}"
                    logger.error(msg)
                    raise ValueError(msg)

            # Add the outputs of the current step to the set of available layers
            outputs = [step.output] if isinstance(step.output, str) else step.output
            available_layers.update(outputs)

        # If the loop completes without errors, the pipeline is valid.
        logger.info("✅ Pipeline validation successful.")
