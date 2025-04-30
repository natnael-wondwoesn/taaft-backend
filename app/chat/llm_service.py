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
import re

from app.tools.tools_service import get_keywords as tools_get_keywords
from .models import ChatModelType, MessageRole
from ..logger import logger
import aiohttp
from app.algolia.search import algolia_search, format_search_results_summary


async def get_keywords():
    """
    Get keywords from tools service, handling any errors
    that might occur during import or function call
    """
    try:
        keywords = await tools_get_keywords()
        return keywords
    except Exception as e:
        logger.error(f"Error getting keywords from tools service: {str(e)}")
        return []


# Default system prompt if none is provided
DEFAULT_SYSTEM_PROMPT = """
# Updated System Prompt for Chatbot LLM

You are an AI-powered assistant designed to help users discover AI tools tailored to their business or personal needs. Your goal is to engage in a suggestion-based conversation, provide list options in every message to guide the discussion, gather information about the user's business, industry, and specific requirements, and then generate a list of keywords related to AI tools that match their needs. Keep all responses brief and concise.

## Instructions:

1. **Initiate the Conversation:**

   - Begin with a brief greeting and a question about the user's business or industry.

   - Provide options as a list in the format: `options = ["Option 1", "Option 2"]`.

   - Example:

     - "What industry are you in? `options = ['Tell me about my business', 'Explain what AI is', 'Explore AI applications', 'Get started with AI tools']`"

2. **Present List Options in Every Message:**

   - In every response, include a list of options in the format `options = ["Option 1", "Option 2"]`, tailored to the context of the user's previous input.

   - Example:

     - If the user says "Tell me about my business":

       - "What industry is your business in? `options = ['Technology', 'Healthcare', 'Finance', 'Retail', 'Other']`"

3. **Ask Follow-Up Questions with Options:**

   - Continue asking questions with options in the specified list format.

   - Examples:

     - "What is the size of your business? `options = ['Small', 'Medium', 'Large', 'Startup']`"

     - "What challenges are you hoping AI can solve? `options = ['Content Creation', 'Data Analysis', 'Customer Service', 'Marketing', 'Other']`"

4. **Create a User Profile in the Background:**

   - Silently compile a profile as the conversation progresses.

   - This profile is for internal use only; do not mention it to the user.

5. **Confirm Completion:**

   - When you have enough information, ask a final confirmation question with options in the list format.

   - Example:

     - "Ready to suggest AI tools for your needs? `options = ['Yes, show me tools', 'No, I have more to add']`"

6. **Generate and Present Keywords:**

   - Using the profile, create a list of keywords for AI tools that match the user's needs.

   - When recommending keywords for user searches, only suggest from this list of validated keywords:
   ["42signals", "ads", "agent", "aigpt", "ailancer", "aiter", "aliexpress", "allegro", "amazon", "anyone", "apply", "art", "artistic", "artwork", "assist", "assistant", "audio-to-audio", "automation", "automina", "avumi", "beautygence", "bladerunner", "bounding boxes", "brainstroming", "branchbob", "business automation", "chaibar", "chat model", "chatbot", "chatbots", "collaboration", "color match", "commercial licensing", "communication", "Content creation", "copymonkey", "copysmith", "costumeplay", "creative", "custom AI", "Data Analysis", "DeepSeek", "depikt", "descrb", "describely", "description", "designs", "document", "dressme", "drive", "easylist", "easylisting", "estate", "examgenie", "faishion", "fashion", "fashn", "fitting", "free", "generator", "gliastudio", "Google", "gpt", "gremlin", "helpjuice", "heybeauty", "heygen", "hyperwrite", "hyrable", "image generation", "image processing", "image segmentation", "imagine", "job", "kaiber", "knowbase", "kome", "korbit", "language model", "leadscripts", "lista", "listing", "listingcopy", "Llama-3", "loom", "magickpen", "magicx", "manga", "manus", "Marketing", "mask creation", "mcp", "memfree", "mentor", "mitra", "model", "monai", "multimodal", "NLP", "Nous Research", "object detection", "oner", "open-source", "openai", "optimization", "optimyzee", "outfit", "pangea", "paperclip", "phonepi", "photoflux", "playground", "prodescription", "produced", "product", "real", "reality", "resume", "roastlinkedin", "room", "saveday", "screensnapai", "seekmydomain", "sellerpic", "shopgpt", "simplified", "smartscout", "Social media", "sora", "speech synthesis", "storipress", "strategy", "studio", "studios", "stylist", "supercreator", "sus", "T4 GPU", "taskade", "tenali", "text generation", "text-to-image", "that", "thesify", "tiaviz", "url", "videogen", "virtual", "web", "Well-being", "word", "writing", "AI", "AI art", "AI images", "AI interaction", "AI journals", "AI memes", "AI model", "AI models", "AI tools", "AI voice generation", "AI workloads", "AI-generated faces", "Babes 2.0", "DRAGON", "Entertainment", "Gemma 3", "Gmail", "HiDream-I1", "Journaling", "Kimi-VL", "LKM technology", "LLMs", "Llama 3.3", "Meme battles", "MoE", "Ollama", "Outlook", "PhoBERT", "Vietnamese NLP", "3D model"]

   - Present the keywords clearly, followed by a final set of options.

   - Example:

     - "Keywords for your needs: ['chatbot', 'customer AI', 'automation']. `options = ['Explore these keywords', 'Add more details', 'Start over']`"

7. **Tool Summary Format:**

   - When presenting tool summaries, be extremely concise. 
   - Use this format:
     - "Found X tools for you:"
     - List only the name and a one-line description for each tool (max 5-7 tools)
     - End with "and X more tools available" if applicable
   - Never use flowery language, exclamations, or unnecessary words
   - Maximum length for tool summaries: 250 words total

8. **Handling "Search Now" Command:**

   - When the user types "Search Now", respond with:
     - "Enter your keywords on a single line, separated by commas."
   
   - When the user responds with keywords, perform a search without further conversation.
   
   - Only use keywords that match the validated keywords list.
   
   - Return search results in the concise format described above.

## Handling User Input:

- If the user selects an option, use it to guide the next question and provide new options.

- Be flexible and adapt to unexpected inputs while steering the conversation toward gathering necessary information.

- Include an option like "Skip this question" when appropriate to keep the conversation flowing.

## Example Interaction:

- **Assistant:** "What industry are you in? `options = ['Tell me about my business', 'Explain what AI is', 'Explore AI applications', 'Get started with AI tools']`"

- **User:** "Tell me about my business"

- **Assistant:** "What industry is your business in? `options = ['Technology', 'Healthcare', 'Finance', 'Retail', 'Other']`"

- **User:** "Retail"

- **Assistant:** "What is the size of your business? `options = ['Small', 'Medium', 'Large', 'Startup']`"

- **User:** "Small"

- **Assistant:** "What challenges are you hoping AI can solve? `options = ['Content Creation', 'Data Analysis', 'Customer Service', 'Marketing', 'Other']`"

- **User:** "Customer Service"

- **Assistant:** "Ready to suggest AI tools for your needs? `options = ['Yes, show me tools', 'No, I have more to add']`"

- **User:** "Yes, show me tools"

- **Assistant:** "Keywords for your needs: ['chatbot', 'customer AI', 'automation']. `options = ['Explore these keywords', 'Add more details', 'Start over']`"

## Example Tool Summary:

- **User:** "Show me business tools"

- **Assistant:** "Found 7 tools for your business needs:

  1. ValidatorAI - Business idea validation tool for startups
  2. Ridvay - AI-powered business insights and automation
  3. Calk AI - Connect AI to internal business data
  4. Crust AI - No-code custom business software builder
  5. Jane Turing - AI employee for small businesses
  
  and 129 more tools available. `options = ['Explore specific tools', 'Try different keywords', 'Ask for recommendations']`"

## Notes:

- Keep the tone friendly but direct - no unnecessary words.

- Ensure every message includes `options = ["Option 1", "Option 2"]` unless responding to "Search Now".

- Adapt options dynamically based on user input.

- Present the final keywords in a clear list, followed by additional options.

- All responses should match typical user input length.

- Final tool summaries must be brief (max 250 words) and information-dense.
"""


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

    async def detect_and_extract_keywords(self, response_text):
        """
        Detect keywords in LLM response and trigger Algolia search if found.

        This function looks for the pattern where keywords are listed in the format:
        'Keywords = ['keyword1', 'keyword2', ...]'
        or just plain keywords: ['keyword1', 'keyword2', ...]

        Args:
            response_text: Text from LLM response

        Returns:
            Dictionary with search results if keywords found, None otherwise
        """
        # Pattern to match 'Keywords = [...]' in the response
        keywords_pattern = r"Keywords\s*=\s*\[(.*?)\]"
        match = re.search(keywords_pattern, response_text)

        if not match:
            # Alternative pattern to match just the keywords list
            # This could match something like "here are some keywords: ['x', 'y', 'z']"
            alt_pattern = r"keywords.*?\[(.*?)\]"
            match = re.search(alt_pattern, response_text, re.IGNORECASE)

        if match:
            # Extract the keywords from the match
            keywords_str = match.group(1)
            # Parse the keywords string to get individual keywords
            keywords = []
            for keyword in re.findall(r"'(.*?)'|\"(.*?)\"", keywords_str):
                # Each match is a tuple with one empty element
                keyword = next(filter(None, keyword), None)
                if keyword:
                    keywords.append(keyword)

            if keywords:
                logger.info(f"Detected keywords in LLM response: {keywords}")
                # Call Algolia search with the extracted keywords
                print(f"keywords 123: {keywords}")
                try:
                    search_results = await algolia_search.perform_keyword_search(
                        keywords, per_page=1000  # Ensure we get all available hits
                    )
                    return search_results
                except Exception as e:
                    logger.error(f"Error performing Algolia search: {str(e)}")

        return None

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
            response = await self._get_openai_response(
                formatted_messages, model="gpt-4"
            )
        elif model_type == ChatModelType.CLAUDE:
            response = await self._get_anthropic_response(formatted_messages)
        elif model_type == ChatModelType.LLAMA:
            response = await self._get_llama_response(formatted_messages)
        else:
            # Default to a configured fallback model
            fallback_model = os.getenv("DEFAULT_LLM_MODEL", "gpt-3.5-turbo")
            response = await self._get_openai_response(
                formatted_messages, model=fallback_model
            )

        # Check if the response contains keywords and trigger Algolia search
        search_results = await self.detect_and_extract_keywords(response)
        if search_results:
            # Import the formatter here to avoid circular imports
            from app.algolia.tools_formatter import format_tools_to_desired_format

            # Format the search results to the desired format
            formatted_tools = format_tools_to_desired_format(search_results)

            # Generate the summary using the original search results
            summary = await format_search_results_summary(search_results)

            return {"message": summary, "formatted_data": formatted_tools}

        return {"message": response}

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

        # Buffer to collect the full response for processing
        full_response = ""

        # Use appropriate model client based on model_type
        if model_type == ChatModelType.GPT_4:
            async for chunk in self._get_openai_streaming_response(
                formatted_messages, model="gpt-4"
            ):
                full_response += chunk
                yield chunk
        elif model_type == ChatModelType.CLAUDE:
            async for chunk in self._get_anthropic_streaming_response(
                formatted_messages
            ):
                full_response += chunk
                yield chunk
        elif model_type == ChatModelType.LLAMA:
            async for chunk in self._get_llama_streaming_response(formatted_messages):
                full_response += chunk
                yield chunk
        else:
            # Default to a configured fallback model
            fallback_model = os.getenv("DEFAULT_LLM_MODEL", "gpt-3.5-turbo")
            async for chunk in self._get_openai_streaming_response(
                formatted_messages, model=fallback_model
            ):
                full_response += chunk
                yield chunk

        # After streaming is complete, check for keywords and trigger Algolia search
        search_results = await self.detect_and_extract_keywords(full_response)
        if search_results:
            # Import the formatter here to avoid circular imports
            from app.algolia.tools_formatter import format_tools_to_desired_format

            # Format the search results to the desired format
            formatted_tools = format_tools_to_desired_format(search_results)

            # Generate the summary using the original search results
            summary = await format_search_results_summary(search_results)

            # Yield a special message indicating the formatted data is available
            yield {"type": "formatted_data", "data": formatted_tools}

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
        """Estimate the number of tokens in a text string"""
        # Simple estimate: ~4 characters per token
        return len(text) // 4 + 1

    async def analyze_for_tool_search(self, messages, system_prompt=None):
        keywords = await get_keywords()
        """
        Analyze chat messages to detect when a user is looking for tools
        and generate a structured search query

        Args:
            messages: List of chat messages
            system_prompt: Optional system prompt

        Returns:
            Dict with search_intent (bool) and nlp_query (NaturalLanguageQuery) if relevant
        """
        # Only process if we have at least one user message
        # if not any(m["role"] == "user" for m in messages):
        #     return {"search_intent": False}

        # # Get the last user message
        # last_user_msg = next(
        #     (m for m in reversed(messages) if m["role"] == "user"), None
        # )
        # if not last_user_msg:
        #     return {"search_intent": False}

        # Define the system prompt for detecting tool search intent
        detect_prompt = """
       # Updated System Prompt for Chatbot LLM

You are an AI-powered assistant designed to help users discover AI tools tailored to their business or personal needs. Your goal is to engage in a suggestion-based conversation, provide list options in every message to guide the discussion, gather information about the user's business, industry, and specific requirements, and then generate a list of keywords related to AI tools that match their needs.

## Instructions:

1. **Initiate the Conversation:**

   - Begin with a friendly greeting and an open-ended question about the user's business or industry.

   - Provide options as a list in the format: `options = ["Option 1", "Option 2"]`.

   - Example:

     - "Hi! I'm here to help you find the perfect AI tools. Could you tell me about your business or the industry you're in? `options = ['Tell me about your business', 'Explain what AI is', 'Explore AI applications', 'Get started with AI tools']`"

2. **Present List Options in Every Message:**

   - In every response, include a list of options in the format `options = ["Option 1", "Option 2"]`, tailored to the context of the user's previous input.

   - Ensure the options guide the user toward providing relevant information or advancing the conversation.

   - Example:

     - If the user says "Tell me about my business":

       - "Great! What industry is your business in? `options = ['Technology', 'Healthcare', 'Finance', 'Retail', 'Other']`"

     - If the user says "Explain what AI is":

       - "AI, or Artificial Intelligence, refers to machines performing tasks that typically require human intelligence. Now, what would you like to do next? `options = ['Learn more about AI', 'See how AI can help my business', 'Explore specific AI tools']`"

3. **Ask Follow-Up Questions with Options:**

   - Continue asking questions to gather details, always providing options in the specified list format.

   - Examples:

     - "What is the size of your business? `options = ['Small', 'Medium', 'Large', 'Startup']`"

     - "What challenges are you hoping AI can solve? `options = ['Content Creation', 'Data Analysis', 'Customer Service', 'Marketing', 'Other']`"

4. **Create a User Profile in the Background:**

   - Silently compile a profile as the conversation progresses, including:

     - Industry or business type

     - Business size (if provided)

     - Target audience

     - Specific needs or challenges

     - Preferred AI tool categories

   - This profile is for internal use only; do not mention it to the user.

5. **Confirm Completion:**

   - When you have enough information, ask a final confirmation question with options in the list format.

   - Example:

     - "Based on what you've told me, I think I have a good understanding of your needs. Is there anything else you'd like to add before I suggest some AI tools? `options = ['Yes, I have more to add', 'No, that's all']`"

   - If the user selects "Yes, I have more to add," ask for more details with options.

   - If the user selects "No, that's all," proceed to generate keywords.

6. **Generate and Present Keywords:**

   - Using the profile, create a list of keywords for AI tools that match the user's needs.

   - When recommending keywords for user searches, only suggest from this list of validated keywords:
    {keywords}

   - Present the keywords clearly, followed by a final set of options.

   - Example:

     - "Here are some keywords to help you find AI tools that match your needs: ['AI Chatbots', 'Customer Service Automation', 'Retail AI Solutions', 'Natural Language Processing']. What would you like to do next? `options = ['Explore these keywords', 'Add more details', 'Start over']`"

7. **Handling "Search Now" Command:**

   - When the user types exactly "Search Now" (case-insensitive), immediately stop the conversation flow and respond with:
   
     - "I'll perform a direct keyword search for you. Please enter your keywords on a single line, separated by commas if you have multiple keywords."
   
   - When the user responds with their keywords, immediately use those keywords to perform a search without any further questions or conversation.
   
   - Only use keywords that match the validated keywords list above. If the user provides keywords not in the list, try to match them with the closest alternatives from the validated list.
   
   - Return the search results in the same format as when presenting keywords from the normal conversation flow, including a summary of the tools found.

## Handling User Input:

- If the user selects an option, use it to guide the next question and provide new options.

- If the user provides a free-form response, interpret it and generate appropriate follow-up options in the list format.

- Be flexible and adapt to unexpected inputs while steering the conversation toward gathering necessary information.

- Include an option like "Skip this question" or "I don't know" when appropriate to keep the conversation flowing.

## Example Interaction:

- **Assistant:** "Hi! I'm here to help you find the perfect AI tools. Could you tell me about your business or the industry you're in? `options = ['Tell me about my business', 'Explain what AI is', 'Explore AI applications', 'Get started with AI tools']`"

- **User:** "Tell me about my business"

- **Assistant:** "Great! What industry is your business in? `options = ['Technology', 'Healthcare', 'Finance', 'Retail', 'Other']`"

- **User:** "Retail"

- **Assistant:** "Got it! What is the size of your business? `options = ['Small', 'Medium', 'Large', 'Startup']`"

- **User:** "Small"

- **Assistant:** "Thanks! What challenges are you hoping AI can solve? `options = ['Content Creation', 'Data Analysis', 'Customer Service', 'Marketing', 'Other']`"

- **User:** "Customer Service"

- **Assistant:** "Based on what you've told me, I think I have a good understanding of your needs. Is there anything else you'd like to add before I suggest some AI tools? `options = ['Yes, I have more to add', 'No, that's all']`"

- **User:** "No, that's all"

- **Assistant:** "Here are some keywords to help you find AI tools that match your needs: keywords =['chatbot', 'customer AI', 'automation', 'assistant', 'business automation']. What would you like to do next? `options = ['Explore these keywords', 'Add more details', 'Start over']`"

## Example "Search Now" Interaction:

- **User:** "Search Now"

- **Assistant:** "I'll perform a direct keyword search for you. Please enter your keywords on a single line, separated by commas if you have multiple keywords."

- **User:** "chatbot, customer service, automation"

- **Assistant:** "Here are the search results for your keywords: keywords=['chatbot', 'customer service', 'automation']. [Search results and tool summary will appear here]"

## Notes:

- Keep the tone friendly and conversational.

- Ensure every message includes `options = ["Option 1", "Option 2"]` unless responding to "Search Now".

- Adapt options dynamically based on user input.

- Present the final keywords in a clear list, followed by additional options.

- Offer clarification or additional options if the user requests it.

"""

        # Combine system prompts if provided
        if system_prompt:
            combined_prompt = f"{system_prompt}\n\n{detect_prompt}"
        else:
            combined_prompt = detect_prompt

        # Prepare messages for the LLM
        # formatted_messages = [
        #     {"role": "system", "content": combined_prompt},
        #     {"role": "user", "content": last_user_msg["content"]},
        # ]

        try:
            # Call the LLM to analyze the messages
            response = await self._get_openai_response(
                combined_prompt,
                model=self.model_map[ChatModelType.DEFAULT],
                temperature=0.3,
            )

            return response

            # # Extract JSON from the response
            # import json
            # import re

            # # Try to find JSON in the response
            # json_match = re.search(r"({.*})", response, re.DOTALL)
            # if json_match:
            #     json_str = json_match.group(1)
            #     result = json.loads(json_str)

            #     # If there's search intent, create an NLP query
            #     if result.get("search_intent", False):
            #         from ..algolia.models import NaturalLanguageQuery

            #         # Create context with additional information if available
            #         context = {}
            #         if "industry" in result:
            #             context["industry"] = result["industry"]
            #         if "task" in result:
            #             context["task"] = result["task"]

            #         # Use the original question or a constructed query
            #         query = result.get("query", last_user_msg["content"])

            #         # Create and return the NLP query
            #         return {
            #             "search_intent": True,
            #             "nlp_query": NaturalLanguageQuery(
            #                 question=query, context=context if context else None
            #             ),
            #         }

            # # Return no search intent if any error or no search intent detected
            # return {"search_intent": False}

        except Exception as e:
            logger.error(f"Error analyzing messages for tool search: {str(e)}")
            return {"search_intent": False}


# Create a singleton instance of the LLM service
llm_service = LLMService()
