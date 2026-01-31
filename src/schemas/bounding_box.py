from typing import List, Optional, Tuple
from pydantic import BaseModel, Field

class BoundingBox(BaseModel):
    """Bounding box coordinates."""
    x1: int = Field(..., description="Top-left X coordinate")
    y1: int = Field(..., description="Top-left Y coordinate")
    x2: int = Field(..., description="Bottom-right X coordinate")
    y2: int = Field(..., description="Bottom-right Y coordinate")
    
    @property
    def width(self) -> int:
        """Box width."""
        return self.x2 - self.x1
    
    @property
    def height(self) -> int:
        """Box height."""
        return self.y2 - self.y1
    
    @property
    def center(self) -> tuple[int, int]:
        """Box center (x, y)."""
        return ((self.x1 + self.x2) / 2, (self.y1 + self.y2) / 2)
    
    @property
    def area(self) -> int:
        """Box area."""
        return self.width * self.height
    
    @classmethod
    def from_xywh(cls, x: int, y: int, w: int, h: int) -> 'BoundingBox':
        """Create BoundingBox from (x, y, width, height) format."""
        return cls(x1=x, y1=y, x2=x + w, y2=y + h)

    def to_list(self) -> list[int]:
        """Convert to list of coordinates [x1, y1, x2, y2]."""
        return [self.x1, self.y1, self.x2, self.y2]
    
    def to_xywh(self) -> Tuple[int, int, int, int]:
        """Convert to (x, y, width, height) format for OpenCV."""
        return (self.x1, self.y1, self.width, self.height)