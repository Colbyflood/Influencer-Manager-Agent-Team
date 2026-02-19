"""Anthropic client factory and model configuration for the negotiation agent."""

from anthropic import Anthropic

# Model selection: Haiku for fast/cheap classification, Sonnet for nuanced composition
INTENT_MODEL = "claude-haiku-4-5-20250929"
COMPOSE_MODEL = "claude-sonnet-4-5-20250929"

# Configuration constants
DEFAULT_CONFIDENCE_THRESHOLD = 0.70
DEFAULT_MAX_ROUNDS = 5


def get_anthropic_client() -> Anthropic:
    """Create an Anthropic client using API key from environment.

    The Anthropic() constructor reads ANTHROPIC_API_KEY from the environment
    automatically. No explicit key parameter is needed.

    Returns:
        Configured Anthropic client instance.
    """
    return Anthropic()
