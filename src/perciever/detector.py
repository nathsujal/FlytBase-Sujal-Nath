from ultralytics import RTDETR
import torch

from src.schemas import Frame, Object, BoundingBox
from src.utils import get_logger

logger = get_logger(__name__)

CLASSES = [
    "person",
    "bicycle",
    "car",
    "motorcycle",
    "bus",
    "truck",
    "boat"
]


class ObjectDetector:
    """RT-DETR object detector wrapper."""
    def __init__(
        self,
        model_size: str = 'l',
        conf_threshold: float = 0.65
    ):
        self.conf_threshold = conf_threshold
        
        # Only detect these classes
        self.allowed_classes = set(CLASSES)

        if torch.cuda.is_available():
            self.device = 'cuda'
        else:
            self.device = 'cpu'

        model_name = f"models/rtdetr-{model_size}.pt"
        self.model = RTDETR(model_name).to(self.device)

        self.class_names = self.model.names
        logger.info(f"Object detector initialized with model: {model_name}")

    def detect(
        self,
        frame: Frame
    ) -> Frame:

        results = self.model(frame.image, conf=self.conf_threshold, verbose=False)[0]
        detections = []

        if results.boxes is not None:
            for box in results.boxes.cpu().numpy():
                x1, y1, x2, y2 = box.xyxy[0]
                conf = float(box.conf[0])
                cls_id = int(box.cls[0])
                class_name = self.class_names[cls_id]
                
                # Filter: only keep allowed classes
                if class_name not in self.allowed_classes:
                    continue

                detections.append(
                    Object(
                        object_id=None,
                        label=class_name,
                        bounding_boxes={frame.frame_id: BoundingBox(
                            x1=int(x1),
                            y1=int(y1),
                            x2=int(x2),
                            y2=int(y2)
                        )}
                    )
                )
        
        frame.objects = detections

        return frame
