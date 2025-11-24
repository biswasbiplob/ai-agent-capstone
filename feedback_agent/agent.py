import uuid
from typing import Any, Dict, Optional
import logging
import json

from google.adk.agents.llm_agent import Agent
from google.adk.agents.sequential_agent import SequentialAgent
from google.adk.agents.callback_context import CallbackContext
from google.genai import types

from feedback_agent.agents.analysis_agent import AnalysisAgent
from feedback_agent.agents.grading_agent import GradingAgent
from feedback_agent.agents.recommendation_agent import RecommendationAgent
from feedback_agent.agents.image_processing_agent import ImageProcessingAgent
from feedback_agent.database import StudentDatabase
from feedback_agent.custom_llm import CustomGemini

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class FeedbackSystem:
    def __init__(self, db_path: str = "students.db"):
        self.db = StudentDatabase(db_path)
        # We keep ImageProcessingAgent here as it's stateless/custom
        self.image_processing_agent = ImageProcessingAgent()

    def register_student(self, name: str) -> str:
        student_id = str(uuid.uuid4())
        self.db.add_student(student_id, name)
        logger.info(f"Registered student: {name} ({student_id})")
        return student_id

    def _get_exam_id(self, session_state: Any) -> str:
        if "exam_id" not in session_state:
            session_state["exam_id"] = str(uuid.uuid4())
        return session_state["exam_id"]

    def _log_grading(self, callback_context: CallbackContext) -> None:
        try:
            # Try accessing output from state using output_key
            response_text = callback_context.state.get("grading_output")
            
            if not response_text:
                logger.error(f"Cannot find grading_output in state. Keys: {list(callback_context.state.keys())}")
                return

            grading_result = json.loads(response_text)
            
            exam_id = self._get_exam_id(callback_context.state)
            student_id = callback_context.state.get("student_id", "unknown")
            subject = callback_context.state.get("subject", "Unknown Subject")
            
            logger.info(f"Logging grading result for exam {exam_id}")
            self.db.log_exam(
                exam_id=exam_id,
                student_id=student_id,
                subject=subject,
                total_score=grading_result.get("total_score", 0),
                max_score=grading_result.get("max_score", 0),
            )
        except Exception as e:
            logger.error(f"Error logging grading result: {e}")

    def _log_analysis(self, callback_context: CallbackContext) -> None:
        try:
            response_text = callback_context.state.get("analysis_output")
            if not response_text:
                logger.error("Cannot find analysis_output in state")
                return

            analysis_result = json.loads(response_text)
            exam_id = self._get_exam_id(callback_context.state)
            
            logger.info(f"Logging analysis result for exam {exam_id}")
            self.db.log_analysis(
                exam_id=exam_id,
                weaknesses=analysis_result.get("weaknesses", [])
            )
        except Exception as e:
            logger.error(f"Error logging analysis result: {e}")

    def _log_recommendation(self, callback_context: CallbackContext) -> None:
        try:
            response_text = callback_context.state.get("recommendation_output")
            if not response_text:
                logger.error("Cannot find recommendation_output in state")
                return

            recommendation_result = json.loads(response_text)
            exam_id = self._get_exam_id(callback_context.state)
            
            logger.info(f"Logging recommendation result for exam {exam_id}")
            self.db.log_analysis(
                exam_id=exam_id,
                recommendations=str(recommendation_result)
            )
        except Exception as e:
            logger.error(f"Error logging recommendation result: {e}")

    def process_exam(
        self, student_id: str, subject: Optional[str] = None, exam_content: Optional[str] = None, answer_key: Optional[str] = None, image_path: Optional[str] = None
    ) -> Dict[str, Any]:
        
        # Create fresh instances of agents for this run to avoid parent conflicts
        grading_agent = GradingAgent()
        analysis_agent = AnalysisAgent()
        recommendation_agent = RecommendationAgent()
        
        # Configure Callbacks
        grading_agent.agent.after_agent_callback = self._log_grading
        grading_agent.agent.output_key = "grading_output"
        
        analysis_agent.agent.after_agent_callback = self._log_analysis
        analysis_agent.agent.output_key = "analysis_output"
        
        recommendation_agent.agent.after_agent_callback = self._log_recommendation
        recommendation_agent.agent.output_key = "recommendation_output"

        # Define the pipeline based on input
        if image_path:
            logger.info(f"Processing exam image for student {student_id}...")
            image_result = self.image_processing_agent.process_image(image_path=image_path)
            
            if not subject or subject == "Unknown":
                subject = image_result.get("subject", "Unknown Subject")
            
            extracted_content = image_result.get("exam_content", "")
            extracted_key = image_result.get("answer_key", "")
            
            if not exam_content:
                exam_content = extracted_content
            if not answer_key or answer_key == "Not found":
                answer_key = extracted_key
                
            # Prepare input for GradingAgent
            input_data = json.dumps({
                "exam_content": exam_content,
                "answer_key": answer_key
            })
        else:
            # Text Pipeline
            input_data = f"Exam Content: {exam_content}\nAnswer Key: {answer_key}"

        # Create the Sequential Agent
        pipeline = SequentialAgent(
            name="exam_processing_pipeline",
            sub_agents=[
                grading_agent.agent,
                analysis_agent.agent,
                recommendation_agent.agent
            ]
        )
        
        # Run the pipeline
        logger.info(f"Starting exam processing pipeline for student {student_id}...")
        
        # Generate exam_id here to ensure we can retrieve it
        exam_id = str(uuid.uuid4())
        
        # We need to pass session data
        session_state = {
            "student_id": student_id,
            "subject": subject or "Unknown",
            "exam_id": exam_id, # Pass explicit exam_id
            "exam_content": exam_content,
            "answer_key": answer_key
        }
        
        from feedback_agent.utils import run_agent
        
        # Run the agent with empty input since data is in session_state
        run_agent(pipeline, "", session_state=session_state)
        
        # Fetch the result from the database
        logger.info(f"Fetching results for exam {exam_id}...")
        exam_result = self.db.get_exam(exam_id)
        
        if exam_result:
            return exam_result
        else:
            logger.error(f"Could not find exam result for {exam_id}")
            return {
                "status": "error",
                "message": "Exam processed but results not found in DB."
            }


# Expose a simple interface or the system itself
feedback_system = FeedbackSystem()


# Tools for the root agent
def register_student_tool(name: str) -> str:
    """Registers a new student and returns their ID."""
    return feedback_system.register_student(name)


def process_exam_tool(
    student_id: str, subject: Optional[str] = None, exam_content: Optional[str] = None, answer_key: Optional[str] = None
) -> Dict[str, Any]:
    """
    Processes an exam for a student.
    
    Args:
        student_id: The ID of the student.
        subject: The subject of the exam (optional if image provided).
        exam_content: The text content of the exam (optional if image provided).
        answer_key: The correct answers or rubric (optional if image provided).

    Returns:
        A dictionary containing grading results, analysis, and recommendations.
    """
    logger.info("process_exam_tool called")
    return feedback_system.process_exam(student_id, subject, exam_content, answer_key)


# Root Agent for ADK Web
root_agent = Agent(
    model=CustomGemini(model="gemini-2.5-pro"),
    name="root_agent",
    description="A helpful assistant for teachers to grade exams and provide feedback.",
    instruction="""
    You are a teacher's assistant powered by AI.
    You can help with:
    1. Registering students.
    2. Processing exams (grading, analyzing weaknesses, and recommending learning objectives).
    
    Use the provided tools to perform these actions.
    
    When a user asks to grade an exam:
    1. Ask for the student's name (if not known).
    2. If they provide text, use it.
    3. If they provide an image, try to extract the text and answer key yourself first (as you have vision capabilities), 
       then call `process_exam_tool` with the extracted text.
       
       Note: The system has an internal `ImageProcessingAgent`, but for now, please help by extracting the text 
       if you can see the image directly.
    
    Then register the student (if needed) and process the exam.
    Present the results nicely to the user.
    """,
    tools=[register_student_tool, process_exam_tool],
)
