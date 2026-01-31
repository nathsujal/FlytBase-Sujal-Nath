# Intelligent Security Orchestrator

The `SecurityAgent` is the final layer of the system—a conversational AI that can "talk" to your data to answer complex security questions.

## Core Technology
- **Engine**: LangChain/LangGraph.
- **Pattern**: ReAct (Reasoning + Action). The agent observes the user query, "thinks" about which tool to use, executes it, and refines its answer based on the result.

## Reusable `SecurityAgent` Class
The agent is encapsulated in a class for easy integration into main pipelines or web APIs.

### Main Methods
- `ask(user_input)`: Synchronously returns the final assistant response.
- `aask(user_input)`: Asynchronous version of `ask`.
- `chat(user_input)`: Returns a stream of events (thoughts, tool calls, and results).
- `run_interactive()`: Provides a CLI interface for manual investigation.

## Integrated Tools

### 1. SQL Query Tools
The agent uses `SQLDatabaseToolkit` to:
- List tables.
- View schemas.
- Execute raw SQL queries on the PostgreSQL database.

### 2. Behavioral Graph Tool (`query_behavior_graph`)
A custom tool that bridges the gap between Relational and Graph data. 
- Input: A natural language question like "What was ID 1 near at 09:30?".
- Transformation: Internally translates the question into Cypher for Neo4j.
- Output: Returns raw behavioral context for the agent to synthesize.

## Conversation Memory
The agent uses LangGraph's `MemorySaver` to maintain state across a `thread_id`.
- **Context Retention**: You can ask "Who was object 5?" followed by "What color was it?" and the agent will remember the reference to ID 5.
- **Thread Sharing**: Multiple concurrent threads can exist, keeping different investigations isolated.

## Orchestration Logic (The "Pivot")
The agent is specifically prompted to follow a "Pivot" logic:
1. **Identify**: Use SQL to find ID/Time metrics.
2. **Investigate**: Use Graph to find the "Story" or "Behavior" behind those metrics.
3. **Report**: Summarize everything into a concise security assessment.
