# FlytBase: Drone-Powered Security Analyst

FlytBase is a multi-modal security orchestration platform that transforms aerial drone telemetry into structured, behavioral intelligence. By combining computer vision with relational and graph knowledge bases, FlytBase provides a conversational interface for advanced security investigations.

## 🏗 System Architecture

The project is built on a modular pipeline that converts visual pixels into high-level security assessments.

### 1. Perception & Tracking
Real-time object detection and persistent identity tracking using YOLO and ByteTracker.
[View Detailed Docs →](docs/perception.md)

### 2. Multi-Database Data Layer
Synchronized storage between PostgreSQL (structured metrics) and Neo4j (behavioral knowledge).
[View Detailed Docs →](docs/data_layer.md)

### 3. VLM Intelligence
Semantic analysis of scenes and objects using BLIP, CLIP, and specialized LLM profiling.
[View Detailed Docs →](docs/vlm.md)

### 4. Security Pattern Detection
Automated identification of loitering, off-hours activity, and behavioral anomalies.
[View Detailed Docs →](docs/security.md)

### 5. Intelligent Orchestration
The conversational security agent that reasons across your entire data stack using LangGraph.
[View Detailed Docs →](docs/agent.md)

---

## 🚀 Quick Start

### 1. Run the Full Perception Pipeline
Processes a video source and populates the databases.
```bash
python main.py --source path/to/video.mp4
```

### 2. Start the Interactive Analyst
Open a chat session with the Multi-DB Security Agent.
```bash
export PYTHONPATH=$PYTHONPATH:$(pwd)
python src/agent/agent.py
```

## 🛠 Prerequisites
- **PostgreSQL 15+**: For structured telemetry.
- **Neo4j 5+**: For behavioral graph storage.
- **Ollama**: For running Qwen2.5 (Perception logic and Agent).
- **Python 3.10+**

## 📂 Project Summary
- `src/perciever`: Computer Vision (Detection + Tracking).
- `src/vlm`: Visual Language Model integration.
- `src/db`: Database connectivity and schema management.
- `src/security`: Threat detection logic and collectors.
- `src/agent`: LangGraph orchestrator and interactive CLI.
