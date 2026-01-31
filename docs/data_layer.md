# Multi-Database Architecture

FlytBase uses a dual-database approach to store high-velocity telemetry alongside complex behavioral relationships.

## 1. PostgreSQL (Relational Layer)
Postgres serves as the authoritative source for raw events and object metadata.

### Core Schema
- **`objects`**: Stores object category (car, person) and persistent IDs.
- **`frames`**: Stores image metadata, storage paths, and high-precision timestamps (`captured_at`).
- **`events`**: The join table connecting objects to frames, storing spatial data (bounding boxes) for every detection.
- **`threats`**: Stores results from security audits, including reasoning and threat levels.

### Key Advantage
- Extremely fast for counting, sorting by time, and filtering by ID.
- Best for "What objects were here between 09:00 and 10:00?"

## 2. Neo4j (Graph Identity Layer)
Neo4j stores the "Meaning" of the data—relationships between objects and their semantic attributes.

### Graph Schema
- **Node: `Object`**: Represents a unique tracked entity.
- **Node: `Value`**: Holds attribute values (e.g., Color="Black", Gender="Male").
- **Relationships**:
  - `(o:Object)-[:color]->(v:Value)`
  - `(o:Object)-[:positioned_at]->(v:Value)`
  - Relationships store timestamps as properties (`captured_at`) for temporal relationship queries.

### Key Advantage
- Excels at behavioral context: "What was Car ID 5 doing near the Warehouse Gate?"
- Allows for "Behavioral Anchoring"—connecting an ID to its physical surroundings and actions.

## Repository Pattern (`src/db/repositories`)
The system uses a repository pattern to abstract DB-specific syntax from the main logic. 
- **Wait/Retry**: All DB connectors include robust retry logic to handle temporary connection drops in drone-to-base environments.
