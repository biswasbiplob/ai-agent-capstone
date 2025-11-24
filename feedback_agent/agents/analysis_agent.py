from google.adk.agents.llm_agent import Agent
from typing import List, Dict, Any
from google.genai import types
import json

import logging

# Configure logging
logger = logging.getLogger(__name__)

from feedback_agent.custom_llm import CustomGemini

class AnalysisAgent:
    def __init__(self, model: str = 'gemini-2.5-pro'):
        self.agent = Agent(
            model=CustomGemini(model=model),
            name='analysis_agent',
            description='An agent that analyzes graded exams to identify weaknesses.',
            instruction='''
            You are an expert educational analyst.
            Your task is to analyze a graded exam and identify the student's weak areas.
            
            Input will be:
            1. Graded Exam Data (Scores, Corrections, Feedback)
            
            Output must be a JSON object with the following structure:
            {
                "weaknesses": [
                    <str> (e.g. "Algebraic Equations", "Historical Dates", "Grammar")
                ],
                "summary": <str>
            }
            
            Focus on identifying the underlying concepts the student struggled with, not just the specific questions.
            '''
        )
        self.agent.generate_content_config = types.GenerateContentConfig(response_mime_type='application/json')

    def analyze_performance(self, graded_exam: Dict[str, Any]) -> Dict[str, Any]:
        prompt = f"""
        Please analyze the following graded exam to identify weaknesses.
        
        --- GRADED EXAM DATA ---
        {json.dumps(graded_exam, indent=2)}
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
            logger.error(f"Error parsing analysis response: {e}")
            return {
                "weaknesses": [],
                "summary": "Error analyzing performance."
            }
