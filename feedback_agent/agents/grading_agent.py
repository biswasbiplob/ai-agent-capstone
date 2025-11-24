
from google.adk.agents.llm_agent import Agent
from typing import Dict, Any
from google.genai import types

import logging

# Configure logging
logger = logging.getLogger(__name__)

from feedback_agent.custom_llm import CustomGemini

class GradingAgent:
    def __init__(self, model: str = 'gemini-2.5-pro'):
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
        self.agent.generate_content_config = types.GenerateContentConfig(response_mime_type='application/json')

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
        
        # Simple cleanup to ensure we get the JSON part if there's extra text
        try:
            import json
            start = response_text.find('{')
            end = response_text.rfind('}') + 1
            if start != -1 and end != -1:
                json_str = response_text[start:end]
                return json.loads(json_str)
            else:
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

