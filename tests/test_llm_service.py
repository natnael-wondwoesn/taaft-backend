import pytest
import os
import sys
from unittest.mock import patch, AsyncMock, MagicMock
from datetime import datetime
import logging

logger = logging.getLogger(__name__)
# Add the parent directory to sys.path to allow importing from the app
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.chat.llm_service import LLMService
from app.chat.models import ChatModelType, MessageRole


@pytest.fixture
def llm_service():
    """Fixture to create a test instance of LLMService"""
    # Set a mock API key for testing
    with patch.dict(os.environ, {"OPENAI_API_KEY": "test_api_key"}):
        service = LLMService()
        return service


@pytest.mark.asyncio
async def test_get_openai_response(llm_service):
    """Test the _get_openai_response method"""

    # Mock the OpenAI API response
    mock_response = AsyncMock()
    mock_response.choices = [AsyncMock()]
    mock_response.choices[0].message.content = "This is a test response from OpenAI"

    # Make the mock properly awaitable
    mock_acreate = AsyncMock(return_value=mock_response)

    # Create test messages
    messages = [{"role": "user", "content": "Hello, can you help me?"}]

    # Patch the OpenAI ChatCompletion.acreate method
    with patch("openai.ChatCompletion.acreate", mock_acreate):
        response = await llm_service._get_openai_response(
            messages=messages,
            model_type=ChatModelType.DEFAULT,
            system_prompt="You are a test assistant",
        )
        print(response)

        assert response == "This is a test response from OpenAI"

        logger.info(response)


@pytest.mark.asyncio
async def test_get_streaming_llm_response_openai(llm_service):
    """Test the streaming response functionality with OpenAI"""

    # Mock the streaming response chunks
    async def mock_streaming_response(*args, **kwargs):
        # Simulate chunks of a streaming response
        chunks = [
            AsyncMock(choices=[AsyncMock(delta=AsyncMock(content="Hello"))]),
            AsyncMock(choices=[AsyncMock(delta=AsyncMock(content=" world"))]),
            AsyncMock(choices=[AsyncMock(delta=AsyncMock(content="!"))]),
        ]
        for chunk in chunks:
            yield chunk

    # Create test messages
    messages = [{"role": "user", "content": "Hello, can you help me?"}]

    # Create a properly structured mock for AsyncOpenAI client
    mock_client = MagicMock()
    mock_client.chat.completions.create = AsyncMock(
        return_value=mock_streaming_response()
    )

    # Patch the constructor instead of the method directly
    with patch("openai.AsyncOpenAI", return_value=mock_client):
        # Collect the chunks to verify the output
        result = ""
        async for chunk in llm_service._get_openai_streaming_response(
            messages, model="gpt-3.5-turbo"
        ):
            result += chunk

        assert result == "Hello world!"


@pytest.mark.asyncio
async def test_estimate_tokens():
    """Test the token estimation functionality"""
    service = LLMService()

    # Test with empty string
    assert service.estimate_tokens("") == 1  # Should return at least 1

    # Test with short text
    assert service.estimate_tokens("Hello world") == 2  # Approx 2 tokens

    # Test with longer text
    long_text = "This is a longer piece of text that should be approximately 20 tokens based on the simple estimation algorithm used in the service."
    estimated = service.estimate_tokens(long_text)
    assert estimated > 10  # Should be significantly more than 10 tokens

    # The implementation uses len(text) // 4, so we can test the exact value
    assert estimated == len(long_text) // 4


@pytest.mark.asyncio
async def test_get_llm_response_openai(llm_service):
    """Test the get_llm_response method with OpenAI"""

    # Mock the OpenAI response
    mock_response = "This is a test response from the LLM"

    # Create test messages
    messages = [{"role": "user", "content": "Hello, can you help me?"}]

    # Patch the _get_openai_response method
    with patch.object(llm_service, "_get_openai_response", return_value=mock_response):
        response = await llm_service.get_llm_response(
            messages=messages,
            model_type=ChatModelType.DEFAULT,
            system_prompt="You are a test assistant",
        )

        assert response == mock_response


@pytest.mark.asyncio
async def test_generate_stream_openai(llm_service):
    """Test the generate_stream method with OpenAI"""

    # Mock the streaming response chunks
    async def mock_streaming_response(*args, **kwargs):
        chunks = ["Hello", " world", "!"]
        for chunk in chunks:
            yield chunk

    # Create test messages
    messages = [{"role": "user", "content": "Hello, can you help me?"}]

    # Patch the get_streaming_llm_response method
    with patch.object(
        llm_service,
        "get_streaming_llm_response",
        return_value=mock_streaming_response(),
    ):
        # Collect the chunks to verify the output
        result = ""
        async for chunk in llm_service.generate_stream(
            messages=messages,
            model=ChatModelType.DEFAULT,
            system_prompt="You are a test assistant",
        ):
            result += chunk

        assert result == "Hello world!"
