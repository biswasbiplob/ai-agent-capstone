
from google.adk.agents.llm_agent import Agent
from typing import Dict, Any
from google.genai import types

import logging
import os
from dotenv import load_dotenv

# Configure logging
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

from feedback_agent.custom_llm import CustomGemini
from feedback_agent.json_utils import parse_json_payload

class GradingAgent:
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
            name='grading_agent',
            description='An agent that grades exams based on an answer key.',
            instruction='''
            You are an expert grader.
            Your task is to grade a student's exam based on the provided answer key.
            
            The exam content and answer key are available in the session state.
            Access them using the session state variables:
            - exam_content: The student's exam with their answers
            - answer_key: The correct answers
            
            Compare the student's answers with the correct answers and calculate the score.
            
            Output must be a JSON object with the following structure:
            {
                "total_score": <number>,
                "max_score": <number>,
                "corrections": [
                    {
                        "question": <str>,
                        "student_answer": <str>,
                        "correct_answer": <str>,
                        "is_correct": <boolean>,
                        "feedback": <str>
                    }
                ],
                "general_feedback": <str>
            }
            '''
        )
        response_schema = types.Schema(
            type=types.Type.OBJECT,
            properties={
                "total_score": types.Schema(type=types.Type.NUMBER),
                "max_score": types.Schema(type=types.Type.NUMBER),
                "corrections": types.Schema(
                    type=types.Type.ARRAY,
                    items=types.Schema(
                        type=types.Type.OBJECT,
                        properties={
                            "question": types.Schema(type=types.Type.STRING),
                            "student_answer": types.Schema(type=types.Type.STRING),
                            "correct_answer": types.Schema(type=types.Type.STRING),
                            "is_correct": types.Schema(type=types.Type.BOOLEAN),
                            "feedback": types.Schema(type=types.Type.STRING),
                            "score": types.Schema(type=types.Type.NUMBER),
                        },
                        required=[
                            "question",
                            "student_answer",
                            "correct_answer",
                            "is_correct",
                            "feedback",
                        ],
                    ),
                ),
                "general_feedback": types.Schema(type=types.Type.STRING),
            },
            required=["total_score", "max_score", "corrections", "general_feedback"],
        )

        self.agent.generate_content_config = types.GenerateContentConfig(
            response_mime_type='application/json',
            response_schema=response_schema,
        )

    def grade_exam(self, exam_content: str, answer_key: str) -> Dict[str, Any]:
        logger.info("GradingAgent.grade_exam called.")
        logger.debug(f"exam_content length: {len(exam_content)}")
        logger.debug(f"answer_key length: {len(answer_key)}")

        prompt = f"""
        You are grading an exam.
        
        Input Data:
        {exam_content}
        
        If the input is a JSON object containing 'exam_content' and 'answer_key', use those.
        Otherwise, treat the input as the exam content and use the provided answer key if available.
        
        HERE IS THE ANSWER KEY (if provided separately):
        =========================================
        {answer_key}
        =========================================
        
        Grade the exam now. Output JSON only.
        """
        
        logger.debug(f"GradingAgent prompt preview: {prompt[:200]}...")
        
        from feedback_agent.utils import run_agent
        response_text = run_agent(self.agent, prompt + "\n\nProvide the output as a valid JSON string.")
        
        logger.debug(f"GradingAgent raw response: {response_text[:200]}...")
        
        try:
            parsed = parse_json_payload(response_text, "grading_result")
            if parsed:
                return parsed
            raise ValueError("No JSON found in response")
        except Exception as e:
            logger.error(f"Error parsing grading response: {e}")
            logger.error(f"Raw response: {response_text}")
            return {
                "total_score": 0,
                "max_score": 0,
                "corrections": [],
                "general_feedback": "Error parsing grading response."
            }
