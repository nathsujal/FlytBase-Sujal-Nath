# Security Analysis & Pattern Detection

The security module transforms raw database entries into actionable intelligence by identifying suspicious behaviors according to pre-defined heuristics.

## Data Collectors (`src/security/collectors`)

### 1. PostgreSQL Collector
- **`get_loitering_objects`**: Identifies objects that have remained in the frame/scene beyond a specific time threshold (e.g., > 30 seconds).
- **`get_off_hours_activity`**: Queries for activity during restricted time windows (midnight to 5 AM).

### 2. Neo4j Collector
- **`get_object_timeline`**: Reconstructs an object's behavior by querying its relationships over time (e.g., "ID 5 was near Gate 1, then near Window 2").

## AI Analyst (`src/security/agent.py`)

The system uses LLM-based reasoning (via Ollama/Qwen) to evaluate extracted patterns.

### Evaluation Workflow
1. **Extraction**: Collectors pull a raw timeline for a suspicious ID.
2. **Reasoning**: The `REASONING_PROMPT` instructs the LLM to judge the behavior in context (e.g., "Is it normal for a person to stay near the perimeter fence for 2 minutes?").
3. **Synthesis**: The reasoning is passed to a `SYNTHESIS_PROMPT` to generate a structured `Threat` object.
4. **Alerting**: Threats are assigned levels (LOW, MEDIUM, HIGH, CRITICAL) and stored back in PostgreSQL.

### Detection Heuristics
- **Loitering**: Calculated as `last_seen - first_seen`.
- **Off-Hours**: Triggered by timestamps during site "cold" periods.
- **Unauthorized Proximity**: Detected via Neo4j relationship nodes (e.g., Person ID 10 near "Restricted Area").

## Occlusion Awareness
The security logic includes explicit instructions to account for drone perception limitations. It is trained to ignore "disappearing" objects as suspicious if they are simply being occluded by buildings or trees.
