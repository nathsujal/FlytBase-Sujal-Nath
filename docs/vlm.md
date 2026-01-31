# Visual Language Model (VLM) Integration

The VLM module provides semantic "depth" to the system, transforming raw images into human-readable descriptions and specific object attributes.

## Semantic Engines (`src/vlm/engines`)

### 1. BLIP Engine
- **Task**: Image Captioning.
- **Role**: Generates a natural language summary of a frame or a cropped object image.
- **Example**: "A black car parked near a north warehouse gate."

### 2. CLIP Engine
- **Task**: Visual Embedding.
- **Role**: Converts images into high-dimensional vectors. Used primarily for:
  - **Novelty Detection**: Comparing frame vectors to determine if a "new" scene has been captured.
  - **Similarity Search**: Finding similar objects across different time periods.

## Data Analyzers (`src/vlm/analyzers`)

### 1. Frame Analyzer (`src/vlm/analyzers/frame_analyzer.py`)
- **Novelty Filtering**: To avoid redundant LLM calls, it only analyzes "novel" frames where the scene change exceeds a calibrated threshold.
- **Scene Profiling**: Coordinates with Ollama/Qwen to extract high-level scene data (e.g., weather, global location, time of day cues).

### 2. Object Analyzer (`src/vlm/analyzers/object_analyzer.py`)
- **Visual Profiling**: For cada tracked ID, it analyze crops of the object to determine:
  - **Color**: (e.g., "Silver", "Red")
  - **Gender/Age**: For people.
  - **Vehicle Type**: (e.g., "Truck", "SUV")
- **Sync**: These attributes are written directly to the **Neo4j Knowledge Graph** as node properties.

## Optimization Strategy
- **Interval Embedding**: Embeddings are only generated every N frames to reduce GPU/CPU load.
- **Batch Processing**: Engines use batch inference where possible to maximize throughput.
