import neo4j
from langchain_core.prompts import PromptTemplate
from langchain_neo4j import Neo4jGraph, GraphCypherQAChain
from langchain_ollama import ChatOllama


CYPHER_PROMPT = PromptTemplate(
    input_variables=["schema", "question"],
    template="""You are a Neo4j Cypher expert. Given the schema:
{schema}
Generate a Cypher query to answer: {question}
Rules:
- Always start with MATCH
- Always end with RETURN
- ALWAYS use `CONTAINS` for timestamp matching to handle milliseconds flexibly (e.g., `WHERE r.captured_at CONTAINS '09:30:00'`).
- The data is from **2026-01-01**. Use this year.
- Relationship properties on `r` include: `captured_at` (String format: '2026-01-01 09:30:00.000000'), `timestamp` (Float).
- Output ONLY the Cypher query string.
Example: MATCH (o:Object {{id: 1}})-[r]->(v:Value) WHERE r.captured_at CONTAINS '09:30:00' RETURN v.value
Cypher Query:"""
)

class GraphAgent:
    def __init__(self):
        self.graph = Neo4jGraph(
            url="neo4j://127.0.0.1:7687",
            username="neo4j",
            password="neo4j-password",
            database="knowlegegraph"
        )
        self.llm = ChatOllama(model="qwen2.5:3b")
        self.chain = GraphCypherQAChain.from_llm(
                        llm=self.llm,
                        graph=self.graph,
                        cypher_prompt=CYPHER_PROMPT,
                        allow_dangerous_requests=True,
                        return_intermediate_steps=True
                    )
    
    def generate_cypher(self, question):
        cypher_queries = []
        res = self.chain.invoke({"query": question})
        for key, value in res.items():
            if key == "intermediate_steps":
                for step in value:
                    if "query" in step:
                        cypher_queries.append(step["query"])
        return cypher_queries


if __name__ == "__main__":
    graph_agent = GraphAgent()
    response = graph_agent.generate_cypher("What happened in the first 1 second?")
    print("\nGenerated Cypher Queries:")
    for query in response:
        print(f"-> {query}")