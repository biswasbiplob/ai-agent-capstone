import os
from google.adk.models.google_llm import Gemini
from google.genai import types, Client
from typing import Optional

from functools import cached_property

class CustomGemini(Gemini):
    """
    Custom Gemini wrapper to force the correct base URL for Google GenAI.
    This bypasses the default ADK behavior which might be trying to use a proxy.
    """
    def __init__(self, **kwargs):
        print(f"CustomGemini instantiated with {kwargs}")
        super().__init__(**kwargs)

    @cached_property
    def api_client(self) -> Client:
        # Override to force base_url for non-streaming requests
        api_key = os.getenv("GOOGLE_API_KEY")
        print(f"CustomGemini: Initializing api_client with API Key present={bool(api_key)}")
        return Client(
            api_key=api_key,
            http_options=types.HttpOptions(
                api_version='v1beta',
                base_url='https://generativelanguage.googleapis.com'
            )
        )

    @cached_property
    async def generate_content(self, model, contents, config=None):
        print(f"DEBUG: CustomGemini.generate_content called with contents: {contents}")
        return await self.api_client.aio.models.generate_content(
            model=model, contents=contents, config=config
        )

    @cached_property
    def _live_api_client(self) -> Client:
        # Override to force base_url
        api_key = os.getenv("GOOGLE_API_KEY")
        print(f"CustomGemini: Initializing client with API Key present={bool(api_key)}")
        return Client(
            api_key=api_key,
            http_options=types.HttpOptions(
                api_version='v1beta',
                base_url='https://generativelanguage.googleapis.com'
            )
        )
