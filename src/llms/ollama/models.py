from dataclasses import dataclass
from typing import Optional, List
from enum import Enum

class ModelCapability(Enum):
    TEXT = "text"
    REASONING = "reasoning"
    TOOL_CALLING = "tool_calling"
    STRUCTURED_OUTPUT = "structured_output"
    KNOWLEDGE_GRAPH = "knowledge_graph"


@dataclass
class ModelConfig:
    """Configuration for an Ollama model."""
    name: str
    display_name: str
    capabilities: List[ModelCapability]

    context_length: int = 4096
    default_temperature: float = 0.3


OLLAMA_MODELS = {
    # Reasoning models
    "phi4": ModelConfig(
        name="phi4-mini-reasoning:latest",
        display_name="Phi-4 Mini Reasoning",
        capabilities=[ModelCapability.REASONING],
        context_length=4096,
        default_temperature=0.3
    ),

    # General purpose
    "qwen": ModelConfig(
        name="qwen2.5:3b",
        display_name="Qwen 2.5 (3b)",
        capabilities=[ModelCapability.REASONING, ModelCapability.TEXT, ModelCapability.STRUCTURED_OUTPUT, ModelCapability.TOOL_CALLING],
        context_length=8192
    ),

    # Knowledge graph
    "triplex": ModelConfig(
        name="sciphi/triplex:1.5b",
        display_name="Triplex (1.5b)",
        capabilities=[ModelCapability.KNOWLEDGE_GRAPH],
        context_length=4096,
        default_temperature=0.0
    )
}

def get_model_config(model_key: str) -> ModelConfig:
    """Get model configuration by key."""
    if model_key not in OLLAMA_MODELS:
        raise ValueError(f"Unknown model: {model_key}. Available models: {list(OLLAMA_MODELS.keys())}")
    return OLLAMA_MODELS[model_key]