from __future__ import annotations

from pathlib import Path
from typing import (
    TYPE_CHECKING,
    Annotated,
    Literal,
    Union,
)

from pydantic import (
    BaseModel,
    Field,
    create_model,
    field_validator,
    model_validator,
)

from plex_pipe.processors.registry import REGISTRY, Kind

if TYPE_CHECKING:
    from spatialdata import SpatialData

from loguru import logger

###################################################################
# Top-Level Configuration Models
###################################################################


class GeneralSettings(BaseModel):
    image_dir: str
    analysis_name: str
    analysis_dir: str
    log_dir: Path | None = None


class RoiDefinitionSettings(BaseModel):
    detection_image: str
    roi_info_file_path: str | None = None
    im_level: float | None = None


class RoiCuttingSettings(BaseModel):
    roi_dir_tif: str | None = None
    roi_dir_output: str | None = None
    include_channels: str | list[str] | None = None
    exclude_channels: str | list[str] | None = None
    use_markers: str | list[str] | None = None
    ignore_markers: str | list[str] | None = None
    margin: int | None = 0
    mask_value: int | None = 0
    transfer_cleanup_enabled: bool | None = False
    roi_cleanup_enabled: bool | None = False


class QcSettings(BaseModel):
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
    name: str
    masks: dict[str, str]
    layer_connection: str | None = None
    morphological_properties: list[str] = DEFAULT_morphological_properties
    intensity_properties: list[str] = DEFAULT_intensity_properties
    markers_to_quantify: list[str] | None = None
    add_qc_masks: bool = False

    @field_validator("morphological_properties")
    @classmethod
    def ensure_label_in_features(cls, v: list[str]) -> list[str]:
        if "label" not in v:
            v.append("label")
        return v


class StorageSettings(BaseModel):
    chunk_size: list[int] | None = [1, 512, 512]
    max_pyramid_level: int | None = 4
    downscale: int | None = 2


###################################################################
# Pipeline Step Models (for 'additional_elements')
###################################################################
class BaseStep(BaseModel):
    category: Kind
    type: str
    input: str | list[str]
    output: str | list[str]
    keep: bool = True


def create_step_models() -> list[type[BaseModel]]:
    """Dynamically creates Pydantic models for each registered processor."""
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
step_models = create_step_models()
PipelineStep = BaseStep if not step_models else Union[*step_models]


class AnalysisConfig(BaseModel):
    """The root model for the entire Track Gardener configuration.

    This class acts as the main entry point for parsing and validating the
    complete YAML configuration file.
    """

    general: GeneralSettings
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

    @model_validator(mode="after")
    def _resolve_paths(self) -> AnalysisConfig:
        """
        This validator resolves paths and sets defaults.
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
        """
        Validates the pipeline's data flow against a SpatialData object.

        This method checks that for every step:
        1. All required inputs exist.
        2. Inputs can be from the initial SpatialData object or outputs of prior steps.

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
