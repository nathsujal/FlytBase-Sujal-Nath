from typing import Optional, List, Type
from pydantic import BaseModel
from langchain_ollama import ChatOllama
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
from langchain_core.output_parsers import BaseOutputParser, StrOutputParser

from ..base import LLM
from .models import get_model_config, ModelConfig, ModelCapability
from src.utils import get_logger, retry

logger = get_logger(__name__)


class OllamaLLM(LLM):
    """Unified Ollama LLM wrapper."""

    def __init__(
        self,
        model_key: str,
        temperature: Optional[float] = None,
        num_predict: int = 2048,
    ):
        # Load config
        self.config = get_model_config(model_key)
        self._model_name = self.config.name
        self.temperature = temperature or self.config.default_temperature

        logger.info(f"Initializing {self.config.display_name}")

        # Initialize Ollama
        self.llm = ChatOllama(
            model=self.config.name,
            temperature=self.temperature,
            num_predict=num_predict,
        )

        logger.info(
            f"{self.config.display_name} initialized successfully | "
            f"Capabilities: {[c.value for c in self.config.capabilities]}"
        )

    @property
    def model_name(self) -> str:
        """Return the model name."""
        return self._model_name

    @property
    def capabilities(self) -> List[ModelCapability]:
        """Return model capabilities."""
        return self.config.capabilities

    def supports(self, capability: ModelCapability) -> bool:
        """Check if model supports a capability."""
        return capability in self.capabilities

    def bind_tools(self, tools: List) -> BaseChatModel:
        """Bind tools to the LLM."""
        return self.llm.bind_tools(tools)

    @retry(retries=3, delay=1.0, backoff=2.0)
    def invoke(
        self,
        prompt: str,
        system_message: Optional[str] = None,
        parser: Optional[BaseOutputParser] = None
    ) -> str:
        """
        Invoke LLM with a single prompt.

        Args:
            prompt: User prompt
            system_message: Optional system message
            parser: Optional output parser
            
        Returns:
            Generated text response
        """
        if parser and not self.supports(ModelCapability.STRUCTURED_OUTPUT):
            raise ValueError(
                f"{self.config.display_name} doesn't support structured output"
            )
        
        try:
            messages = []
            if system_message:
                messages.append(SystemMessage(content=system_message))
            messages.append(HumanMessage(content=prompt))

            if parser and isinstance(parser, StrOutputParser):
                chain = self.llm | parser
                return chain.invoke(messages)
            
            response = self.llm.invoke(messages)
            return response.content
            
        except Exception as e:
            logger.error(f"Failed to invoke {self.config.display_name}: {e}")
            raise RuntimeError(f"{self.config.display_name} invocation failed: {e}") from e

    @retry(retries=3, delay=1.0, backoff=2.0)
    def invoke_structured(
        self,
        prompt: str,
        schema: Type[BaseModel],
        system_message: Optional[str] = None
    ) -> BaseModel:
        """
        Invoke LLM with structured output using Pydantic schema.
        
        Args:
            prompt: User prompt
            schema: Pydantic model class defining output structure
            system_message: Optional system message
            
        Returns:
            Validated Pydantic model instance
        """
        if not self.supports(ModelCapability.STRUCTURED_OUTPUT):
            raise ValueError(
                f"{self.config.display_name} doesn't support structured output"
            )
        
        try:
            # Create structured LLM
            structured_llm = self.llm.with_structured_output(schema)
            
            # Build messages
            messages = []
            if system_message:
                messages.append(SystemMessage(content=system_message))
            messages.append(HumanMessage(content=prompt))
            
            # Invoke and return structured output
            response = structured_llm.invoke(messages)
            logger.debug(f"Structured output response: {response.model_dump_json(indent=2)}")
            return response
            
        except Exception as e:
            logger.error(f"Failed to get structured output: {e}")
            raise RuntimeError(f"Structured output failed: {e}") from e

    
    @retry(retries=3, delay=1.0, backoff=2.0)
    def invoke_with_tools(
        self,
        prompt: str,
        tools: List,
        system_message: Optional[str] = None,
        max_iterations: int = 5
    ) -> dict:
        """
        Invoke LLM with tools in agentic loop.

        Args:
            prompt: User prompt
            tools: List of tools to bind
            system_message: Optional system message
            max_iterations: Maximum tool call rounds (default: 5)
            
        Returns:
            {
                "answer": "final response" or None,
                "tool_calls": [{"tool": str, "args": dict, "result": any}],
                "iterations": int
            }
        """
        if not self.supports(ModelCapability.TOOL_CALLING):
            raise ValueError(
                f"{self.config.display_name} doesn't support tool calling"
            )
        
        # Bind tools to LLM
        llm_with_tools = self.bind_tools(tools)
        tool_map = {t.name: t for t in tools}
            
        # Build messages
        messages = []
        if system_message:
            messages.append(SystemMessage(content=system_message))
        messages.append(HumanMessage(content=prompt))

        tool_history = []

        for i in range(max_iterations):
            response = llm_with_tools.invoke(messages)

            # No tool calls = done
            if not response.tool_calls:
                return {
                    "answer": response.content,
                    "tool_calls": tool_history,
                    "iterations": i + 1
                }

            # Add AI response to messages
            messages.append(response)
                
            # Execute tool calls
            for tool_call in response.tool_calls:
                tool_name = tool_call.name
                tool_args = tool_call.args
                tool_id = tool_call.id
                    
                logger.debug(f"Calling tool: {tool_name}({tool_args})")
                    
                # Execute tool
                tool = tool_map.get(tool_name)
                if not tool:
                    result = f"Error: Unknown tool '{tool_name}'"
                    logger.error(result)
                else:
                    try:
                        result = tool.invoke(tool_args)
                    except Exception as e:
                        result = f"Error: {str(e)}"
                        logger.error(f"Tool '{tool_name}' failed: {e}")
                # Record in history
                tool_history.append({
                    "tool": tool_name,
                    "args": tool_args,
                    "result": result
                })

                # Add tool result to messages
                messages.append(
                    ToolMessage(
                        content=str(result),
                        tool_call_id=tool_id
                    )
                )

            logger.debug(f"Iteration {i+1}: {len(response.tool_calls)} tool calls")
            
        raise RuntimeError(
            f"Max iterations ({max_iterations}) reached without final answer."
        )

    @retry(retries=3, delay=1.0, backoff=2.0)
    def invoke_with_reasoning(
        self,
        prompt: str,
        system_message: Optional[str] = None,
    ) -> str:
        """
        Invoke reasoning model (phi4-mini-reasoning).
        
        Extracts answer from <solution> tags, logs full reasoning chain.
        
        Args:
            prompt: Problem to solve
            system_message: Optional system message
            
        Returns:
            Final answer extracted from <solution> tags
        """
        if not self.supports(ModelCapability.REASONING):
            raise ValueError(
                f"{self.config.display_name} doesn't support reasoning"
            )
        
        try:
            # Build messages
            messages = []
            if system_message:
                messages.append(SystemMessage(content=system_message))
            messages.append(HumanMessage(content=prompt))
            
            # Invoke and get full response
            response = self.llm.invoke(messages)
            
            # Eliminate <think> tags from response
            answer = self._extract_answer(response.content)
            
            # Log full reasoning chain
            logger.debug(f"Reasoning complete for: {prompt}")
            logger.debug(f"Full response:\n{response.content}")
            logger.debug(f"Extracted answer: {answer}")
            
            return answer
            
        except Exception as e:
            logger.error(f"Failed to get reasoning: {e}")
            raise RuntimeError(f"Reasoning failed: {e}") from e

    def _extract_answer(self, text: str) -> str:
        """
        Extract answer from <solution> tags using regex.
        
        Args:
            text: Full response text
            
        Returns:
            Answer text, or original text if no tags found
        """
        import re

        if '</think>' in text.lower():
            parts = re.split(r'</think>', text, flags=re.IGNORECASE)
            if len(parts) > 1:
                return parts[-1].strip()
        
        return text.strip()

    def invoke_knowledge_graph(self, prompt: str) -> str:
        """
        Invoke knowledge graph model (triplex).
        
        Args:
            prompt: Prompt for knowledge graph extraction
            system_message: Optional system message
            
        Returns:
            Knowledge graph response
        """
        if not self.supports(ModelCapability.KNOWLEDGE_GRAPH):
            raise ValueError(
                f"{self.config.display_name} doesn't support knowledge graph"
            )
        
        try:
            # Invoke and get response
            response = self.llm.invoke([
                {'role': 'user', 'content': prompt}
            ])
            
            # Log response
            logger.debug(f"Knowledge graph complete for: {prompt}")
            logger.debug(f"Full response:\n{response.content}")
            
            return response.content
            
        except Exception as e:
            logger.error(f"Failed to get knowledge graph: {e}")
            raise RuntimeError(f"Knowledge graph failed: {e}") from e