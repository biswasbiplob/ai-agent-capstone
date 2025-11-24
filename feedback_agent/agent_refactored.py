"""
Refactored FeedbackSystem using proper ADK Runner pattern.

This module replaces the custom run_agent() wrapper with ADK's recommended
Runner/SessionService pattern following the Kaggle course best practices.

Key Improvements:
- Uses proper Runner with DatabaseSessionService
- Agents communicate via output_key and state placeholders
- Async callbacks for database logging
- Proper event streaming and session management
"""

import uuid
import json
import logging
from typing import Any, Dict, Optional

from google.adk.agents import Agent
from google.adk.agents.sequential_agent import SequentialAgent
from google.adk.agents.callback_context import CallbackContext
from google.adk.runners import Runner
from google.adk.sessions import DatabaseSessionService, InMemorySessionService
from google.adk.apps.app import App, EventsCompactionConfig
from google.adk.plugins import LoggingPlugin
from google.genai import types

from feedback_agent.agents.analysis_agent import AnalysisAgent
from feedback_agent.agents.grading_agent import GradingAgent
from feedback_agent.agents.recommendation_agent import RecommendationAgent
from feedback_agent.database import StudentDatabase
from feedback_agent.custom_llm import CustomGemini
from feedback_agent.plugins import ExamMetricsPlugin

# Configure structured logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s',
    handlers=[
        logging.StreamHandler(),  # Console output
        logging.FileHandler('feedback_system.log', mode='a')  # File output
    ]
)
logger = logging.getLogger(__name__)


class FeedbackSystemRefactored:
    """
    Refactored feedback system using proper ADK Runner pattern.

    Architecture:
    - Runner manages session and event flow
    - DatabaseSessionService provides persistent sessions
    - Agents communicate via output_key -> next agent's instruction placeholder
    - Async callbacks handle database logging
    """

    def __init__(
        self,
        db_path: str = "students.db",
        session_db_url: str = "sqlite:///feedback_sessions.db",
        use_memory_sessions: bool = False,
        enable_metrics: bool = True,
        metrics_file: str = "exam_metrics.jsonl"
    ):
        """
        Initialize the feedback system.

        Args:
            db_path: Path to student/exam database
            session_db_url: URL for session storage
            use_memory_sessions: If True, use InMemorySessionService (for testing)
            enable_metrics: If True, enable ExamMetricsPlugin for observability
            metrics_file: Path to metrics file (JSONL format)
        """
        self.db = StudentDatabase(db_path)

        # Create session service (persistent or in-memory)
        if use_memory_sessions:
            self.session_service = InMemorySessionService()
            logger.info("Using InMemorySessionService (sessions won't persist)")
        else:
            self.session_service = DatabaseSessionService(db_url=session_db_url)
            logger.info(f"Using DatabaseSessionService: {session_db_url}")

        # Build the agent pipeline
        self.pipeline = self._build_pipeline()

        # Initialize plugins
        self.plugins = []

        # Add LoggingPlugin for ADK built-in observability
        self.logging_plugin = LoggingPlugin()
        self.plugins.append(self.logging_plugin)
        logger.info("📝 LoggingPlugin enabled for ADK observability")

        # Add custom metrics plugin if enabled
        if enable_metrics:
            self.metrics_plugin = ExamMetricsPlugin(
                log_to_file=True,
                metrics_file=metrics_file
            )
            self.plugins.append(self.metrics_plugin)
            logger.info(f"📊 ExamMetricsPlugin enabled (logging to {metrics_file})")
        else:
            self.metrics_plugin = None

        # Create App with context compaction and plugins
        self.app = App(
            name="feedback_system",
            root_agent=self.pipeline,
            plugins=self.plugins,  # Plugins go in App, not Runner
            events_compaction_config=EventsCompactionConfig(
                compaction_interval=5,  # Compact after 5 exam processing sessions
                overlap_size=1  # Keep last exam for context
            )
        )

        # Create Runner (without plugins, since they're in App)
        self.runner = Runner(
            app=self.app,
            session_service=self.session_service
        )

        logger.info("✅ FeedbackSystemRefactored initialized with Runner pattern")

    def _build_pipeline(self) -> SequentialAgent:
        """
        Build the exam processing pipeline with proper state flow.

        Agent Communication Flow:
        1. GradingAgent: Reads exam_content, answer_key from state
                        Outputs to "grading_result" state key
        2. AnalysisAgent: Reads {grading_result} from state
                         Outputs to "weakness_analysis" state key
        3. RecommendationAgent: Reads {weakness_analysis} from state
                               Outputs to "learning_plan" state key
        """
        # Create agent instances
        grading_agent = GradingAgent()
        analysis_agent = AnalysisAgent()
        recommendation_agent = RecommendationAgent()

        # Configure GradingAgent
        grading_agent.agent.output_key = "grading_result"
        grading_agent.agent.after_agent_callback = self._log_grading_callback

        # Update GradingAgent instruction to use state placeholders
        grading_agent.agent.instruction = '''
        You are an expert grader.

        Exam content: {exam_content}
        Answer key: {answer_key}

        Compare the student's answers with the correct answers and calculate the score.

        Output must be a JSON object with the following structure:
        {{
            "total_score": <number>,
            "max_score": <number>,
            "corrections": [
                {{
                    "question": <str>,
                    "student_answer": <str>,
                    "correct_answer": <str>,
                    "is_correct": <boolean>,
                    "feedback": <str>
                }}
            ],
            "general_feedback": <str>
        }}
        '''

        # Configure AnalysisAgent
        analysis_agent.agent.output_key = "weakness_analysis"
        analysis_agent.agent.after_agent_callback = self._log_analysis_callback

        # Update AnalysisAgent instruction to use state placeholders
        analysis_agent.agent.instruction = '''
        You are an expert educational analyst.
        Your task is to analyze a graded exam and identify the student's weak areas by identifying the CONCEPTS/TOPICS being tested, not the question text.

        Input from state:
        1. ORIGINAL EXAM CONTENT: {exam_content}
        2. GRADING RESULTS: {grading_result}

        Your analysis process:
        STEP 1: Read each question in the ORIGINAL EXAM CONTENT
        STEP 2: For each question, identify what CONCEPT/TOPIC it is testing (e.g., "Newton's Laws", "Square Roots", "Cell Biology")
        STEP 3: Review the GRADING RESULTS to see which questions the student got wrong
        STEP 4: For each wrong answer, extract the CONCEPT/TOPIC (not the question text) as the weakness

        Output must be a JSON object with the following structure:
        {{
            "weaknesses": [
                {{
                    "topic": <str> (the CONCEPT being tested, NOT the question text),
                    "description": <str> (explain what the student got wrong),
                    "severity": <str> (low, medium, or high)
                }}
            ],
            "summary": <str> (overall analysis of student performance)
        }}

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
        Question: "Calculate the force when mass=10kg and acceleration=5m/s²"
        Correct topic: "Force Calculations" or "Newton's Second Law"
        WRONG topic: "Calculate the force when mass=10kg..." (don't copy the question!)

        Example 2:
        Question: "What is the square root of 16?"
        Correct topic: "Square Roots" or "Radical Expressions"
        WRONG topic: "What is the square root of 16?" (don't copy the question!)

        Focus on identifying the underlying CONCEPTS the student struggled with, not repeating the question text.
        '''

        # Configure RecommendationAgent
        recommendation_agent.agent.output_key = "learning_plan"
        recommendation_agent.agent.after_agent_callback = self._log_recommendation_callback

        # Update RecommendationAgent instruction to use state placeholders
        recommendation_agent.agent.instruction = '''
        You are a learning advisor.

        Based on the weakness analysis: {weakness_analysis}

        Create a personalized learning plan with specific, actionable recommendations.

        Output must be a JSON object with the following structure:
        {{
            "learning_objectives": [
                {{
                    "objective": <str>,
                    "resources": [<str>],
                    "estimated_time": <str>
                }}
            ],
            "encouragement": <str>
        }}
        '''

        # Create Sequential Pipeline
        pipeline = SequentialAgent(
            name="exam_processing_pipeline",
            sub_agents=[
                grading_agent.agent,
                analysis_agent.agent,
                recommendation_agent.agent
            ]
        )

        return pipeline

    async def _log_grading_callback(self, callback_context: CallbackContext) -> None:
        """
        Async callback to log grading results to database.

        This callback is triggered after GradingAgent completes.
        It reads the grading_result from state and saves to DB.
        """
        try:
            # Access grading result from state (output_key)
            grading_result_str = callback_context.state.get("grading_result")

            if not grading_result_str:
                logger.error("No grading_result in state")
                return

            # Parse JSON result
            grading_result = json.loads(grading_result_str)

            # Get exam metadata from state
            exam_id = callback_context.state.get("exam_id")
            student_id = callback_context.state.get("student_id")
            subject = callback_context.state.get("subject", "Unknown Subject")

            if not exam_id or not student_id:
                logger.error(f"Missing exam_id or student_id in state")
                return

            # Save to database
            logger.info(f"Logging grading result for exam {exam_id}")
            self.db.log_exam(
                exam_id=exam_id,
                student_id=student_id,
                subject=subject,
                total_score=grading_result.get("total_score", 0),
                max_score=grading_result.get("max_score", 0)
            )

        except json.JSONDecodeError as e:
            logger.error(f"Error parsing grading JSON: {e}")
        except Exception as e:
            logger.error(f"Error in grading callback: {e}", exc_info=True)

    async def _log_analysis_callback(self, callback_context: CallbackContext) -> None:
        """
        Async callback to log analysis results to database.

        This callback is triggered after AnalysisAgent completes.
        """
        try:
            # Access analysis result from state
            analysis_result_str = callback_context.state.get("weakness_analysis")

            if not analysis_result_str:
                logger.error("No weakness_analysis in state")
                return

            # Parse JSON result
            analysis_result = json.loads(analysis_result_str)

            # Get exam_id from state
            exam_id = callback_context.state.get("exam_id")

            if not exam_id:
                logger.error("Missing exam_id in state")
                return

            # Save to database
            logger.info(f"Logging analysis result for exam {exam_id}")
            self.db.log_analysis(
                exam_id=exam_id,
                weaknesses=analysis_result.get("weaknesses", [])
            )

        except json.JSONDecodeError as e:
            logger.error(f"Error parsing analysis JSON: {e}")
        except Exception as e:
            logger.error(f"Error in analysis callback: {e}", exc_info=True)

    async def _log_recommendation_callback(self, callback_context: CallbackContext) -> None:
        """
        Async callback to log recommendations to database.

        This callback is triggered after RecommendationAgent completes.
        """
        try:
            # Access recommendation result from state
            recommendation_result_str = callback_context.state.get("learning_plan")

            if not recommendation_result_str:
                logger.error("No learning_plan in state")
                return

            # Parse JSON result
            recommendation_result = json.loads(recommendation_result_str)

            # Get exam_id from state
            exam_id = callback_context.state.get("exam_id")

            if not exam_id:
                logger.error("Missing exam_id in state")
                return

            # Save to database
            logger.info(f"Logging recommendation result for exam {exam_id}")
            self.db.log_analysis(
                exam_id=exam_id,
                recommendations=json.dumps(recommendation_result)
            )

        except json.JSONDecodeError as e:
            logger.error(f"Error parsing recommendation JSON: {e}")
        except Exception as e:
            logger.error(f"Error in recommendation callback: {e}", exc_info=True)

    def register_student(self, name: str) -> str:
        """Register a new student and return their ID."""
        student_id = str(uuid.uuid4())
        self.db.add_student(student_id, name)
        logger.info(f"Registered student: {name} ({student_id})")
        return student_id

    async def process_exam(
        self,
        student_id: str,
        exam_content: str,
        answer_key: str,
        subject: str = "Unknown Subject",
        user_id: str = "default_user"
    ) -> Dict[str, Any]:
        """
        Process an exam using the proper Runner pattern.

        Args:
            student_id: ID of the student
            exam_content: The student's exam answers
            answer_key: The correct answers
            subject: Subject of the exam
            user_id: User ID for session management

        Returns:
            Dictionary with grading results, analysis, and recommendations
        """
        # Generate exam ID
        exam_id = str(uuid.uuid4())

        # Create session ID for this exam processing
        session_id = f"exam_{exam_id}"

        logger.info(f"Processing exam {exam_id} for student {student_id}")

        # Prepare initial state with exam data
        initial_state = {
            "exam_id": exam_id,
            "student_id": student_id,
            "subject": subject,
            "exam_content": exam_content,
            "answer_key": answer_key
        }

        # Create or get session with initial state
        session = await self.session_service.create_session(
            app_name=self.app.name,
            user_id=user_id,
            session_id=session_id,
            state=initial_state
        )

        # Create a trigger message for the pipeline
        # The message itself is empty because data is in state
        trigger_message = types.Content(
            role="user",
            parts=[types.Part(text="Process this exam.")]
        )

        # Run the pipeline through the Runner
        logger.info("Starting exam processing pipeline via Runner...")

        response_parts = []
        async for event in self.runner.run_async(
            user_id=user_id,
            session_id=session_id,
            new_message=trigger_message
        ):
            # Collect response parts
            if event.content and event.content.parts:
                for part in event.content.parts:
                    if part.text:
                        response_parts.append(part.text)

        # Retrieve final session state
        final_session = await self.session_service.get_session(
            app_name=self.app.name,
            user_id=user_id,
            session_id=session_id
        )

        # Fetch from database which has the proper format
        db_result = self.db.get_exam(exam_id)

        if db_result:
            # Add metadata
            results = {
                "exam_id": exam_id,
                "student_id": student_id,
                "subject": subject,
                # Flatten structure for easy access
                "total_score": db_result['grading']['total_score'],
                "max_score": db_result['grading']['max_score'],
                "percentage": (db_result['grading']['total_score'] / db_result['grading']['max_score'] * 100) if db_result['grading']['max_score'] > 0 else 0,
                "weaknesses": db_result['analysis']['weaknesses'],
                "recommendations": db_result['analysis']['recommendations']
            }
            logger.info(f"✅ Exam processing complete for {exam_id}")
        else:
            # Return empty structure if database retrieval fails
            logger.error(f"⚠️ Data not found in database for exam {exam_id}")
            results = {
                "exam_id": exam_id,
                "student_id": student_id,
                "subject": subject,
                "total_score": 0,
                "max_score": 0,
                "percentage": 0.0,
                "weaknesses": [],
                "recommendations": ""
            }

        return results

    def get_metrics_summary(self) -> Optional[Dict[str, Any]]:
        """
        Get summary statistics from the metrics plugin.

        Returns:
            Dictionary with summary statistics, or None if metrics disabled
        """
        if self.metrics_plugin:
            return self.metrics_plugin.get_summary_statistics()
        else:
            logger.warning("Metrics plugin not enabled")
            return None

    def print_metrics_summary(self) -> None:
        """
        Print human-readable summary of metrics.
        """
        if self.metrics_plugin:
            self.metrics_plugin.print_summary()
        else:
            logger.warning("Metrics plugin not enabled")


# Create global instance (for backward compatibility)
feedback_system_refactored = FeedbackSystemRefactored()
