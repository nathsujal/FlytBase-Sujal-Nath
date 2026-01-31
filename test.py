# import neo4j
# from langchain_neo4j import Neo4jGraph, GraphCypherQAChain
# from langchain_ollama import ChatOllama

# graph = Neo4jGraph(
#     url="neo4j://127.0.0.1:7687",
#     username="neo4j",
#     password="neo4j-password",
#     database="knowlegegraph"
# )

# # graph.refresh_schema()
# print(graph.schema)

# llm = ChatOllama(model="qwen2.5:3b")

# from langchain_core.prompts import PromptTemplate
# CYPHER_PROMPT = PromptTemplate(
#     input_variables=["schema", "question"],
#     template="""You are a Neo4j Cypher expert. Given the schema:
# {schema}
# Generate a Cypher query to answer: {question}
# Rules:
# - Always start with MATCH
# - Always end with RETURN
# - Use proper Cypher syntax
# Example: MATCH (o:Object)-[:color]->(v:Value {{value: 'blue'}}) RETURN o
# Cypher Query:"""
# )

# graph_chain = GraphCypherQAChain.from_llm(
#     llm=llm,
#     graph=graph,
#     cypher_prompt=CYPHER_PROMPT,
#     verbose=True,
#     allow_dangerous_requests=True,
#     return_intermediate_steps=True
# )

# response = graph_chain.invoke(
#     {"query": "Find all object IDs where the object label is 'car' and it has a color relationship to a Value node with value 'black'"}
# )

# print(response["intermediate_steps"])
# print(f"Response: {response['result']}")
# import json
# from src.vlm.processing.kg_extractor import KGExtractor
# from dataclasses import asdict

# kg_extractor = KGExtractor()
# res = """{
#     "entities_and_triples": [
#         "[1], OBJECT:Object [2]",
#         "[2], VEHICLE:car",
#         "[3], URBAN_ELEMENT:crosswalk",
#         "[4], BUILDING:buildings",
#         "[5], TRAFFIC_CONTROL:traffic signals",
#         "[6], PERIMETER:surrounding area",
#         "[1] NEAR [3]",
#         "[1] POSITIONED_AT [6]",
#         "[4] IN_FRONT_OF [1]",
#         "[5] IN_FRONT_OF [1]","""

# entities, relations = kg_extractor._parse_response(res)

# print("Entities:")
# print(json.dumps({k: asdict(v) for k, v in entities.items()}, indent=2))

# print("\nRelations:")
# print(json.dumps([asdict(r) for r in relations], indent=2))

# from src.security.agent import SecurityAgent

# agent = SecurityAgent(loitering_threshold_sec=2)

# analysis = agent.analyze()
# for a in analysis:
#     print(
#         f"Object id: {a.object_id}\n"
#         f"Label: {a.label}\n"
#         f"Duration: {a.duration_sec}s\n"
#         f"is_threat: {a.is_threat}\n"
#         f"reasoning: {a.reasoning}\n"
#         f"timeline: {a.timeline_summary}\n"
#     )
#     print("\n")

import json
from src.security.collectors.postgres_collector import get_off_hours_activity

objs = get_off_hours_activity(start_hour=9, end_hour=10)

i = 0
for obj in objs:
    for o in obj.items():
        print(f"{o[0]}: {o[1]} ({type(o[1])})")
    print("\n")
    i += 1
    if i == 5:
        break