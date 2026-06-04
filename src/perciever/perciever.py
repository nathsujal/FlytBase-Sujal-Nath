from typing import Dict, Iterator, Optional, Callable, List
from collections import Counter
from tqdm import tqdm

from .detector import ObjectDetector
from .tracker import ObjectTracker
from src.schemas import Frame, Object
from src.utils import get_logger

logger = get_logger(__name__)


class Perciever:
    """
    Object detection and tracking.
    
    Features:
    - Periodic detection (every N frames)
    - Continuous tracking (all frames)
    - Automatic sync between detector and tracker
    
    Usage:
        stage = Perciever(frames, detect_interval=5)
        for frame in stage.process():
            # frame has detected/tracked objects
            print(f"Frame {frame.frame_id}: {len(frame.objects)} objects")
    """
    
    def __init__(
        self,
        frames: List[Frame],
        detect_interval: int = 5
    ):
        """
        Initialize perciever.
        
        Args:
            frames: List of frames to process
            detect_interval: Run detection every N frames
        """
        self.detector = ObjectDetector()
        self.tracker = ObjectTracker()
        
        self.detect_interval = detect_interval

        self.frames = frames
        self.objects: Dict[int, Object] = {} # object_id -> Object
        
        # State
        self.frame_count = 0
        
        logger.info(
            f"Perciever initialized: "
            f"detect_interval={detect_interval}"
        )
    
    def _should_detect(self, frame_id: int) -> bool:
        """Determine if detection should run on this frame."""
        return (frame_id) % self.detect_interval == 0
    
    def _upsert_object(self, obj: Object) -> None:
        """Add or update an object in the objects dict."""
        if obj.object_id not in self.objects:
            # New object - add it
            self.objects[obj.object_id] = obj
        else:
            # Existing object - merge data
            existing = self.objects[obj.object_id]
            
            # Merge bounding boxes
            existing.bounding_boxes.update(obj.bounding_boxes)
            
            # Update timestamps
            if obj.last_timestamp_sec is not None:
                existing.last_timestamp_sec = obj.last_timestamp_sec
    
    def process_frame(self, frame: Frame) -> Frame:
        """
        Process a single frame with detection and/or tracking.
        
        Args:
            frame: Input frame
            
        Returns:
            Frame with detected/tracked objects
        """
        
        if self._should_detect(frame.frame_id):
            # Run detection
            logger.debug(f"Frame {frame.frame_id}: Running detection")
            frame = self.detector.detect(frame)
            
            # Sync tracker with detections
            frame = self.tracker.sync_with_detections(frame)
        else:
            # Only track existing objects
            logger.debug(f"Frame {frame.frame_id}: Running tracking only")
            frame = self.tracker.update(frame)

        # Store all tracked objects
        if frame.contains_objects:
            for obj in frame.objects:
                self._upsert_object(obj)
        
        self.frame_count += 1
        
        return frame
    
    def process(
        self,
        on_frame: Optional[Callable[[Frame], None]] = None
    ) -> Iterator[Frame]:
        """
        Process all frames from the loader.
        
        Args:
            on_frame: Optional callback for each processed frame
            
        Yields:
            Processed frames with detected/tracked objects
        """
        logger.info("Starting perception pipeline")
        
        # Get total frames if available
        try:
            total_frames = len(self.frames)
        except:
            total_frames = None
        
        # Create progress bar
        pbar = tqdm(
            total=total_frames,
            desc="Processing",
            unit="frame",
            bar_format="{l_bar}{bar}| {n_fmt}/{total_fmt} [{rate_fmt}]",
            dynamic_ncols=True,
            ncols=100,
            leave=True,
            position=0
        )
            
        try:
            for idx, frame in enumerate(self.frames):
                # Process frame
                frame = self.process_frame(frame)
                    
                # Update frame in list
                self.frames[idx] = frame
                
                # Call callback if provided
                if on_frame:
                    on_frame(frame)
                
                # Update progress bar
                pbar.update(1)
                    
                yield frame
                    
        except Exception as e:
            pbar.close()
            logger.error(f"Error at frame {self.frame_count}: {e}")
            raise
        finally:
            # Close progress bar
            pbar.close()
        
        # Final statistics
        logger.info("Perciever Complete")
    
    def process_all(self) -> None:
        """
        Process all frames and update frame store.
        Convenience method that consumes the entire generator.
        
        This is equivalent to:
            for frame in perciever.process():
                pass
        """
        logger.info("Starting batch processing (all frames)")
        # Consume the generator - process() will handle updates
        for _ in self.process():
            pass

        objects_count = Counter(
            getattr(obj, "label", "unknown")
            for obj in self.objects.values()
        )

        report_path = "alerts.txt"
        with open(report_path, "w") as f:
            f.write("=" * 50 + "\n")
            f.write("SECURITY ANALYSIS REPORT\n")
            f.write("=" * 50 + "\n\n")

            f.write(f"Total objects detected: {len(self.objects)}\n") 
            f.write("Object breakdown:\n")
            for label, count in objects_count.most_common():
                f.write(f"  {label}: {count}\n")

        logger.info("Batch processing complete")
    
    def __iter__(self) -> Iterator[Frame]:
        """Make the stage directly iterable."""
        return self.process()
