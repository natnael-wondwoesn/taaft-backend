# app/chat/llm_service.py
"""
LLM service for chat feature
Handles interaction with different LLM providers based on the requested model
"""
import os
import json
import httpx
from typing import Dict, List, Optional, Union, Any
from enum import Enum
import openai
from .models import ChatModelType, MessageRole
from ..logger import logger
import aiohttp

# Default system prompt if none is provided
DEFAULT_SYSTEM_PROMPT = """You are a helpful AI assistant for TAAFT, an AI tool discovery platform. 
You can help users find appropriate AI tools for their needs, explain AI concepts, and provide general assistance.
Be concise, accurate, and helpful."""


class LLMService:
    """Service for interacting with LLM providers"""

    def __init__(self):
        """Initialize the LLM service with API keys from environment variables"""
        # OpenAI settings
        self.openai_api_key = os.getenv("OPENAI_API_KEY", "")

        # Anthropic settings
        self.anthropic_api_key = os.getenv("ANTHROPIC_API_KEY", "")

        # Llama settings
        self.llama_api_url = os.getenv("LLAMA_API_URL", "http://localhost:8000")

        # Model mappings
        self.model_map = {
            ChatModelType.GPT_4: "gpt-4-turbo-preview",
            ChatModelType.CLAUDE: "claude-3-opus-20240229",
            ChatModelType.LLAMA: "meta/llama-3-8b-instruct",  # Example, would be used with local or other API
            ChatModelType.DEFAULT: "gpt-3.5-turbo",  # Default fallback model
        }

        # Configure OpenAI client if key is available
        if self.openai_api_key:
            openai.api_key = self.openai_api_key

    async def get_llm_response(
        self, messages, model_type=ChatModelType.DEFAULT, system_prompt=None
    ):
        """Get a response from the LLM service"""
        # Include system prompt if provided
        if system_prompt:
            formatted_messages = [
                {"role": "system", "content": system_prompt}
            ] + messages
        else:
            formatted_messages = messages

        logger.info(f"Getting LLM response with model: {model_type}")

        # Use appropriate model client based on model_type
        if model_type == ChatModelType.GPT_4:
            return await self._get_openai_response(formatted_messages, model="gpt-4")
        elif model_type == ChatModelType.CLAUDE:
            return await self._get_anthropic_response(formatted_messages)
        elif model_type == ChatModelType.LLAMA:
            return await self._get_llama_response(formatted_messages)
        else:
            # Default to a configured fallback model
            fallback_model = os.getenv("DEFAULT_LLM_MODEL", "gpt-3.5-turbo")
            return await self._get_openai_response(
                formatted_messages, model=fallback_model
            )

    async def get_streaming_llm_response(
        self, messages, model_type=ChatModelType.DEFAULT, system_prompt=None
    ):
        """Get a streaming response from the LLM service, yielding chunks as they arrive"""
        # Include system prompt if provided
        if system_prompt:
            formatted_messages = [
                {"role": "system", "content": system_prompt}
            ] + messages
        else:
            formatted_messages = messages

        logger.info(f"Getting streaming LLM response with model: {model_type}")

        # Use appropriate model client based on model_type
        if model_type == ChatModelType.GPT_4:
            async for chunk in self._get_openai_streaming_response(
                formatted_messages, model="gpt-4"
            ):
                yield chunk
        elif model_type == ChatModelType.CLAUDE:
            async for chunk in self._get_anthropic_streaming_response(
                formatted_messages
            ):
                yield chunk
        elif model_type == ChatModelType.LLAMA:
            async for chunk in self._get_llama_streaming_response(formatted_messages):
                yield chunk
        else:
            # Default to a configured fallback model
            fallback_model = os.getenv("DEFAULT_LLM_MODEL", "gpt-3.5-turbo")
            async for chunk in self._get_openai_streaming_response(
                formatted_messages, model=fallback_model
            ):
                yield chunk

    async def _get_openai_streaming_response(self, messages, model="gpt-3.5-turbo"):
        """Get a streaming response from OpenAI"""
        try:
            client = openai.AsyncOpenAI(api_key=self.openai_api_key)

            response = await client.chat.completions.create(
                model=model,
                messages=[
                    {"role": m["role"], "content": m["content"]} for m in messages
                ],
                stream=True,
            )
            print(response)

            async for chunk in response:
                if chunk.choices and chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content

        except Exception as e:
            logger.error(f"Error getting streaming OpenAI response: {str(e)}")
            raise

    # async def _get_anthropic_streaming_response(self, messages):
    #     """Get a streaming response from Anthropic Claude"""
    #     try:
    #         from anthropic import AsyncAnthropic

    #         client = AsyncAnthropic(api_key=self.anthropic_api_key)

    #         # Convert messages to Claude format
    #         system_prompt = None
    #         user_messages = []

    #         for msg in messages:
    #             if msg["role"] == "system":
    #                 system_prompt = msg["content"]
    #             else:
    #                 user_messages.append(msg)

    #         # Format messages for Claude
    #         formatted_messages = []
    #         for i, msg in enumerate(user_messages):
    #             role = "user" if msg["role"] == "user" else "assistant"
    #             formatted_messages.append({"role": role, "content": msg["content"]})

    #         response = await client.messages.create(
    #             model="claude-3-opus-20240229",
    #             messages=formatted_messages,
    #             system=system_prompt,
    #             stream=True,
    #             max_tokens=1024,
    #         )

    #         async for chunk in response:
    #             if chunk.delta and chunk.delta.text:
    #                 yield chunk.delta.text

    #     except Exception as e:
    #         logger.error(f"Error getting streaming Anthropic response: {str(e)}")
    #         raise

    async def _get_llama_streaming_response(self, messages):
        """Get a streaming response from self-hosted Llama model"""
        try:
            # Convert messages to Llama format
            llama_messages = []

            for msg in messages:
                if msg["role"] == "system":
                    llama_messages.append({"role": "system", "content": msg["content"]})
                elif msg["role"] == "user":
                    llama_messages.append({"role": "user", "content": msg["content"]})
                else:
                    llama_messages.append(
                        {"role": "assistant", "content": msg["content"]}
                    )

            # Make request to local Llama endpoint
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.llama_api_url}/v1/chat/completions",
                    json={
                        "messages": llama_messages,
                        "stream": True,
                        "max_tokens": 1024,
                    },
                    headers={"Content-Type": "application/json"},
                ) as response:
                    # Stream response chunks
                    if response.status == 200:
                        async for line in response.content:
                            line = line.decode("utf-8").strip()
                            if line.startswith("data: ") and not line.startswith(
                                "data: [DONE]"
                            ):
                                try:
                                    data = json.loads(line[6:])
                                    if (
                                        "choices" in data
                                        and data["choices"]
                                        and "delta" in data["choices"][0]
                                    ):
                                        delta = data["choices"][0]["delta"]
                                        if "content" in delta and delta["content"]:
                                            yield delta["content"]
                                except json.JSONDecodeError:
                                    logger.warning(f"Failed to parse line: {line}")
                                    continue
                    else:
                        error_text = await response.text()
                        logger.error(
                            f"Llama API error: {response.status}, {error_text}"
                        )
                        raise Exception(
                            f"Llama API error: {response.status}, {error_text}"
                        )

        except Exception as e:
            logger.error(f"Error getting streaming Llama response: {str(e)}")
            raise

    async def _get_openai_response(
        self,
        messages: List[Dict[str, str]],
        model: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
    ) -> str:
        """Get response from OpenAI API"""
        if not self.openai_api_key:
            return "OpenAI API key not configured. Please set the OPENAI_API_KEY environment variable."

        try:
            # Prepare the messages list
            formatted_messages = []

            # Add system prompt if provided, otherwise use default
            sys_prompt = system_prompt if system_prompt else DEFAULT_SYSTEM_PROMPT
            formatted_messages.append({"role": "system", "content": sys_prompt})

            # Add the chat history
            for msg in messages:
                formatted_messages.append(
                    {"role": msg["role"], "content": msg["content"]}
                )

            # Make the API call with the new API format
            client = openai.AsyncOpenAI(api_key=self.openai_api_key)
            response = await client.chat.completions.create(
                model=model,
                messages=formatted_messages,
                temperature=temperature,
                max_tokens=max_tokens,
                n=1,
            )

            # Extract and return the response text
            return response.choices[0].message.content

        except Exception as e:
            logger.error(f"OpenAI API error: {str(e)}")
            raise

    async def _get_anthropic_response(
        self,
        messages: List[Dict[str, str]],
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
    ) -> str:
        """Get response from Anthropic API"""
        if not self.anthropic_api_key:
            return "Anthropic API key not configured. Please set the ANTHROPIC_API_KEY environment variable."

        try:
            # Prepare the messages list
            formatted_messages = []

            # Add the chat history
            for msg in messages:
                formatted_messages.append(
                    {"role": msg["role"], "content": msg["content"]}
                )

            # Get the model to use
            model = self.model_map[ChatModelType.CLAUDE]

            # Set system prompt
            sys_prompt = system_prompt if system_prompt else DEFAULT_SYSTEM_PROMPT

            # Make the API call using httpx
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    "https://api.anthropic.com/v1/messages",
                    headers={
                        "x-api-key": self.anthropic_api_key,
                        "anthropic-version": "2023-06-01",
                        "content-type": "application/json",
                    },
                    json={
                        "model": model,
                        "messages": formatted_messages,
                        "system": sys_prompt,
                        "temperature": temperature,
                        "max_tokens": max_tokens or 1024,
                    },
                )

                # Raise exception for bad responses
                response.raise_for_status()

                # Parse the response
                response_data = response.json()

                # Return the content
                return response_data["content"][0]["text"]

        except Exception as e:
            logger.error(f"Anthropic API error: {str(e)}")
            raise

    async def _get_llama_response(
        self,
        messages: List[Dict[str, str]],
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
    ) -> str:
        """Get a response from self-hosted Llama model"""
        # This is a placeholder implementation
        # In a real scenario, you'd connect to a local server running Llama,
        # or use a service like Replicate, Together AI, etc.

        logger.warning(
            "Llama implementation is a placeholder. Configure with your chosen Llama provider."
        )
        return "Llama model support is not fully implemented. Please choose a different model or configure Llama API access."

    async def generate_stream(
        self, messages, system_prompt=None, model=ChatModelType.DEFAULT
    ):
        """
        Generate a streaming response from the LLM.
        This method is used by the WebSocket interface to stream responses.
        It's an alias for get_streaming_llm_response to maintain API compatibility.
        """
        async for chunk in self.get_streaming_llm_response(
            messages=messages, model_type=model, system_prompt=system_prompt
        ):
            yield chunk

    def estimate_tokens(self, text: str) -> int:
        """
        Estimate the number of tokens in a text string.
        This is a simple approximation - each word is roughly 1.3 tokens.
        """
        # A simple approximation: ~4 chars per token for English text
        return len(text) // 4 or 1  # Ensure at least 1 token is counted


# Create a singleton instance of the LLM service
llm_service = LLMService()
