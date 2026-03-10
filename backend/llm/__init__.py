from .base import LLMAdapter, Message, ToolDefinition, LLMResponse


def create_adapter(config) -> LLMAdapter:
    provider = config.provider.lower()

    if provider == "ollama":
        from .ollama import OllamaAdapter
        return OllamaAdapter(config)
    elif provider == "openai":
        from .openai import OpenAIAdapter
        return OpenAIAdapter(config)
    elif provider == "openai_compatible":
        from .openai import OpenAIAdapter
        return OpenAIAdapter(config)
    elif provider == "anthropic":
        from .anthropic import AnthropicAdapter
        return AnthropicAdapter(config)
    else:
        raise ValueError(f"Unknown LLM provider: {provider}")


__all__ = ["LLMAdapter", "Message", "ToolDefinition", "LLMResponse", "create_adapter"]
