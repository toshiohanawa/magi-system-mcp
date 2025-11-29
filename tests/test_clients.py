import pytest

from magi.clients import CodexClient, ClaudeClient, GeminiClient
from magi.models import ModelOutput


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "client_cls",
    [CodexClient, ClaudeClient, GeminiClient],
)
async def test_clients_return_model_output(client_cls):
    client = client_cls()
    output = await client.generate("Hello")
    assert isinstance(output, ModelOutput)
    assert output.model
    assert isinstance(output.content, str)
