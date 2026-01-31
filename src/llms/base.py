from abc import ABC, abstractmethod
from typing import Optional, List, Type
from pydantic import BaseModel


class LLM(ABC):
    """
    Abstract base class for LLM implementations.
    
    All LLM providers (Mistral, OpenAI, Ollama, etc.) should inherit from this.
    """
    
    @property
    @abstractmethod
    def model_name(self) -> str:
        """Return the model name."""
        pass
    
    @abstractmethod
    def invoke(
        self,
        prompt: str,
        system_message: Optional[str] = None
    ) -> str:
        """
        Invoke LLM with a simple prompt.
        
        Args:
            prompt: User prompt
            system_message: Optional system message
            
        Returns:
            Generated text response
        """
        pass
    
    @abstractmethod
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
        pass
    
    def bind_tools(self, tools: List) -> "LLM":
        """
        Bind tools to LLM for tool calling.
        
        Args:
            tools: List of @tool decorated functions
            
        Returns:
            LLM with tools bound
            
        Note:
            Override in subclasses that support tool calling.
        """
        raise NotImplementedError(f"{self.__class__.__name__} does not support tool binding")