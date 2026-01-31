import numpy as np
from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List, Dict
from datetime import datetime

from .object import Object

class Frame(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    
    # --- Identity ---
    frame_id: int = Field(..., description="Unique frame identifier")

    # --- Visual ---
    image: np.ndarray = Field(..., description="Frame image")

    # --- Temporal ---
    timestamp_sec: float = Field(
        ...,
        description="Seconds since start of video (relative time)",
        ge=0.0,
    )
    captured_at: datetime = Field(
        ...,
        description="Absolute timestamp when frame was captured (wall-clock time)",
    )

    # --- Visual Semantics ---
    caption: Optional[str] = Field(
        None, description="BLIP-generated caption"
    )
    is_novel: Optional[bool] = Field(
        None, description="Whether this frame is novel"
    )

    # --- Object References ---
    objects: List[Object] = Field(
        default_factory=list,
        description="Objects present in this frame"
    )

    attributes: Optional[Dict[str, str]] = Field(
        None, description="Attributes of the frame"
    )

    @property
    def num_objects(self) -> int:
        return len(self.objects)

    @property
    def contains_objects(self) -> bool:
        return len(self.objects) > 0