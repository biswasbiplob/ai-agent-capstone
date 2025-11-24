from google.adk.agents.llm_agent import Agent
from typing import List, Dict, Any
from google.genai import types
import json

import logging
import os
from dotenv import load_dotenv

# Configure logging
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

from feedback_agent.custom_llm import CustomGemini

class RecommendationAgent:
    def __init__(self, model: str = None):
        # Get model from environment or use provided value
        if model is None:
            model = os.getenv('MODEL_NAME')
            if not model:
                raise ValueError(
                    "MODEL_NAME must be set in .env file. "
                    "Add MODEL_NAME=<model-name> to feedback_agent/.env "
                    "(e.g., MODEL_NAME=gemini-1.5-flash)"
                )

        self.agent = Agent(
            model=CustomGemini(model=model),
            name='recommendation_agent',
            description='An agent that generates learning recommendations based on student weaknesses.',
            instruction='''
            You are an expert curriculum designer.
            Your task is to create a personalized learning plan for a student based on their identified weaknesses.
            
            Input will be:
            1. List of Weaknesses (from AnalysisAgent)
            
            Output must be a JSON object with the following structure:
            {
                "learning_objectives": [
                    {
                        "topic": <str>,
                        "objective": <str>,
                        "resources": [
                            <str> (e.g. "Read chapter 5", "Watch video X")
                        ]
                    }
                ],
                "encouragement": <str>
            }
            
            Be specific and actionable.
            '''
        )
        self.agent.generate_content_config = types.GenerateContentConfig(response_mime_type='application/json')

    def generate_recommendations(self, weaknesses: List[str]) -> Dict[str, Any]:
        prompt = f"""
        Please generate learning recommendations for the following weaknesses.
        
        --- WEAKNESSES ---
        {json.dumps(weaknesses, indent=2)}
        """
        
        from feedback_agent.utils import run_agent
        response_text = run_agent(self.agent, prompt + "\n\nProvide the output as a valid JSON string.")
        
        try:
            text = response_text
            start = text.find('{')
            end = text.rfind('}') + 1
            if start != -1 and end != -1:
                json_str = text[start:end]
                return json.loads(json_str)
            else:
                raise ValueError("No JSON found in response")
        except Exception as e:
            logger.error(f"Error parsing recommendation response: {e}")
            return {
                "learning_objectives": [],
                "encouragement": "Error generating recommendations."
            }
