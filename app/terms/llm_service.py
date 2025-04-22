"""
LLM service for terms feature
Handles interaction with different LLM providers to generate term definitions
"""

import os
import json
from typing import Dict, List, Optional, Union, Any, Tuple
import openai
from .models import TermModelType
from ..logger import logger
import aiohttp

# Default system prompt for term definitions
DEFAULT_TERM_SYSTEM_PROMPT = """You are an AI assistant specialized in providing concise, accurate definitions for technical terms.
When given a term, provide a brief, clear definition and 2-4 practical examples that illustrate the concept.
Your response should be structured as a JSON object with "description" and "examples" fields.
Keep your descriptions under 150 words and focus on clarity. Examples should be concrete, practical, and understandable."""


class TermsLLMService:
    """Service for interacting with LLM providers to generate term definitions"""

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
            TermModelType.GPT_4: "gpt-4-turbo-preview",
            TermModelType.CLAUDE: "claude-3-opus-20240229",
            TermModelType.LLAMA: "meta/llama-3-8b-instruct",  # Example, would be used with local or other API
            TermModelType.DEFAULT: "gpt-3.5-turbo",  # Default fallback model
        }

        # Configure OpenAI client if key is available
        if self.openai_api_key:
            openai.api_key = self.openai_api_key

    async def get_term_definition(
        self, term: str, model_type=TermModelType.DEFAULT
    ) -> Tuple[str, List[str]]:
        """
        Get a definition and examples for a term
        Returns a tuple of (description, examples)
        """
        # Create message with the term request
        messages = [
            {"role": "system", "content": DEFAULT_TERM_SYSTEM_PROMPT},
            {"role": "user", "content": f"Define the term: {term}"},
        ]

        logger.info(f"Getting term definition for '{term}' with model: {model_type}")

        # Use appropriate model client based on model_type
        if model_type == TermModelType.GPT_4:
            response_text = await self._get_openai_response(messages, model="gpt-4")
        elif model_type == TermModelType.CLAUDE:
            response_text = await self._get_anthropic_response(messages)
        elif model_type == TermModelType.LLAMA:
            response_text = await self._get_llama_response(messages)
        else:
            # Default to a configured fallback model
            fallback_model = os.getenv("DEFAULT_LLM_MODEL", "gpt-3.5-turbo")
            response_text = await self._get_openai_response(
                messages, model=fallback_model
            )

        # Parse the response to extract description and examples
        try:
            # Try to parse as JSON
            response_data = json.loads(response_text)
            description = response_data.get("description", "")
            examples = response_data.get("examples", [])

            # Ensure examples is a list
            if isinstance(examples, str):
                examples = [examples]
        except json.JSONDecodeError:
            # If not valid JSON, try to parse the text manually
            logger.warning(f"Failed to parse LLM response as JSON: {response_text}")
            description, examples = self._parse_text_response(response_text)

        return description, examples

    def _parse_text_response(self, text: str) -> Tuple[str, List[str]]:
        """Parse a non-JSON text response into description and examples"""
        lines = text.split("\n")
        description = ""
        examples = []

        # Simple heuristic: first paragraph is description, lines with "Example" are examples
        in_description = True

        for line in lines:
            line = line.strip()
            if not line:
                continue

            if in_description and not line.lower().startswith(("example", "- example")):
                description += line + " "
            else:
                in_description = False
                if line.lower().startswith(
                    ("example", "- example", "* example", "• example")
                ):
                    examples.append(line.split(":", 1)[-1].strip())
                elif examples and line.startswith(("- ", "* ", "• ")):
                    examples.append(line[2:].strip())

        # If we couldn't extract examples but have some text, use the whole thing as description
        if not examples and description:
            # Split the text at 80% as description and the rest as an example
            split_point = int(len(description) * 0.8)
            examples = [description[split_point:].strip()]
            description = description[:split_point].strip()

        return description.strip(), examples

    async def _get_openai_response(
        self,
        messages: List[Dict[str, str]],
        model: str,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
    ) -> str:
        """Get a response from OpenAI"""
        try:
            client = openai.AsyncOpenAI(api_key=self.openai_api_key)

            response = await client.chat.completions.create(
                model=model,
                messages=[
                    {"role": m["role"], "content": m["content"]} for m in messages
                ],
                temperature=temperature,
                max_tokens=max_tokens or 500,
            )

            return response.choices[0].message.content

        except Exception as e:
            logger.error(f"Error getting OpenAI response: {str(e)}")
            raise

    async def _get_anthropic_response(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
    ) -> str:
        """Get a response from Anthropic Claude"""
        try:
            # Handle API request to Anthropic
            # Extract system message if present
            system_prompt = None
            for message in messages:
                if message["role"] == "system":
                    system_prompt = message["content"]
                    break

            # Format messages for Claude API
            anthropic_messages = []
            for msg in messages:
                if (
                    msg["role"] != "system"
                ):  # Skip system message as it's handled separately
                    role = "user" if msg["role"] == "user" else "assistant"
                    anthropic_messages.append({"role": role, "content": msg["content"]})

            headers = {
                "x-api-key": self.anthropic_api_key,
                "content-type": "application/json",
                "anthropic-version": "2023-06-01",
            }

            payload = {
                "model": "claude-3-opus-20240229",
                "messages": anthropic_messages,
                "max_tokens": max_tokens or 500,
                "temperature": temperature,
            }

            if system_prompt:
                payload["system"] = system_prompt

            async with aiohttp.ClientSession() as session:
                async with session.post(
                    "https://api.anthropic.com/v1/messages",
                    headers=headers,
                    json=payload,
                ) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        logger.error(f"Anthropic API error: {error_text}")
                        raise Exception(f"Anthropic API error: {response.status}")

                    response_data = await response.json()
                    return response_data["content"][0]["text"]

        except Exception as e:
            logger.error(f"Error getting Anthropic response: {str(e)}")
            raise

    async def _get_llama_response(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
    ) -> str:
        """Get a response from self-hosted Llama model"""
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
                        "temperature": temperature,
                        "max_tokens": max_tokens or 500,
                    },
                    headers={"Content-Type": "application/json"},
                ) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        logger.error(f"Llama API error: {error_text}")
                        raise Exception(f"Llama API error: {response.status}")

                    response_data = await response.json()
                    return response_data["choices"][0]["message"]["content"]

        except Exception as e:
            logger.error(f"Error getting Llama response: {str(e)}")
            raise


# Create a singleton instance of the service
terms_llm_service = TermsLLMService()
