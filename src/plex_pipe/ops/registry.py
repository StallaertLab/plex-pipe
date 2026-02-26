from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Literal

from pydantic import BaseModel

from plex_pipe.ops.base import BaseOp


@dataclass
class RegistryEntry:
    """Stores a processor class and its configuration model.

    Attributes:
        processor_class: The class implementing the processor logic.
        param_model: The Pydantic model defining the processor's parameters.
    """

    processor_class: type[BaseOp]
    param_model: type[BaseModel]


Kind = Literal[
    "mask_builder",
    "object_segmenter",
    "image_enhancer",
]

REGISTRY: dict[Kind, dict[str, RegistryEntry]] = {
    "mask_builder": {},
    "object_segmenter": {},
    "image_enhancer": {},
}


def register(kind: Kind, name: str) -> Callable[[type[BaseOp]], type[BaseOp]]:
    """Registers a processor class under a specific kind and name.

    Args:
        kind: The category of the processor (e.g., 'mask_builder').
        name: The unique name for the processor within its category.

    Returns:
        A decorator that registers the class and returns it unmodified.
    """

    def deco(cls: type[BaseOp]) -> type[BaseOp]:
        # Get the parameter model from the class, defaulting to an empty one
        param_model = getattr(cls, "Params", BaseModel)

        # Create and store the complete registry entry
        REGISTRY[kind][name] = RegistryEntry(
            processor_class=cls, param_model=param_model
        )
        cls.kind = kind
        cls.type_name = name
        return cls

    return deco


def build_processor(kind: Kind, name: str, **cfg: Any) -> BaseOp:
    """Instantiates a processor by its registered kind and name.

    Args:
        kind: The category of the processor.
        name: The name of the processor.
        **cfg: Configuration keyword arguments passed to the processor's constructor.

    Returns:
        An instance of the requested processor.

    Raises:
        ValueError: If the kind or name is not registered.
    """
    if kind not in REGISTRY:
        available_kinds = ", ".join(sorted(REGISTRY))
        raise ValueError(
            f"Unknown kind '{kind}'. Available kinds: {available_kinds or '(none)'}"
        )

    registry_for_kind = REGISTRY[kind]
    if name not in registry_for_kind:
        available_names = ", ".join(sorted(registry_for_kind))
        raise ValueError(
            f"Unknown {kind} '{name}'. Available: {available_names or '(none)'}"
        )

    cls = registry_for_kind[name].processor_class
    obj = cls(**cfg)

    return obj
