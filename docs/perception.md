# Perception & Tracking Module

The Perception module is the "eyes" of the FlytBase system. It processes raw video footage into tracked object identities and spatial metadata.

## Core Components

### 1. Object Detector (`src/perciever/detector.py`)
- **Technology**: YOLO (You Only Look Once).
- **Function**: Performs inference on individual frames to generate bounding boxes and class labels (e.g., car, person, vehicle).
- **Optimization**: To save compute, detection isn't run on every single frame by default. The `detect_interval` parameter controls frequency.

### 2. Object Tracker (`src/perciever/tracker.py`)
- **Technology**: ByteTracker.
- **Function**: Links detections across frames to assign a unique, persistent `object_id`.
- **Kalman Filtering**: Uses Kalman filters to predict object positions even when detections are missing (occlusions).
- **Syncing**: The `sync_with_detections` method reconciles raw YOLO detections with existing tracked paths.

### 3. Perciever Orchestrator (`src/perciever/perciever.py`)
- **Role**: Coordinates the Detector and Tracker.
- **Continuous Tracking**: While detection and data sync might happen every 5 frames, the tracker updates its state on *every* frame to ensure no ID switching occurs.
- **State Management**: Maintains the `objects` dictionary which stores the global state of every entity seen in the session.

## Data Flow
1. **Raw Frame**: Received from the loader.
2. **Decision Node**: 
   - If `frame_id % interval == 0`: Run YOLO Detection -> Sync Tracker.
   - Else: Update Tracker using motion prediction only.
3. **Upsert**: Results are merged into the global `Object` schema.
4. **Broadcast**: Processed frames are yielded for downstream storage or visualization.

## Key Schemas
- **`src/schemas/frame.py`**: Contains metadata about the captured image.
- **`src/schemas/object.py`**: Stores the persistent identity, including movement history (bounding boxes over time).
