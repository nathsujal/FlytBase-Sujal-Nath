from pydantic import BaseModel, Field
from enum import Enum
from dataclasses import dataclass
from typing import List, Dict, Any, Optional
from datetime import datetime

from .collectors.postgres_collector import get_loitering_objects, get_vehicle_ids, get_off_hours_activity
from .collectors.neo4j_collector import get_object_timeline
from src.llms.ollama import OllamaLLM
from src.utils import get_logger

logger = get_logger(__name__)


# ============================================================================
# Data Classes
# ============================================================================

class ThreatType(Enum):
    LOITERING = "loitering"
    OFF_HOURS_ACTIVITY = "off-hours activity"

class VehicleEvent(Enum):
    ENTRY = "entry"
    EXIT = "exit"
    PARKED = "parked"
    LOADING = "loading"
    UNLOADING = "unloading"
    STATIONARY = "stationary"

@dataclass
class Threat:
    object_id: int
    label: str
    threat_type: ThreatType
    is_threat: bool
    reasoning: str
    alert: str

@dataclass
class VehicleEventInfo:
    event_type: VehicleEvent
    timestamp: str
    location: str
    description: str

@dataclass
class VehicleTracking:
    object_id: int
    label: str
    events: List[VehicleEventInfo]
    summary: str

class ThreatSchema(BaseModel):
    is_threat: bool = Field(description="Whether behavior is suspicious")
    threat_level: str = Field(description="LOW, MEDIUM, HIGH, or CRITICAL")
    reasoning: str = Field(description="Detailed logic for assessment")
    alert: str = Field(description="Concise alert message")

class VehicleLifecycleSchema(BaseModel):
    object_id: int = Field(description="ID of the vehicle")
    entry_time: Optional[str] = Field(description="Timestamp when vehicle entered perimeter")
    exit_time: Optional[str] = Field(description="Timestamp when vehicle exited perimeter")
    parked_time: Optional[str] = Field(description="Timestamp when vehicle was first stationary in a parking spot")
    loading_start: Optional[str] = Field(description="Timestamp when loading activity started")
    unloading_start: Optional[str] = Field(description="Timestamp when unloading activity started")
    events: List[str] = Field(description="Cronological list of major events detected")
    is_suspicious: bool = Field(description="Whether the vehicle behavior is suspicious")
    reasoning: str = Field(description="Detailed reasoning for the assessment")


# ============================================================================
# Prompts
# ============================================================================

VEHICLE_LIFECYCLE_REASONING_PROMPT = """You are a security analyst AI reviewing vehicle surveillance data from a drone.

## Task
Perform a detailed behavioral analysis of the vehicle's "lifecycle" within the surveillance zone. 
Your goal is to identify specific milestones: Arrival (Entry), Parking, Loading/Unloading, and Departure (Exit).

## Vehicle Information
- **Object ID:** {object_id}
- **Type:** {label}

## Movement Timeline
{timeline}

## Analysis Instructions
Analyze the timeline for the following:
1. **Perimeter Entry:** Identify the exact time and location where the vehicle first appeared or crossed into the property.
2. **Parking Event:** Look for a sustained period where the vehicle is stationary at a designated parking area or near a building.
3. **Loading/Unloading:** Identify activity around the vehicle while it is parked. Are people nearby? Is the trunk or door area active? Look for proximity shifts in the timeline.
4. **Perimeter Exit:** Identify the time and location where the vehicle was last seen leaving the area.
5. **Suspicious Patterns:** Note any circling, loitering before parking, or bypassing security checkpoints.

## System Perception Context (IMPORTANT)
The surveillance system processes data in discrete temporal phases and from a dynamic drone perspective.
- **Expected Gaps**: Gaps in the timeline where the object is not detected are expected system artifacts.
- **Occlusions**: Objects may be temporarily hidden behind buildings, trees, or other structures from the drone's point of view.
- **Constraint**: You MUST NOT interpret these data gaps or temporary disappearances as suspicious "hiding," "bypassing checkpoints," or deliberate evasion. Judge behavior only based on the data available WITHIN the captured segments.

## Required Output
Perform the analysis internally and provide a clear, structured summary of findings.
"""

VEHICLE_LIFECYCLE_SYNTHESIS_PROMPT = """You are a data synthesis AI. 
Convert the following behavioral reasoning into a structured JSON representation of the vehicle's lifecycle.
Object ID: {object_id}
Object Label: {label}

## Reasoning Input
{reasoning}

## Target Schema
Refer to the provided JSON schema. Ensure all timestamps are extracted exactly as seen in the reasoning.
If an event (like loading) was not detected, leave it as null.
"""

LOITERING_REASONING_PROMPT = """You are a security analyst AI reviewing surveillance data.

## Task
Analyze whether the following object behavior indicates suspicious loitering or normal activity.

## Object Information
- **Object ID:** {object_id}
- **Type:** {label}
- **Duration in footage:** {duration_sec:.1f} seconds

## Object Timeline (where it was and when)
{timeline}

## Analysis Instructions
Consider the following:
1. Is the object stationary in one location or moving between locations?
2. Are the locations it visited normal for its type? (e.g., person lingering near perimeter = suspicious)
3. Does the movement pattern suggest surveillance, waiting, or normal transit?
4. What is the context of its surroundings?

## System Perception Context (IMPORTANT)
The surveillance system processes data in discrete temporal phases and from a dynamic drone perspective.
- **Expected Gaps**: Gaps in the timeline where the object is not detected are expected system artifacts.
- **Occlusions**: Objects may be temporarily hidden behind buildings, trees, or other structures from the drone's point of view.
- **Constraint**: You MUST NOT interpret these data gaps or temporary disappearances as suspicious "hiding," "bypassing checkpoints," or deliberate evasion. Judge behavior only based on the data available WITHIN the captured segments.

## Required Output
Perform the analysis internally and provide a clear, structured summary of findings.
"""

LOITERING_SYNTHESIS_PROMPT = """You are a security data synthesizer.
Convert the following behavioral reasoning about loitering into a structured JSON representation.
Object ID: {object_id}
Object Label: {label}

## Reasoning Input
{reasoning}

## Target Schema
Refer to the provided Threat schema. 
- **is_threat**: YES if the reasoning concludes suspicious loitering, NO otherwise.
- **threat_level**: LOW, MEDIUM, HIGH, or CRITICAL based on the severity.
- **alert**: A concise one-line alert message.
"""


OFF_HOURS_REASONING_PROMPT = """You are a security analyst AI.

## Task
Analyze whether the presence of the following object during restricted "off-hours" is suspicious or authorized.

## Object Information
- **Object ID:** {object_id}
- **Type:** {label}

## Object Timeline
{timeline}

## Analysis Instructions
1. **Context of Location**: Is the object in a public-facing area (like a perimeter road) or a restricted area (near side doors, warehouses)?
2. **Behavioral Cues**: Is the object moving purposefuly (transit) or showing signs of surveillance (loitering, frequent stops)?
3. **Risk Level**: Given the "off-hours" constraint, how high is the risk of this activity being unauthorized or malicious?

## System Perception Constraints
The surveillance system processes data in discrete temporal phases and from a dynamic drone perspective.
- **Expected Gaps**: Gaps in the timeline where the object is not detected are expected system artifacts.
- **Occlusions**: Objects may be temporarily hidden behind buildings, trees, or other structures from the drone's point of view.
- **Constraint**: You MUST NOT interpret these data gaps as suspicious "hiding."

## Required Output
Provide a clear, structured summary of findings.
"""

OFF_HOURS_SYNTHESIS_PROMPT = """You are a security data synthesizer.
Convert the following behavioral reasoning about off-hours activity into a structured JSON representation.
Object ID: {object_id}
Object Label: {label}

## Reasoning Input
{reasoning}

## Target Schema
Refer to the provided Threat schema. 
- **is_threat**: YES if the reasoning concludes the activity is suspicious/unauthorized, NO otherwise.
- **threat_level**: LOW, MEDIUM, HIGH, or CRITICAL.
- **alert**: A concise one-line alert message.
"""


# ============================================================================
# Security Agent
# ============================================================================

class SecurityAgent:
    """
    Security agent that analyzes surveillance data for potential threats.
    
    Detection Pipeline:
    1. Rule-based extraction (PostgreSQL) - Find objects with long duration
    2. Context gathering (Neo4j) - Get spatial/temporal timeline
    3. LLM reasoning - Determine if behavior is actually suspicious
    """
    
    def __init__(
        self,
        loitering_threshold_sec: float = 3.0,
        off_hours_start_hour: int = 9,
        off_hours_end_hour: int = 10,
    ):
        """
        Initialize the security agent.
        """
        self.reasoning_llm = OllamaLLM("qwen", num_predict=2048)
        self.synthesize_llm = OllamaLLM("qwen", num_predict=512)
        self.loitering_threshold_sec = loitering_threshold_sec
        self.off_hours_start_hour = off_hours_start_hour
        self.off_hours_end_hour = off_hours_end_hour

        logger.info(f"SecurityAgent initialized with loitering threshold: {loitering_threshold_sec}s")

    def analyze(self) -> List[Any]:
        """
        Run full security analysis pipeline.
        
        Returns:
            List of detected assessments
        """
        logger.info("Starting security analysis...")

        tracks = self._track_vehicles()
        
        threats = []
        
        # 1. Detect loitering
        threats.extend(self._detect_loitering())
        
        # 2. Analyze off-hours activity
        threats.extend(self._analyze_off_hours_activity())

        self.write_alerts(tracks, threats)
        
        return tracks, threats

    def _format_timeline_as_table(self, timeline_data: Dict[str, Any]) -> str:
        """
        Format the Neo4j timeline data as a Markdown table for better LLM readability.
        """
        timeline = timeline_data.get("timeline", [])
        if not timeline:
            return "No movement recorded."
            
        header = "| Time (s) | Timestamp | Event Type | Entity | Value |"
        separator = "|----------|-----------|------------|--------|-------|"
        rows = []
        
        for e in timeline:
            ts = f"{e['timestamp_sec']:.2f}" if e.get("timestamp_sec") is not None else "N/A"
            captured = e.get("captured_at") or "N/A"
            relation = e.get("relation") or "N/A"
            entity = e.get("entity_type") or "N/A"
            value = e.get("value") or "N/A"
            
            rows.append(f"| {ts} | {captured} | {relation} | {entity} | {value} |")
            
        return "\n".join([header, separator] + rows)

    def _track_vehicles(self) -> List[VehicleTracking]:
        """
        Track and analyze vehicle behavior.

        Pipeline:
        1. Extract vehicle IDs from PostgreSQL
        2. Get timeline for each vehicle from Neo4j
        3. Analyze vehicle lifecycle using LLM reasoning
        """
        logger.info("Starting vehicle tracking analysis...")
        vehicle_data = get_vehicle_ids()
        logger.info(f"Retrieved {len(vehicle_data)} vehicle IDs")
        
        tracks = []
        for v in vehicle_data:
            object_id = v["id"]
            label = v["label"]
            
            logger.debug(f"Analyzing vehicle lifecycle: {object_id} ({label})")
            
            # Get timeline
            timeline_data = get_object_timeline(object_id)
            timeline = self._format_timeline_as_table(timeline_data)
            
            object_info = {
                "object_id": object_id,
                "label": label,
                "timeline": timeline
            }
            
            try:
                tracking_res = self._reason(
                    object_info=object_info,
                    reason_for="vehicle_lifecycle"
                )
                
                # Ensure it has timeline info for test.py
                tracking_res.timeline_summary = timeline
                tracks.append(tracking_res)
                
            except Exception as e:
                logger.error(f"Reasoning failed for vehicle {object_id}: {e}")
                
        return tracks

    def _detect_loitering(self) -> List[Threat]:
        """
        Detect loitering behavior using rule-based + LLM reasoning.
        
        Pipeline:
        1. Get objects with duration > threshold (PostgreSQL)
        2. Get timeline for each object (Neo4j)
        3. Ask LLM to reason about each candidate
        
        Returns:
            List of Threat assessments
        """
        logger.info(f"Detecting loitering (threshold: {self.loitering_threshold_sec}s)")
        
        # Step 1: Rule-based extraction from PostgreSQL
        loitering_objects = get_loitering_objects(self.loitering_threshold_sec)
        logger.info(f"Found {len(loitering_objects)} objects exceeding duration threshold")
        
        if not loitering_objects:
            return []
        
        threats = []
        
        for obj in loitering_objects:
            object_id = obj["object_id"]
            label = obj["label"]
            duration_sec = obj["duration_sec"]
            
            logger.debug(f"Analyzing object {object_id} ({label}) - duration: {duration_sec:.1f}s")
            
            # Step 2: Get timeline from Neo4j
            timeline_data = get_object_timeline(object_id)
            timeline = self._format_timeline_as_table(timeline_data)

            object_info = {
                "object_id": object_id,
                "label": label,
                "duration_sec": duration_sec,
                "timeline": timeline
            }
            
            # Step 3: LLM reasoning
            threat = self._reason(
                object_info=object_info,
                reason_for="loitering",
            )
            
            threats.append(threat)
        
        return threats

    def _analyze_off_hours_activity(self) -> List[Threat]:
        """
        Analyze off-hours activity.

        Pipeline:
        1. Rule-based extraction from PostgreSQL
        2. Get timeline for each object from Neo4j
        3. Analyze object behavior using LLM reasoning
        """
        logger.info(f"Detecting off-hours activity (Starting hour: {self.off_hours_start_hour}, End hour: {self.off_hours_end_hour})")
        
        # 1. Rule-based extraction from PostgreSQL
        objects = get_off_hours_activity(self.off_hours_start_hour, self.off_hours_end_hour)
        logger.info(f"Found {len(objects)} off-hours detections")
        
        if not objects:
            return []
        
        threats = []
        
        for obj in objects:
            object_id = obj["object_id"]
            label = obj["label"]
            
            logger.debug(f"Analyzing object {object_id} ({label}) - off-hours")
            
            # Get timeline from Neo4j
            timeline_data = get_object_timeline(object_id)
            timeline = self._format_timeline_as_table(timeline_data)
            
            object_info = {
                "object_id": object_id,
                "label": label,
                "timeline": timeline
            }
            
            # LLM reasoning
            threat = self._reason(
                object_info=object_info,
                reason_for="off_hours_activity"
            )
            
            threats.append(threat)
        
        return threats


    def _reason(
        self,
        object_info: dict,
        reason_for: str,
    ) -> Any:
        """
        Use LLM to reason about whether the object behavior is suspicious.
        
        Args:
            object_id: Object ID
            label: Object type (car, person, etc.)
            duration_sec: Duration in footage
            timeline: Formatted timeline string
            
        Returns:
            LoiteringThreat with reasoning
        """
        # Build prompt
        if reason_for == "loitering":
            prompt = LOITERING_REASONING_PROMPT.format(**object_info)
        elif reason_for == "vehicle_lifecycle":
            prompt = VEHICLE_LIFECYCLE_REASONING_PROMPT.format(**object_info)
        elif reason_for == "off_hours_activity":
            prompt = OFF_HOURS_REASONING_PROMPT.format(**object_info)
        else:
            raise ValueError(f"Unknown reason_for: {reason_for}")

        try:
            logger.debug(f"Executing behavioral reasoning with phi4 for {reason_for}...")
            reasoning = self.reasoning_llm.invoke_with_reasoning(prompt)

            print(f"\nReasoning: {reasoning}\n")
            
            # 2. Structured Synthesis (Qwen)
            if reason_for == "loitering" or reason_for == "off_hours_activity":
                logger.debug(f"Synthesizing {reason_for} threat with qwen...")
                
                if reason_for == "loitering":
                    schema = ThreatSchema
                    synthesis_prompt = LOITERING_SYNTHESIS_PROMPT.format(
                        reasoning=reasoning,
                        object_id=object_info["object_id"],
                        label=object_info["label"]
                    )
                else:
                    schema = ThreatSchema
                    synthesis_prompt = OFF_HOURS_SYNTHESIS_PROMPT.format(
                        reasoning=reasoning,
                        object_id=object_info["object_id"],
                        label=object_info["label"]
                    )

                threat_data = self.synthesize_llm.invoke_structured(
                    prompt=synthesis_prompt,
                    schema=schema,
                    system_message="You are a security data synthesizer. Convert behavioral logs into structured JSON."
                )

                print(f"\nThreat Data: {threat_data.model_dump_json(indent=2)}\n")
                
                return Threat(
                    object_id=object_info["object_id"],
                    label=object_info["label"],
                    threat_type=ThreatType.LOITERING if reason_for == "loitering" else ThreatType.OFF_HOURS_ACTIVITY,
                    is_threat=threat_data.is_threat,
                    reasoning=threat_data.reasoning,
                    alert=threat_data.alert
                )
            
            elif reason_for == "vehicle_lifecycle":
                logger.debug("Synthesizing vehicle lifecycle with qwen...")
                synthesis_prompt = VEHICLE_LIFECYCLE_SYNTHESIS_PROMPT.format(
                    reasoning=reasoning,
                    object_id=object_info["object_id"],
                    label=object_info["label"]
                )
                lifecycle = self.synthesize_llm.invoke_structured(
                    prompt=synthesis_prompt,
                    schema=VehicleLifecycleSchema,
                    system_message="You are a security data synthesizer. Convert behavioral logs into structured JSON."
                )

                print(f"\nVehicle Lifecycle Data: {lifecycle.model_dump_json(indent=2)}\n")
                
                # Map to VehicleTracking object
                events = []
                if lifecycle.entry_time:
                    events.append(VehicleEventInfo(VehicleEvent.ENTRY, lifecycle.entry_time, "perimeter", "Vehicle entered property"))
                if lifecycle.parked_time:
                    events.append(VehicleEventInfo(VehicleEvent.PARKED, lifecycle.parked_time, "internal", "Vehicle parked"))
                if lifecycle.loading_start:
                    events.append(VehicleEventInfo(VehicleEvent.LOADING, lifecycle.loading_start, "internal", "Loading activity started"))
                if lifecycle.unloading_start:
                    events.append(VehicleEventInfo(VehicleEvent.UNLOADING, lifecycle.unloading_start, "internal", "Unloading activity started"))
                if lifecycle.exit_time:
                    events.append(VehicleEventInfo(VehicleEvent.EXIT, lifecycle.exit_time, "perimeter", "Vehicle exited property"))

                return VehicleTracking(
                    object_id=object_info["object_id"],
                    label=object_info["label"],
                    events=events,
                    summary=lifecycle.reasoning
                )
            
        except Exception as e:
            logger.error(f"LLM reasoning failed for object {object_info['object_id']}: {e}")
            # Default to conservative assessment on error
            # This part needs to be updated to return a Threat object, not LoiteringThreat
            # For now, returning a placeholder or re-raising if the schema is strict.
            # Assuming Threat has similar fields for error handling.
            return Threat(
                object_id=object_info["object_id"],
                label=object_info["label"],
                threat_type=ThreatType.UNKNOWN,
                is_threat=False,
                reasoning=f"Analysis failed: {str(e)}",
                alert="Analysis failed"
            )

    def write_alerts(self, tracks: List[VehicleTracking], threats: List[Threat]):
        """
        Write tracks and threats to a text file, sorted by object_id.
        """
        # Combine all items with their object_id
        items = []
        for track in tracks:
            items.append((track.object_id, "TRACK", track))
        for threat in threats:
            items.append((threat.object_id, "THREAT", threat))
            
        # Sort by object_id
        items.sort(key=lambda x: x[0])
        
        report_path = "alerts.txt"
        with open(report_path, "w") as f:
            f.write("=" * 50 + "\n")
            f.write("SECURITY ANALYSIS REPORT\n")
            f.write("=" * 50 + "\n\n")
            
            prev_oid = None
            for _, item_type, data in items:
                if item_type == "THREAT" and not data.is_threat:
                    continue
                if data.object_id != prev_oid:
                    f.write(f"Object ID: {data.object_id} ({data.label})\n")
                if item_type == "TRACK":
                    f.write(f"🚗 VEHICLE LIFECYCLE:\n")
                    f.write("  - Events     :\n")
                    for event in data.events:
                        f.write(f"    [{event.timestamp}] {event.description}\n")
                    f.write(f"  - Summary    : {data.summary}\n")
                    f.write("\n")
                elif data.is_threat:
                    f.write(f"🚨 {data.threat_type.value.upper()} DETECTED: {data.alert}\n")
                    f.write(f"  - Reasoning  : {data.reasoning}\n")
                    f.write("\n")
                prev_oid = data.object_id
            
            f.write("=" * 50 + "\n")
            f.write("End of Report\n")
            
        logger.info(f"Security report written to {report_path}")


# ============================================================================
# Convenience Functions
# ============================================================================

def run_security_analysis() -> List[Any]:
    """
    Run security analysis and return threats.
    
    Args:
        loitering_threshold_sec: Minimum duration for loitering detection
        
    Returns:
        List of detected threats
    """
    agent = SecurityAgent()
    return agent.analyze()
