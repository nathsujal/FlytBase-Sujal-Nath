"""Data loader for drone footage - supports video files and frame directories."""

import cv2
from pathlib import Path
from typing import Iterator, Optional, Tuple, Union
import numpy as np
from datetime import datetime, timedelta

from src.schemas import Frame

class DroneFootageLoader:
    """
    Loads drone footage from video files or frame directories.
    Provides uniform interface for both sources.
    """
    
    def __init__(
        self,
        source: Union[str, Path],
        fps: Optional[float] = None,
        record_start_time: Optional[datetime] = datetime(2026, 1, 1, 9, 30, 0)
    ):
        """
        Args:
            source: Path to video file or frames directory
            fps: Override FPS (if None, use video FPS or default 30)
            record_start_time: Recording start time (if None, uses current time)
        """
        self.source = Path(source)
        self.fps = fps
        self.record_start_time = record_start_time
        self._frames = []
        
        # Determine source type
        if self.source.is_file():
            self.source_type = "video"
            self._init_video()
        elif self.source.is_dir():
            self.source_type = "frames"
            self._init_frames()
        else:
            raise ValueError(f"Source not found: {source}")
        
        # Eagerly load all frames into store
        self._load_all_frames()
    
    def _init_video(self):
        """Initialize video capture."""
        self.cap = cv2.VideoCapture(str(self.source))
        if not self.cap.isOpened():
            raise ValueError(f"Could not open video: {self.source}")
        
        # Get video properties
        self.video_fps = self.cap.get(cv2.CAP_PROP_FPS)
        self.total_frames = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT))
        self.width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        self.height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        
        if self.fps is None:
            self.fps = self.video_fps
        
        self.frame_paths = None
    
    def _init_frames(self):
        """Initialize frame directory."""
        # Find all image files
        self.frame_paths = []
        for ext in ['*.jpg', '*.jpeg', '*.png']:
            self.frame_paths.extend(self.source.glob(ext))
        self.frame_paths = sorted(self.frame_paths,
                                  key=lambda x: x.stat().st_mtime
                                )
        
        if not self.frame_paths:
            raise ValueError(f"No frames found in: {self.source}")
        
        print(f"Found frames: {len(self.frame_paths)}") 
        
        self.total_frames = len(self.frame_paths)

        # Get dimensions from first frame
        first_frame = cv2.imread(str(self.frame_paths[0]))
        if first_frame is None:
            raise ValueError(f"Could not read first frame: {self.frame_paths[0]}")
        
        self.height, self.width = first_frame.shape[:2]
        
        if self.fps is None:
            self.fps = 30.0  # Default FPS for frame sequences
        
        self.cap = None
        self.current_frame_idx = 0
    
    def _load_all_frames(self):
        """Load all frames into the frame store."""
        if self.source_type == "video":
            frame_id = 0
            while True:
                ret, image = self.cap.read()
                if not ret:
                    break
                # Calculate timestamp based on frame_id and FPS
                timestamp_sec = round(frame_id / self.fps, 2)
                captured_at = self.record_start_time + timedelta(seconds=timestamp_sec)
                frame = Frame(
                    frame_id=frame_id,
                    image=image,
                    timestamp_sec=timestamp_sec,
                    captured_at=captured_at,
                )
                self._frames.append(frame)
                frame_id += 1
        else:  # frames directory
            for frame_id, frame_path in enumerate(self.frame_paths):
                image = cv2.imread(str(frame_path))
                if image is not None:
                    # Calculate timestamp based on frame_id and FPS
                    timestamp_sec = round(frame_id / self.fps, 2)
                    captured_at = self.record_start_time + timedelta(seconds=timestamp_sec)
                    frame = Frame(
                        frame_id=frame_id,
                        image=image,
                        timestamp_sec=timestamp_sec,
                        captured_at=captured_at,
                    )
                    self._frames.append(frame)
    
    def __iter__(self) -> Iterator[Frame]:
        """Iterate over frames from the store.
    
        Yields:
            Frame objects
        """
        for frame in self._frames:
            yield frame

        if self.cap is not None:
            self.cap.release()
    
    def __len__(self) -> int:
        """Return total number of frames."""
        return self.total_frames

    @property
    def frames(self) -> list[Frame]:
        """Return all frames as a list."""
        return self._frames