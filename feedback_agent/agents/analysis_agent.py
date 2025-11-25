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

class AnalysisAgent:
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
            name='analysis_agent',
            description='An agent that analyzes graded exams to identify weaknesses by identifying CONCEPTS being tested, not question text.',
            instruction='''
            You are an expert educational analyst.
            Your task is to analyze a graded exam and identify the student's weak areas by identifying the CONCEPTS/TOPICS being tested, not the question text.

            Input will be:
            1. ORIGINAL EXAM CONTENT (the questions being asked)
            2. GRADED EXAM DATA (scores, corrections, feedback showing what the student got wrong)

            Your analysis process:
            STEP 1: Read each question in the ORIGINAL EXAM CONTENT
            STEP 2: For each question, identify what CONCEPT/TOPIC it is testing (e.g., "Newton's Laws", "Square Roots", "Cell Biology")
            STEP 3: Create a list of ALL topics/concepts tested in the exam (regardless of whether student got them right or wrong)
            STEP 4: Review the GRADED EXAM DATA to see which questions the student got wrong
            STEP 5: For each wrong answer, extract the CONCEPT/TOPIC (not the question text) as the weakness

            Output must be a JSON object with the following structure:
            {
                "topics": [<str>] (ALL concepts/topics tested in this exam, even if student got them correct),
                "weaknesses": [
                    {
                        "topic": <str> (the CONCEPT being tested, NOT the question text),
                        "description": <str> (explain what the student got wrong),
                        "severity": <str> (low, medium, or high)
                    }
                ],
                "summary": <str> (overall analysis of student performance)
            }

            CRITICAL RULES - TOPIC FIELD:
            - The "topic" field MUST be a CONCEPT NAME, never the question text
            - BAD: "Calculate force: mass = 10kg, acceleration = 5m/s²" (this is question text)
            - GOOD: "Force Calculations" or "Newton's Second Law" (these are concepts)
            - BAD: "What is the speed of light?" (this is question text)
            - GOOD: "Speed of Light" or "Fundamental Constants" (these are concepts)
            - BAD: "Who discovered America?" (this is question text)
            - GOOD: "Age of Exploration" or "Historical Discoveries" (these are concepts)

            EXAMPLES:
            Example 1:
            Exam has 3 questions: Force calculation (wrong), Speed of light (correct), Kinetic energy (correct)
            Output:
            {
                "topics": ["Force Calculations", "Speed of Light", "Kinetic Energy"],
                "weaknesses": [{
                    "topic": "Force Calculations",
                    "description": "Student made calculation error",
                    "severity": "medium"
                }],
                "summary": "Strong understanding of physics concepts, minor calculation error"
            }

            Example 2:
            Question: "What is the square root of 16?"
            Correct topic: "Square Roots" or "Radical Expressions"
            WRONG topic: "What is the square root of 16?" (don't copy the question!)

            CRITICAL: The "topics" list must include ALL concepts tested, not just the ones with errors.
            Focus on identifying the underlying CONCEPTS the student was tested on, not repeating the question text.
            '''
        )

        # Define JSON schema to enforce structure
        response_schema = types.Schema(
            type=types.Type.OBJECT,
            properties={
                "topics": types.Schema(
                    type=types.Type.ARRAY,
                    description="ALL concepts/topics tested in this exam (required, even if empty)",
                    items=types.Schema(type=types.Type.STRING)
                ),
                "weaknesses": types.Schema(
                    type=types.Type.ARRAY,
                    description="Student weaknesses (empty if perfect score)",
                    items=types.Schema(
                        type=types.Type.OBJECT,
                        properties={
                            "topic": types.Schema(type=types.Type.STRING, description="Concept being tested"),
                            "description": types.Schema(type=types.Type.STRING, description="What student got wrong"),
                            "severity": types.Schema(type=types.Type.STRING, description="low, medium, or high")
                        },
                        required=["topic", "description", "severity"]
                    )
                ),
                "summary": types.Schema(type=types.Type.STRING, description="Overall analysis")
            },
            required=["topics", "weaknesses", "summary"]
        )

        self.agent.generate_content_config = types.GenerateContentConfig(
            response_mime_type='application/json',
            response_schema=response_schema
        )

    def analyze_performance(
        self,
        graded_exam: Dict[str, Any],
        exam_content: str = None
    ) -> Dict[str, Any]:
        """
        Analyze a graded exam to identify student weaknesses.

        Args:
            graded_exam: Graded exam data with scores and corrections
            exam_content: Original exam content (questions and topics being tested)

        Returns:
            Dictionary with weaknesses and summary
        """
        # If no exam_content provided, log warning and proceed with graded_exam only
        if not exam_content:
            logger.warning("No exam_content provided to AnalysisAgent. Topic identification may be limited.")
            prompt = f"""
            Please analyze the following graded exam to identify weaknesses.

            --- GRADED EXAM DATA ---
            {json.dumps(graded_exam, indent=2)}
            """
        else:
            prompt = f"""
            Please analyze the exam to identify student weaknesses.

            --- ORIGINAL EXAM CONTENT ---
            {exam_content}

            --- GRADED EXAM DATA ---
            {json.dumps(graded_exam, indent=2)}

            Remember to:
            1. First identify all topics tested in the ORIGINAL EXAM CONTENT
            2. Then match student errors to those specific topics
            3. Use specific topic names from the exam, not generic categories
            """

        from feedback_agent.utils import run_agent
        response_text = run_agent(self.agent, prompt + "\n\nProvide the output as a valid JSON string.")

        try:
            text = response_text
            start = text.find('{')
            end = text.rfind('}') + 1
            if start != -1 and end != -1:
                json_str = text[start:end]
                result = json.loads(json_str)

                # Ensure topics field exists (even if empty)
                if "topics" not in result:
                    result["topics"] = []

                # Normalize topics to ensure consistent structure (list of strings)
                if isinstance(result["topics"], list):
                    result["topics"] = [str(topic) for topic in result["topics"]]

                # Normalize weaknesses to ensure consistent structure
                if "weaknesses" in result:
                    normalized_weaknesses = []
                    for weakness in result["weaknesses"]:
                        if isinstance(weakness, str):
                            # Convert string weaknesses to structured format
                            normalized_weaknesses.append({
                                "topic": weakness,
                                "description": "",
                                "severity": "medium"
                            })
                        elif isinstance(weakness, dict):
                            # Ensure all required fields exist
                            normalized_weaknesses.append({
                                "topic": weakness.get("topic", "Unknown"),
                                "description": weakness.get("description", ""),
                                "severity": weakness.get("severity", "medium")
                            })
                    result["weaknesses"] = normalized_weaknesses

                return result
            else:
                raise ValueError("No JSON found in response")
        except Exception as e:
            logger.error(f"Error parsing analysis response: {e}")
            logger.error(f"Response text: {response_text}")
            return {
                "weaknesses": [],
                "summary": "Error analyzing performance."
            }
