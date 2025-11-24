
import os
from google.adk.models.google_llm import Gemini
from google.genai import types, Client
from dotenv import load_dotenv

load_dotenv("feedback_agent/.env")

class CustomGemini(Gemini):
    @property
    def _live_api_client(self) -> Client:
        # Override to force base_url
        return Client(
            api_key=os.getenv("GOOGLE_API_KEY"),
            http_options=types.HttpOptions(
                api_version='v1beta',
                base_url='https://generativelanguage.googleapis.com'
            )
        )

try:
    # Instantiate CustomGemini
    # Gemini(model='...')
    llm = CustomGemini(model="gemini-2.0-flash-exp")
    print("CustomGemini instantiated")
    
    # Test connection if possible, but just instantiation and passing to Agent is enough for now.
    from google.adk.agents.llm_agent import Agent
    
    # Agent takes 'model' which can be a BaseLlm instance
    agent = Agent(model=llm, name="test")
    print("Agent instantiated with CustomGemini")
    
    # If we want to really test it, we need to run it, but that requires context etc.
    # But if this runs without error, it means the structure is correct.

except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
