"""OpenAI embedding utilities for SueChef."""

from typing import List
import openai


async def get_embedding(text: str, openai_client: openai.AsyncOpenAI) -> List[float]:
    """Get OpenAI embedding for text."""
    response = await openai_client.embeddings.create(
        input=text,
        model="text-embedding-3-small"
    )
    return response.data[0].embedding