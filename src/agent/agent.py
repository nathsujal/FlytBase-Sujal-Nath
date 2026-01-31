from typing import Generator, List, Any
from langchain_ollama import ChatOllama
from langchain_community.utilities import SQLDatabase
from langchain_community.agent_toolkits import SQLDatabaseToolkit
from src.agent.graph_agent import GraphAgent
from langchain.tools import tool
from langgraph.prebuilt import create_react_agent
from langgraph.checkpoint.memory import MemorySaver
from src.config import settings

@tool
def query_behavior_graph(question: str) -> str:
    """
    Use this tool to fetch raw behavioral and contextual data from Neo4j.
    Input should be a descriptive question like 'What is car ID 5 near?' or 'What activities were seen for ID 10?'.
    Returns raw data nodes and relationships.
    """
    graph_agent = GraphAgent()
    # Use the internal chain's cypher generation logic but return the raw query results
    res = graph_agent.chain.invoke({"query": question})
    
    # Extract the context gathered by the chain (the actual DB results)
    context = ""
    for step in res.get("intermediate_steps", []):
        if "context" in step:
            context = str(step["context"])
            break
            
    if not context or context == "[]":
        return "No behavioral data found in the graph for this specific question. Try broadening the search."
        
    return f"Neo4j Behavioral Context for '{question}': {context}"

class SecurityAgent:
    def __init__(self, model: str = "qwen2.5:3b", thread_id: str = "security_analyst_001"):
        self.llm = ChatOllama(model=model, num_predict=1024, num_ctx=16384)
        self.db = SQLDatabase.from_uri(
            f"postgresql://{settings.pg_reader}:{settings.pg_reader_password}@"
            f"{settings.pg_host}:{settings.pg_port}/{settings.pg_database_name}"
        )
        self.toolkit = SQLDatabaseToolkit(db=self.db, llm=self.llm)
        self.thread_id = thread_id
        
        # Filter tools to prevent distraction and hallucination
        all_sql_tools = self.toolkit.get_tools()
        essential_tools = [t for t in all_sql_tools if t.name in ["sql_db_query", "sql_db_schema", "sql_db_list_tables"]]
        self.tools = essential_tools + [query_behavior_graph]

        self.system_prompt = """
You are a Security Assistant that orchestrates PostgreSQL and Neo4j.

### **DATABASE ARCHITECTURE**
1. **SQL (Postgres)**: Stores WHAT (labels) and WHEN (captured_at). 
   - Tables: `objects`(id, label), `frames`(id, captured_at), `events`(object_id, frame_id).
2. **Graph (Neo4j)**: Stores BEHAVIOR and ATTRIBUTES (color, gender, age, location).
   - Tool: `query_behavior_graph`

### **STRICT OPERATING RULES**
- **No Hallucination**: You ONLY have: `sql_db_query`, `sql_db_schema`, `sql_db_list_tables`, and `query_behavior_graph`.
- **Result Limits**: Always `LIMIT 5` in SQL queries to prevent memory overload.
- **2-Step Pivot**: 
    1. First, use SQL to find a specific Object ID.
    2. Second, use `query_behavior_graph` with that ID. 
- **Focus**: Investigate ONLY the first relevant object ID you find. Do not try to analyze 20 IDs at once.
- **SQL Syntax**: Timestamps are strings in 'frames'. Use `captured_at::text LIKE '%09:30%'`.
- **Time Sync**: When using `query_behavior_graph`, pass the exact timestamp string or HH:MM from SQL.
- **Context**: The data is from **2026-01-01**.

### **EXAMPLE**
User: "What was the car at 09:30 doing?"
1. Thought: I'll find the car ID in SQL first.
2. Action: `sql_db_query` -> `SELECT o.id FROM objects o JOIN events e ON o.id=e.object_id JOIN frames f ON e.frame_id=f.id WHERE o.label='car' AND f.captured_at::text LIKE '%09:30%' LIMIT 1`
3. Action: `query_behavior_graph` -> "What was car ID 5 doing near the entrance?"

User: "What's the color of object 1?"
1. Thought: I'll find the object ID in Neo4j.
2. Action: `query_behavior_graph` -> "What is color of Object ID 1?"

IMPORTANT: If the Graph tool says 'No behavioral data found', try asking a broader question like 'What is object ID 5 near?'.
"""
        self.memory = MemorySaver()
        self.agent_executor = create_react_agent(
            self.llm, 
            self.tools, 
            prompt=self.system_prompt, 
            checkpointer=self.memory
        )

    def ask(self, user_input: str) -> str:
        """Synchronous version to get only the final response string."""
        config = {"configurable": {"thread_id": self.thread_id}}
        result = self.agent_executor.invoke({"messages": [("user", user_input)]}, config=config)
        return result["messages"][-1].content

    def run_interactive(self):
        print(f"\n--- Unified Security Analyst Agent (Thread: {self.thread_id}) ---")
        print("Type 'exit' to quit.\n")
        
        while True:
            try:
                user_input = input("User: ")
                if user_input.lower() in ["exit", "quit", "q"]:
                    break
                if not user_input.strip():
                    continue
                
                response = self.ask(user_input)
                print(f"\nAssistant: {response}")

            except EOFError:
                break
            except KeyboardInterrupt:
                print("\nExiting...")
                break

if __name__ == "__main__":
    agent = SecurityAgent()
    agent.run_interactive()