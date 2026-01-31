# import neo4j
# from langchain_neo4j import Neo4jGraph, GraphCypherQAChain
# from langchain_ollama import ChatOllama

# graph = Neo4jGraph(
#     url="neo4j://127.0.0.1:7687",
#     username="neo4j",
#     password="neo4j-password",
#     database="knowlegegraph",
#     enhanced_schema=True,
# )
# graph.refresh_schema()

# from langchain_core.prompts import PromptTemplate

# CYPHER_GENERATION_PROMPT_TEMPLATE = """Task: Generate a Cypher query for a Neo4j graph database.
# Instructions:
# 1. Relationships: ALL relationships (POSITIONED_AT, NEAR, color, build, etc.) MUST connect an (:Object) to a (:Value) node.
# 2. NO Object-to-Object relationships: Never link (o:Object) directly to another (o:Object).
# 3. NO property filtering on Object: Attributes like 'color', 'gender', 'type' are NOT properties of Object nodes. They are relationships to Value nodes.
# Schema:
# {schema}
# Note: Return ONLY the Cypher statement. No explanations or apologies.
# Examples:
# - "Find black car in garage": MATCH (o:Object)-[:color]->(v1:Value {{value: 'black'}}), (o)-[:POSITIONED_AT]->(v2:Value {{value: 'garage'}}) WHERE o.label = 'car' RETURN o.id
# - "Person near main gate": MATCH (o:Object)-[:NEAR]->(v:Value {{value: 'main gate'}}) WHERE o.label = 'person' RETURN o.id
# - "Motorcycles with no rider": MATCH (o:Object)-[:rider_present]->(v:Value {{value: 'no'}}) WHERE o.label = 'motorcycle' RETURN o.id

# Question: {question}
# """

# CYPHER_GENERATION_PROMPT = PromptTemplate(
#     input_variables=["schema", "question"],
#     template=CYPHER_GENERATION_PROMPT_TEMPLATE
# )

# llm = ChatOllama(model="qwen2.5:3b")

# graph_chain = GraphCypherQAChain.from_llm(
#     cypher_llm=llm,
#     qa_llm=llm,
#     graph=graph,
#     cypher_prompt=CYPHER_GENERATION_PROMPT,
#     return_direct=True,
#     allow_dangerous_requests=True,
#     return_intermediate_steps=True
# )

# response = graph_chain.invoke(
#     {"query": "When did the black car entered the garage?"}
# )

# print(response["intermediate_steps"])
# print(f"Response: {response['result']}")


# print(f"\n\n{response}\n\n")

from pydantic import BaseModel, Field
from typing import List
from src.llms.ollama.base import OllamaLLM
from src.security.agent import run_security_analysis, Threat, VehicleTracking

tracks, threats = run_security_analysis()

print("\n" + "="*50)
print("SECURITY ANALYSIS REPORT")
print("="*50)

for track in tracks:
    print(f"\n🚗 VEHICLE LIFECYCLE: {track.object_id} ({track.label})")
    print(f"  - Summary    : {track.summary}")
    print("  - Events     :")
    for event in track.events:
        print(f"    [{event.timestamp}] {event.event_type.value} | {event.location} | {event.description}")
    print()

print("\n" + "="*50)

for threat in threats:
    print(f"\n🚨 THREAT DETECTED: {threat.threat_type.value.upper()}")
    print(f"  - Object ID  : {threat.object_id} ({threat.label})")
    print(f"  - Is Suspicious: {threat.is_threat}")
    print(f"  - Reasoning  : {threat.reasoning}")
    print(f"  - Alert      : {threat.alert}")
    print()