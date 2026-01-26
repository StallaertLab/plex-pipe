from __future__ import annotations

from pathlib import Path
from typing import (
    TYPE_CHECKING,
    Annotated,
    Dict,
    List,
    Literal,
    Optional,
    Type,
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
    log_dir: Optional[Path] = None


class SamSettings(BaseModel):
    im_level: int
    min_area: int
    max_area: int
    min_iou: float
    min_st: float
    min_int: int
    frame: int


class CoreDetectionSettings(BaseModel):
    detection_image: str
    core_info_file_path: Optional[str] = None
    # If 'sam' is missing, it defaults to None.
    # If 'sam' is provided, it must match the SamSettings schema.
    sam: Optional[SamSettings] = None


class CoreCuttingSettings(BaseModel):
    cores_dir_tif: Optional[str] = None
    cores_dir_output: Optional[str] = None
    include_channels: Optional[Union[str, List[str]]] = None
    exclude_channels: Optional[Union[str, List[str]]] = None
    use_markers: Optional[Union[str, List[str]]] = None
    ignore_markers: Optional[Union[str, List[str]]] = None
    margin: Optional[int] = 0
    mask_value: Optional[int] = 0
    transfer_cleanup_enabled: Optional[bool] = False
    core_cleanup_enabled: Optional[bool] = False


class QcSettings(BaseModel):
    prefix: str


DEFAULT_MORPHOLOGICAL_FEATURES = [
    "label",
    "area",
    "eccentricity",
    "solidity",
    "perimeter",
    "centroid",
    "euler_number",
]

DEFAULT_INTENSITY_METRICS = ["mean", "median"]


class QuantTask(BaseModel):
    name: str
    masks: Dict[str, str]
    layer_connection: str | None = None
    morphological_features: List[str] = DEFAULT_MORPHOLOGICAL_FEATURES
    intensity_metrics: List[str] = DEFAULT_INTENSITY_METRICS

    @field_validator("morphological_features")
    @classmethod
    def ensure_label_in_features(cls, v: List[str]) -> List[str]:
        if "label" not in v:
            v.append("label")
        return v


class StorageSettings(BaseModel):
    chunk_size: Optional[List[int]] = [1, 512, 512]
    max_pyramid_level: Optional[int] = 4
    downscale: Optional[int] = 2


###################################################################
# Pipeline Step Models (for 'additional_elements')
###################################################################
class BaseStep(BaseModel):
    category: Kind
    type: str
    input: Union[str, List[str]]
    output: Union[str, List[str]]
    keep: bool = True


def create_step_models() -> list[Type[BaseModel]]:
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
    core_detection: CoreDetectionSettings
    core_cutting: CoreCuttingSettings
    additional_elements: List[Annotated[PipelineStep, Field(discriminator="type")]]
    qc: QcSettings
    quant: List[QuantTask]
    sdata_storage: StorageSettings

    analysis_dir: Path = Path(".")
    temp_dir: Path = Path(".")
    log_dir_path: Path = Path(".")
    core_info_file_path: Path = Path(".")
    cores_dir_tif_path: Path = Path(".")
    cores_dir_output_path: Path = Path(".")

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
            "core_info_file_path": analysis_dir / "cores.csv",
            "cores_dir_tif": analysis_dir / "temp",
            "cores_dir_output": analysis_dir / "cores",
            "temp_dir": analysis_dir / "temp",
        }

        # Populate final Path objects
        self.log_dir_path = Path(self.general.log_dir or defaults["log_dir"])

        self.core_info_file_path = Path(
            self.core_detection.core_info_file_path or defaults["core_info_file_path"]
        )

        self.cores_dir_tif_path = Path(
            self.core_cutting.cores_dir_tif or defaults["cores_dir_tif"]
        )

        self.cores_dir_output_path = Path(
            self.core_cutting.cores_dir_output or defaults["cores_dir_output"]
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
