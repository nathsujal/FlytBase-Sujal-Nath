import re
import json
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass

from src.llms.ollama import OllamaLLM
from src.db.neo4j import get_session
from src.utils import get_logger

logger = get_logger(__name__)


@dataclass
class Entity:
    id: str
    type: str
    value: str

@dataclass
class Relation:
    subject_id: str
    predicate: str
    object_id: str



ENTITY_TYPES = [
    "OBJECT", "VEHICLE", "PERSON", "BUILDING", "ROAD_FEATURE",
    "TRAFFIC_CONTROL", "LANDMARK", "ZONE", "PERIMETER",
    "VEGETATION", "URBAN_ELEMENT"
]
PREDICATES = [
    "POSITIONED_AT", "NEAR", "SURROUNDED_BY", "ADJACENT_TO",
    "ON", "INSIDE", "STOPPED_AT", "WAITING_AT", "CROSSING",
    "IN_FRONT_OF", "BEHIND", "FACING"
]
EXTRACTION_PROMPT = """
Perform Named Entity Recognition (NER) and extract knowledge graph triplets from the text.
**Entity Types:**
{entity_types}
**Predicates:**
{predicates}
**Text:**
{text}
"""


class KGExtractor:
    """Extracts knowledge graph triplets from object description."""

    def __init__(self):
        """
        Initialize KG Extractor.
        """
        self.llm = OllamaLLM(model_key="triplex")

    def extract(
        self,
        object_id: str,
        object_label: str,
        description: str
    ) -> Tuple[Dict[str, Entity], List[Relation]]:
        """
        Extract entities and relations from object description.

        Args:
            object_id: Object ID
            object_label: Object label
            description: Object description

        Returns:
            Tuple of entities and relations
        """
        # Build prompt
        text = f"Object [{object_id}] ({object_label}): {description}"
        prompt = EXTRACTION_PROMPT.format(
            entity_types=ENTITY_TYPES,
            predicates=PREDICATES,
            text=text
        )

        response = self.llm.invoke_knowledge_graph(prompt)

        # Parse response
        entities, relations = self._parse_response(response)

        logger.info(
            f"Extracted {len(entities)} entities and {len(relations)} relations for object {object_id}"
        )
        
        # Log entities
        for eid, entity in entities.items():
            logger.debug(f"  Entity [{eid}]: {entity.type} = {entity.value}")
        
        # Log relations
        for rel in relations:
            subj = entities.get(rel.subject_id)
            obj = entities.get(rel.object_id)
            subj_str = f"{subj.value}" if subj else f"[{rel.subject_id}]"
            obj_str = f"{obj.value}" if obj else f"[{rel.object_id}]"
            logger.debug(f"  Relation: {subj_str} --[{rel.predicate}]--> {obj_str}")

        return entities, relations

    def extract_and_store(
        self,
        object_id: int,
        object_label: str,
        description: str,
        timestamp: int,
        captured_at: str
    ) -> Tuple[Dict[str, Entity], List[Relation]]:
        """
        Extract KG and store to Neo4j.

        Args:
            object_id: Object ID
            object_label: Object label
            description: Object description
            timestamp: Timestamp of the frame

        Returns:
            Tuple of entities and relations
        """
        entities, relations = self.extract(object_id, object_label, description)

        # Store to Neo4j
        self._store_to_neo4j(object_id, entities, relations, timestamp, captured_at)

        return entities, relations

    def _parse_response(self, response: str) -> Tuple[Dict[str, Entity], List[Relation]]:
        """Parse response from LLM."""
        entities: Dict[str, Entity] = {}
        relations: List[Relation] = []

        # Fix incomplete JSON
        content = self._fix_incomplete_json(response)

        # Parse JSON
        try:
            data = json.loads(content)
            items = data.get("entities_and_triples", [])
        except json.JSONDecodeError:
            items = re.findall(r'"([^"]+)"', response)

        for item in items:
            # Entity: "[id], TYPE:value"
            entity_match = re.match(r'\[(\d+)\],?\s*(\w+):(.+)', item.strip())
            if entity_match:
                eid, etype, evalue = entity_match.groups()
                entities[eid] = Entity(id=eid, type=etype, value=evalue.strip())
                continue
            
            # Relation: "[id1] PREDICATE [id2]"
            rel_match = re.match(r'\[(\d+)\]\s+(\w+)\s+\[(\d+)\]', item.strip())
            if rel_match:
                subj_id, predicate, obj_id = rel_match.groups()
                relations.append(Relation(
                    subject_id=subj_id,
                    predicate=predicate,
                    object_id=obj_id
                ))
        
        return entities, relations

    def _fix_incomplete_json(self, content: str) -> str:
        """Fix incomplete JSON by adding missing brackets."""
        content = content.strip()
        
        if content.endswith(','):
            content = content[:-1]
        
        open_brackets = content.count('[') - content.count(']')
        open_braces = content.count('{') - content.count('}')
        
        content += ']' * open_brackets
        content += '}' * open_braces
        
        return content

    def _store_to_neo4j(
        self,
        object_id: int,
        entities: Dict[str, Entity],
        relations: List[Relation],
        timestamp: int,
        captured_at: str
    ):
        """Store extracted KG to Neo4j."""
        with get_session() as session:
            for rel in relations:
                subj = entities.get(rel.subject_id)
                obj = entities.get(rel.object_id)
                
                if not subj or not obj:
                    continue

                if rel.subject_id == "1":
                    # Node starts from the o:Object {id: $object_id}

                    cypher = f"""
                    MATCH (o:Object {{id: $object_id}})
                    MERGE (target:Value {{value: $target_value}})
                    MERGE (o)-[r:{rel.predicate}]->(target)
                    SET r.timestamp = $timestamp,
                        r.captured_at = $captured_at,
                        r.target_entity_type = $target_entity_type
                    """

                    session.run(
                        cypher, 
                        object_id=object_id,
                        target_value=obj.value,
                        timestamp=timestamp,
                        captured_at=captured_at,
                        target_entity_type=obj.type
                    )
                
                elif rel.object_id == "1":
                    # Node ends at the o:Object {id: $object_id}
                    cypher = f"""
                    MERGE (target:Value {{value: $target_value}})
                    WITH target
                    MATCH (o:Object {{id: $object_id}})
                    MERGE (target)-[r:{rel.predicate}]->(o)
                    SET r.timestamp = $timestamp,
                        r.captured_at = $captured_at,
                        r.source_entity_type = $source_entity_type
                    """

                    session.run(
                        cypher,
                        target_value=subj.value,
                        object_id=object_id,
                        timestamp=timestamp,
                        captured_at=captured_at,
                        source_entity_type=subj.type
                    )
                else:
                    logger.warning(f"Skipping relation {rel.predicate} between {subj.value} and {obj.value} as neither is the main object")
        
        logger.info(f"Stored {len(relations)} relations to Neo4j for object {object_id} at timestamp{timestamp}")


# Singleton Instance
_kg_extractor: Optional[KGExtractor] = None
def get_kg_extractor() -> KGExtractor:
    global _kg_extractor
    if _kg_extractor is None:
        _kg_extractor = KGExtractor()
    return _kg_extractor