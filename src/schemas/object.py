import numpy as np
from pydantic import BaseModel, Field
from typing import Optional, List, Dict

from .bounding_box import BoundingBox

class ContextualCaption(BaseModel):
    frame_id: int
    timestamp_sec: float
    caption: str

class Object(BaseModel):
    # --- Identity ---
    object_id: Optional[int] = Field(
        None, description="Tracker ID (ByteTrack)"
    )
    label: str = Field(
        ..., description="Object class label (person, vehicle, bag, etc.)"
    )

    # --- Temporal Lifecycle ---
    first_timestamp_sec: Optional[float] = None
    last_timestamp_sec: Optional[float] = None

    # --- Spatial Trajectory ---
    bounding_boxes: Dict[int, BoundingBox] = Field(
        default_factory=dict,
        description="BBox per frame"
    )

    # --- Visual Semantics ---
    contextual_captions: List[ContextualCaption] = Field(
        default_factory=list,
        description="Contextual captions across frames"
    )

    # --- Behavior Analysis ---
    suspicious_activity: List[str] = Field(
        default_factory=list,
        description="Detected security-relevant behaviors"
    )

    @property
    def duration(self) -> float:
        """Total time object was visible (seconds)."""
        if not self.first_timestamp_sec or not self.last_timestamp_sec:
            return 0.0
        return self.last_timestamp_sec - self.first_timestamp_sec

    @property
    def first_frame_id(self) -> int:
        return min(self.bounding_boxes.keys())
    
    @property
    def last_frame_id(self) -> int:
        return max(self.bounding_boxes.keys())

    @property
    def total_displacement(self) -> float:
        """Total distance traveled (pixels)."""
        if len(self.bounding_boxes) < 2:
            return 0.0
        total = 0.0
        for bbox1, bbox2 in zip(self.bounding_boxes.values()[:-1], self.bounding_boxes.values()[1:]):
            total += np.linalg.norm(np.array(bbox2.center) - np.array(bbox1.center))
        return total