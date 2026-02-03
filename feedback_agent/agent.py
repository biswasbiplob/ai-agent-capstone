"""
FeedbackSystem using proper ADK Runner pattern.

This module replaces the custom run_agent() wrapper with ADK's recommended
Runner/SessionService pattern following the Kaggle course best practices.

Key Improvements:
- Uses proper Runner with DatabaseSessionService
- Agents communicate via output_key and state placeholders
- Async callbacks for database logging
- Proper event streaming and session management
"""

import json
import logging
import os
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
from google.adk.agents.base_agent import BaseAgent
from google.adk.agents.callback_context import CallbackContext
from google.adk.agents.invocation_context import InvocationContext
from google.adk.agents.llm_agent import Agent as LlmAgent
from google.adk.agents.loop_agent import LoopAgent
from google.adk.agents.parallel_agent import ParallelAgent
from google.adk.agents.sequential_agent import SequentialAgent
from google.adk.apps.app import App, EventsCompactionConfig
from google.adk.events import Event, EventActions
from google.adk.plugins import LoggingPlugin
from google.adk.runners import Runner
from google.adk.sessions import DatabaseSessionService, InMemorySessionService
from google.genai import types
from typing import AsyncGenerator

# Load environment variables from .env file
# Try specific path first, then fall back to current directory
_env_path = Path(__file__).parent / ".env"
if _env_path.exists():
    load_dotenv(_env_path)
else:
    load_dotenv()  # Load from current directory or system environment

from feedback_agent.agents.analysis_agent import AnalysisAgent
from feedback_agent.agents.grading_agent import GradingAgent
from feedback_agent.agents.recommendation_agent import RecommendationAgent
from feedback_agent.conversational_agent import create_root_agent
from feedback_agent.database import StudentDatabase
from feedback_agent.json_utils import parse_json_payload
from feedback_agent.memory import MemoryService
from feedback_agent.plugins import ExamMetricsPlugin

# Configure structured logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s",
    handlers=[
        logging.StreamHandler(),  # Console output
        logging.FileHandler("feedback_system.log", mode="a"),  # File output
    ],
)
logger = logging.getLogger(__name__)


class ValidationAgent(BaseAgent):
    """
    Custom validation agent for LoopAgent quality assurance.

    Checks analysis quality and emits escalation events to control loop iteration:
    - escalate=True: Stop loop (validation passed, we're done)
    - escalate=False: Continue loop (validation failed, retry needed)
    """

    def __init__(self, name: str = "validation_agent"):
        super().__init__(
            name=name,
            description="Validates analysis quality and controls loop retry"
        )

    async def _run_async_impl(self, ctx: InvocationContext) -> AsyncGenerator[Event, None]:
        """
        Validate analysis in state and emit escalation signal.

        Returns:
            Event with escalate=True if validation passes (stop loop)
            Event with escalate=False if validation fails (continue loop)
        """
        try:
            analysis_str = ctx.session.state.get("weakness_analysis")

            # Validation failed: no analysis in state
            if not analysis_str:
                logger.warning("❌ Validation failed: No weakness_analysis in state")
                yield Event(
                    author=self.name,
                    actions=EventActions(escalate=False)  # Continue loop to retry
                )
                return

            analysis = json.loads(analysis_str)

            # Check 1: Topics field exists and has at least one topic
            topics = analysis.get("topics", [])
            weaknesses = analysis.get("weaknesses", [])

            if not topics or len(topics) == 0:
                # Provide detailed feedback to help the model improve
                if weaknesses:
                    logger.warning(
                        f"❌ Validation failed: Topics field is empty but {len(weaknesses)} "
                        f"weaknesses were identified. Topics MUST list ALL concepts tested in the exam, "
                        f"not just areas where student struggled."
                    )
                else:
                    logger.warning(
                        f"❌ Validation failed: Topics field is empty. Must list ALL concepts/subjects "
                        f"tested in the exam (e.g., 'Basic Arithmetic', 'Algebra', 'Biology')."
                    )
                yield Event(
                    author=self.name,
                    actions=EventActions(escalate=False)  # Continue loop to retry
                )
                return

            # Check 2: Weaknesses structure is valid
            if isinstance(weaknesses, list):
                for w in weaknesses:
                    if not isinstance(w, dict) or "topic" not in w:
                        logger.warning("❌ Validation failed: Invalid weakness structure")
                        yield Event(
                            author=self.name,
                            actions=EventActions(escalate=False)  # Continue loop to retry
                        )
                        return

                    # Check that weakness topics are concept names, not question text
                    topic = w.get("topic", "")
                    if len(topic) > 100 or "?" in topic or topic.startswith("Calculate"):
                        logger.warning(
                            f"❌ Validation failed: Weakness topic appears to be question text "
                            f"instead of concept name: '{topic[:50]}...'"
                        )
                        yield Event(
                            author=self.name,
                            actions=EventActions(escalate=False)
                        )
                        return

            # Check 3: Summary exists and is substantive
            summary = analysis.get("summary", "")
            if not summary or len(summary) < 20:
                logger.warning("❌ Validation failed: Summary too short (< 20 characters)")
                yield Event(
                    author=self.name,
                    actions=EventActions(escalate=False)  # Continue loop to retry
                )
                return

            # All checks passed!
            logger.info(f"✅ Analysis quality validated: {len(topics)} topics, {len(weaknesses)} weaknesses")
            yield Event(
                author=self.name,
                actions=EventActions(escalate=True)  # Stop loop, validation passed!
            )

        except json.JSONDecodeError as e:
            logger.warning(f"❌ Validation failed: Invalid JSON in analysis: {e}")
            yield Event(
                author=self.name,
                actions=EventActions(escalate=False)  # Continue loop to retry
            )
        except Exception as e:
            logger.error(f"❌ Validation error: {e}")
            yield Event(
                author=self.name,
                actions=EventActions(escalate=False)  # Continue loop to retry
            )


class FeedbackSystem:
    """
    Feedback system using proper ADK Runner pattern.

    Architecture:
    - Runner manages session and event flow
    - DatabaseSessionService provides persistent sessions
    - Agents communicate via output_key -> next agent's instruction placeholder
    - Async callbacks handle database logging
    """

    def __init__(
        self,
        db_path: str = "data/students.db",
        session_db_url: str = "sqlite:///data/feedback_sessions.db",
        use_memory_sessions: bool = False,
        enable_metrics: bool = True,
        metrics_file: str = "exam_metrics.jsonl",
        enable_logging_plugin: bool = True,
    ):
        """
        Initialize the feedback system.

        Args:
            db_path: Path to student/exam database
            session_db_url: URL for session storage
            use_memory_sessions: If True, use InMemorySessionService (for testing)
            enable_metrics: If True, enable ExamMetricsPlugin for observability
            metrics_file: Path to metrics file (JSONL format)
            enable_logging_plugin: If True, enable verbose LoggingPlugin output (disable for evaluations)
        """
        self.db = StudentDatabase(db_path)

        # Initialize memory service for cross-session tracking
        self.memory = MemoryService(self.db)
        logger.info("🧠 MemoryService initialized for cross-session tracking")

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

        # Add LoggingPlugin for ADK built-in observability (optional)
        if enable_logging_plugin:
            self.logging_plugin = LoggingPlugin()
            self.plugins.append(self.logging_plugin)
            logger.info("📝 LoggingPlugin enabled for ADK observability")
        else:
            self.logging_plugin = None
            logger.info("📝 LoggingPlugin disabled (evaluation mode)")

        # Add custom metrics plugin if enabled
        if enable_metrics:
            self.metrics_plugin = ExamMetricsPlugin(
                log_to_file=True, metrics_file=metrics_file
            )
            self.plugins.append(self.metrics_plugin)
            logger.info(f"📊 ExamMetricsPlugin enabled (logging to {metrics_file})")
        else:
            self.metrics_plugin = None

        # Create App with context compaction and plugins
        self.app = App(
            name="feedback_system",
            root_agent=self.pipeline,
            plugins=self.plugins,
            events_compaction_config=EventsCompactionConfig(
                compaction_interval=5,  # Compact after 5 exam processing sessions
                overlap_size=1,  # Keep last exam for context
            ),
        )

        self.runner = Runner(app=self.app, session_service=self.session_service)

        logger.info("✅ FeedbackSystem initialized with Runner pattern")

    def _create_study_materials_agent(self) -> LlmAgent:
        """Create specialized agent for study materials recommendations."""
        from feedback_agent.custom_llm import CustomGemini

        agent = LlmAgent(
            model=CustomGemini(model=os.getenv('MODEL_NAME')),
            name='study_materials_agent',
            description='Generates curated study materials and resources',
            instruction='''
            Based on the weakness analysis: {weakness_analysis}

            Generate specific study materials and resources for each weak topic.
            Focus on textbooks, online courses, video tutorials, and practice resources.

            Output JSON with:
            {{
                "study_materials": [
                    {{
                        "topic": <str>,
                        "resources": [
                            {{
                                "type": <str> (textbook/video/course/article),
                                "title": <str>,
                                "description": <str>,
                                "difficulty": <str> (beginner/intermediate/advanced)
                            }}
                        ]
                    }}
                ]
            }}
            '''
        )
        response_schema = types.Schema(
            type=types.Type.OBJECT,
            properties={
                "study_materials": types.Schema(
                    type=types.Type.ARRAY,
                    items=types.Schema(
                        type=types.Type.OBJECT,
                        properties={
                            "topic": types.Schema(type=types.Type.STRING),
                            "resources": types.Schema(
                                type=types.Type.ARRAY,
                                items=types.Schema(
                                    type=types.Type.OBJECT,
                                    properties={
                                        "type": types.Schema(type=types.Type.STRING),
                                        "title": types.Schema(type=types.Type.STRING),
                                        "description": types.Schema(type=types.Type.STRING),
                                        "difficulty": types.Schema(type=types.Type.STRING),
                                    },
                                    required=["type", "title", "description", "difficulty"],
                                ),
                            ),
                        },
                        required=["topic", "resources"],
                    ),
                ),
            },
            required=["study_materials"],
        )
        agent.generate_content_config = types.GenerateContentConfig(
            response_mime_type='application/json',
            response_schema=response_schema,
        )
        agent.output_key = "study_materials"
        return agent

    def _create_practice_problems_agent(self) -> LlmAgent:
        """Create specialized agent for practice problems."""
        from feedback_agent.custom_llm import CustomGemini

        agent = LlmAgent(
            model=CustomGemini(model=os.getenv('MODEL_NAME')),
            name='practice_problems_agent',
            description='Creates targeted practice problems',
            instruction='''
            Based on the weakness analysis: {weakness_analysis}

            Create specific practice problems for each weak topic.
            Design problems that progressively build mastery.

            Output JSON with:
            {{
                "practice_problems": [
                    {{
                        "topic": <str>,
                        "problems": [
                            {{
                                "difficulty": <str> (easy/medium/hard),
                                "problem": <str>,
                                "hint": <str>,
                                "learning_goal": <str>
                            }}
                        ]
                    }}
                ]
            }}
            '''
        )
        response_schema = types.Schema(
            type=types.Type.OBJECT,
            properties={
                "practice_problems": types.Schema(
                    type=types.Type.ARRAY,
                    items=types.Schema(
                        type=types.Type.OBJECT,
                        properties={
                            "topic": types.Schema(type=types.Type.STRING),
                            "problems": types.Schema(
                                type=types.Type.ARRAY,
                                items=types.Schema(
                                    type=types.Type.OBJECT,
                                    properties={
                                        "difficulty": types.Schema(type=types.Type.STRING),
                                        "problem": types.Schema(type=types.Type.STRING),
                                        "hint": types.Schema(type=types.Type.STRING),
                                        "learning_goal": types.Schema(type=types.Type.STRING),
                                    },
                                    required=["difficulty", "problem", "hint", "learning_goal"],
                                ),
                            ),
                        },
                        required=["topic", "problems"],
                    ),
                ),
            },
            required=["practice_problems"],
        )
        agent.generate_content_config = types.GenerateContentConfig(
            response_mime_type='application/json',
            response_schema=response_schema,
        )
        agent.output_key = "practice_problems"
        return agent

    def _create_learning_strategy_agent(self) -> LlmAgent:
        """Create specialized agent for learning strategies."""
        from feedback_agent.custom_llm import CustomGemini

        agent = LlmAgent(
            model=CustomGemini(model=os.getenv('MODEL_NAME')),
            name='learning_strategy_agent',
            description='Develops personalized learning strategies',
            instruction='''
            Based on the weakness analysis: {weakness_analysis}

            Develop a personalized learning strategy tailored to the student's weaknesses.
            Include study schedules, learning techniques, and progress milestones.

            Output JSON with:
            {{
                "learning_strategy": {{
                    "study_schedule": {{
                        "weekly_hours": <number>,
                        "sessions_per_week": <number>,
                        "session_duration": <str>
                    }},
                    "learning_techniques": [
                        {{
                            "technique": <str>,
                            "when_to_use": <str>,
                            "expected_benefit": <str>
                        }}
                    ],
                    "milestones": [
                        {{
                            "timeline": <str>,
                            "goal": <str>,
                            "success_criteria": <str>
                        }}
                    ]
                }}
            }}
            '''
        )
        response_schema = types.Schema(
            type=types.Type.OBJECT,
            properties={
                "learning_strategy": types.Schema(
                    type=types.Type.OBJECT,
                    properties={
                        "study_schedule": types.Schema(
                            type=types.Type.OBJECT,
                            properties={
                                "weekly_hours": types.Schema(type=types.Type.NUMBER),
                                "sessions_per_week": types.Schema(type=types.Type.NUMBER),
                                "session_duration": types.Schema(type=types.Type.STRING),
                            },
                            required=["weekly_hours", "sessions_per_week", "session_duration"],
                        ),
                        "learning_techniques": types.Schema(
                            type=types.Type.ARRAY,
                            items=types.Schema(
                                type=types.Type.OBJECT,
                                properties={
                                    "technique": types.Schema(type=types.Type.STRING),
                                    "when_to_use": types.Schema(type=types.Type.STRING),
                                    "expected_benefit": types.Schema(type=types.Type.STRING),
                                },
                                required=["technique", "when_to_use", "expected_benefit"],
                            ),
                        ),
                        "milestones": types.Schema(
                            type=types.Type.ARRAY,
                            items=types.Schema(
                                type=types.Type.OBJECT,
                                properties={
                                    "timeline": types.Schema(type=types.Type.STRING),
                                    "goal": types.Schema(type=types.Type.STRING),
                                    "success_criteria": types.Schema(type=types.Type.STRING),
                                },
                                required=["timeline", "goal", "success_criteria"],
                            ),
                        ),
                    },
                    required=["study_schedule", "learning_techniques", "milestones"],
                ),
            },
            required=["learning_strategy"],
        )
        agent.generate_content_config = types.GenerateContentConfig(
            response_mime_type='application/json',
            response_schema=response_schema,
        )
        agent.output_key = "learning_strategy"
        return agent

    def _create_synthesis_agent(self) -> LlmAgent:
        """Create agent to synthesize parallel recommendations."""
        from feedback_agent.custom_llm import CustomGemini

        agent = LlmAgent(
            model=CustomGemini(model=os.getenv('MODEL_NAME')),
            name='recommendation_synthesizer',
            description='Synthesizes diverse recommendations into unified plan',
            instruction='''
            Synthesize the following parallel recommendations into a cohesive learning plan:

            Study Materials: {study_materials}
            Practice Problems: {practice_problems}
            Learning Strategy: {learning_strategy}

            Create a unified, actionable learning plan that integrates all three aspects.

            Output JSON with:
            {{
                "learning_objectives": [
                    {{
                        "objective": <str>,
                        "resources": [<str>],
                        "practice_activities": [<str>],
                        "estimated_time": <str>,
                        "priority": <str> (high/medium/low)
                    }}
                ],
                "weekly_plan": {{
                    "total_hours": <number>,
                    "activities": [
                        {{
                            "day": <str>,
                            "activity": <str>,
                            "duration": <str>,
                            "resources_needed": [<str>]
                        }}
                    ]
                }},
                "encouragement": <str>,
                "success_metrics": [<str>]
            }}
            '''
        )
        response_schema = types.Schema(
            type=types.Type.OBJECT,
            properties={
                "learning_objectives": types.Schema(
                    type=types.Type.ARRAY,
                    items=types.Schema(
                        type=types.Type.OBJECT,
                        properties={
                            "objective": types.Schema(type=types.Type.STRING),
                            "resources": types.Schema(
                                type=types.Type.ARRAY,
                                items=types.Schema(type=types.Type.STRING),
                            ),
                            "practice_activities": types.Schema(
                                type=types.Type.ARRAY,
                                items=types.Schema(type=types.Type.STRING),
                            ),
                            "estimated_time": types.Schema(type=types.Type.STRING),
                            "priority": types.Schema(type=types.Type.STRING),
                        },
                        required=[
                            "objective",
                            "resources",
                            "practice_activities",
                            "estimated_time",
                            "priority",
                        ],
                    ),
                ),
                "weekly_plan": types.Schema(
                    type=types.Type.OBJECT,
                    properties={
                        "total_hours": types.Schema(type=types.Type.NUMBER),
                        "activities": types.Schema(
                            type=types.Type.ARRAY,
                            items=types.Schema(
                                type=types.Type.OBJECT,
                                properties={
                                    "day": types.Schema(type=types.Type.STRING),
                                    "activity": types.Schema(type=types.Type.STRING),
                                    "duration": types.Schema(type=types.Type.STRING),
                                    "resources_needed": types.Schema(
                                        type=types.Type.ARRAY,
                                        items=types.Schema(type=types.Type.STRING),
                                    ),
                                },
                                required=[
                                    "day",
                                    "activity",
                                    "duration",
                                    "resources_needed",
                                ],
                            ),
                        ),
                    },
                    required=["total_hours", "activities"],
                ),
                "encouragement": types.Schema(type=types.Type.STRING),
                "success_metrics": types.Schema(
                    type=types.Type.ARRAY,
                    items=types.Schema(type=types.Type.STRING),
                ),
            },
            required=[
                "learning_objectives",
                "weekly_plan",
                "encouragement",
                "success_metrics",
            ],
        )
        agent.generate_content_config = types.GenerateContentConfig(
            response_mime_type='application/json',
            response_schema=response_schema,
        )
        agent.output_key = "learning_plan"
        agent.after_agent_callback = self._log_recommendation_callback
        return agent

    def _build_pipeline(self) -> SequentialAgent:
        """
        Build the hybrid exam processing pipeline with quality assurance and parallel recommendations.

        Hybrid Architecture Flow:
        1. GradingAgent (Sequential): Reads exam_content, answer_key from state
                                      Outputs to "grading_result" state key

        2. AnalysisAgent with QA (LoopAgent): Reads {exam_content}, {grading_result} from state
                                              Validates output quality (topics field, weaknesses structure)
                                              Retries up to 3 times if quality insufficient
                                              Outputs to "weakness_analysis" state key

        3. Specialized Recommendations (ParallelAgent): All read {weakness_analysis} from state
                                                        Run simultaneously for performance
           - Study Materials Agent → "study_materials" state key
           - Practice Problems Agent → "practice_problems" state key
           - Learning Strategy Agent → "learning_strategy" state key

        4. Synthesis Agent (Sequential): Reads {study_materials}, {practice_problems}, {learning_strategy}
                                         Combines into unified learning plan
                                         Outputs to "learning_plan" state key
        """
        # ========================================================================
        # STEP 1: Configure GradingAgent (Sequential)
        # ========================================================================
        grading_agent = GradingAgent()
        grading_agent.agent.output_key = "grading_result"
        grading_agent.agent.after_agent_callback = self._log_grading_callback

        grading_agent.agent.instruction = """
        You are an expert grader.

        Exam content: {exam_content}
        Answer key: {answer_key}

        GRADING PROCESS:
        1. Compare each student answer with the corresponding correct answer
        2. Mark each question as correct (is_correct: true) or incorrect (is_correct: false)
        3. Calculate scores:
           - Count how many questions are marked as correct
           - Count total number of questions
           - total_score = number of correct answers
           - max_score = total number of questions
        4. VERIFY your calculation: Count the "is_correct: true" values in corrections array and ensure it matches total_score

        CRITICAL RULES:
        - total_score MUST equal the count of is_correct: true in corrections array
        - max_score MUST equal the total number of questions in corrections array
        - Double-check your arithmetic before outputting

        EXAMPLE:
        If corrections has 4 items with is_correct values: [true, false, true, false]
        Then: total_score = 2 (two trues), max_score = 4 (four questions total)

        Output must be a JSON object with the following structure:
        {{
            "total_score": <number> (count of correct answers),
            "max_score": <number> (total number of questions),
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
        """

        # ========================================================================
        # STEP 2: Configure AnalysisAgent with LoopAgent for Quality Assurance
        # ========================================================================
        analysis_agent = AnalysisAgent()
        analysis_agent.agent.output_key = "weakness_analysis"
        analysis_agent.agent.after_agent_callback = self._log_analysis_callback

        analysis_agent.agent.instruction = """
        You are an expert educational analyst.
        Your task is to analyze a graded exam and identify the student's weak areas by identifying the CONCEPTS/TOPICS being tested, not the question text.

        Input from state:
        1. ORIGINAL EXAM CONTENT: {exam_content}
        2. GRADING RESULTS: {grading_result}

        Your analysis process:
        STEP 1: Read each question in the ORIGINAL EXAM CONTENT
        STEP 2: For each question, identify what CONCEPT/TOPIC it is testing (e.g., "Newton's Laws", "Square Roots", "Cell Biology")
        STEP 3: Create a list of ALL topics/concepts tested in the exam (regardless of whether student got them right or wrong)
        STEP 4: Review the GRADING RESULTS to see which questions the student got wrong
        STEP 5: For each wrong answer, extract the CONCEPT/TOPIC (not the question text) as the weakness

        Output must be a JSON object with the following structure:
        {{
            "topics": [<str>] (ALL concepts/topics tested in this exam, required field),
            "weaknesses": [
                {{
                    "topic": <str> (the CONCEPT being tested, NOT the question text),
                    "description": <str> (explain what the student got wrong),
                    "severity": <str> (low, medium, or high)
                }}
            ],
            "summary": <str> (overall analysis of student performance, at least 20 characters)
        }}

        CRITICAL RULES:
        - The "topics" field is REQUIRED and must contain ALL concepts tested
        - The "topic" field in weaknesses MUST be a CONCEPT NAME, never the question text
        - Summary must be substantive (at least 20 characters)

        TOPIC EXTRACTION EXAMPLES:

        EXAMPLE 1 - Perfect Score:
        Exam has 4 questions: 2 on addition, 2 on subtraction. Student gets all correct.
        Expected output:
        {{
            "topics": ["Addition", "Subtraction"],  // ALL concepts tested
            "weaknesses": [],  // No weaknesses since perfect score
            "summary": "Student demonstrates strong mastery of basic arithmetic operations."
        }}

        EXAMPLE 2 - Mixed Performance:
        Exam has 4 questions: 3 chemistry (all correct), 1 astronomy (incorrect).
        Expected output:
        {{
            "topics": ["Chemistry", "Astronomy"],  // ALL concepts tested, not just failures
            "weaknesses": [
                {{
                    "topic": "Astronomy",  // Concept name, not question text
                    "description": "Student incorrectly identified the planet with the most moons",
                    "severity": "medium"
                }}
            ],
            "summary": "Student shows strong chemistry knowledge but needs work on astronomy concepts."
        }}

        EXAMPLE 3 - Multiple Topics with Multiple Weaknesses:
        Exam has 6 questions: 2 on physics (1 correct, 1 wrong), 2 on biology (both wrong), 2 on chemistry (both correct).
        Expected output:
        {{
            "topics": ["Physics", "Biology", "Chemistry"],  // ALL three subjects tested
            "weaknesses": [
                {{
                    "topic": "Force Calculations",  // Physics concept, not question text
                    "description": "Student did not apply Newton's Second Law correctly",
                    "severity": "high"
                }},
                {{
                    "topic": "Cell Structure",  // Biology concept
                    "description": "Student confused mitochondria function with nucleus function",
                    "severity": "high"
                }},
                {{
                    "topic": "Photosynthesis",  // Another biology concept
                    "description": "Student did not identify the correct products of photosynthesis",
                    "severity": "medium"
                }}
            ],
            "summary": "Student needs significant work on biology and physics concepts, but demonstrates good chemistry understanding."
        }}

        BAD EXAMPLES (DO NOT DO THIS):
        ❌ "Calculate force: mass = 10kg, acceleration = 5m/s²" (this is question text, not a concept)
        ❌ "What is the capital of France?" (this is question text)
        ❌ "Solve for x: 2x + 3 = 7" (this is question text)

        GOOD EXAMPLES (DO THIS):
        ✅ "Force Calculations" or "Newton's Second Law"
        ✅ "European Geography" or "Capital Cities"
        ✅ "Linear Equations" or "Algebraic Problem Solving"
        """

        # LoopAgent for quality assurance - validates analysis and retries up to 5 times
        # Uses custom ValidationAgent that emits escalation events to control retry:
        # - escalate=True: Stop loop (validation passed)
        # - escalate=False: Continue loop (validation failed, retry needed)
        validation_agent = ValidationAgent(name="analysis_validator")
        analysis_with_qa = LoopAgent(
            name="analysis_with_qa",
            sub_agents=[analysis_agent.agent, validation_agent],
            max_iterations=5
        )

        # ========================================================================
        # STEP 3: Create ParallelAgent with Specialized Recommendation Agents
        # ========================================================================
        parallel_recommendations = ParallelAgent(
            name="parallel_recommendations",
            sub_agents=[
                self._create_study_materials_agent(),
                self._create_practice_problems_agent(),
                self._create_learning_strategy_agent()
            ]
        )

        # ========================================================================
        # STEP 4: Create Synthesis Agent
        # ========================================================================
        synthesis_agent = self._create_synthesis_agent()

        # ========================================================================
        # STEP 5: Assemble Hybrid Pipeline
        # ========================================================================
        pipeline = SequentialAgent(
            name="exam_processing_pipeline",
            sub_agents=[
                grading_agent.agent,       # Sequential: Grade exam first
                analysis_with_qa,          # Loop: Quality-assured analysis with retries
                parallel_recommendations,  # Parallel: 3 specialized recommendation agents
                synthesis_agent            # Sequential: Synthesize parallel outputs
            ],
        )

        logger.info("✅ Hybrid pipeline built: Grading → Analysis(LoopAgent) → Parallel Recs → Synthesis")
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
            grading_result = parse_json_payload(grading_result_str, "grading_result")
            if not grading_result:
                logger.error("Failed to parse grading_result JSON")
                return

            # Get exam metadata from state
            exam_id = callback_context.state.get("exam_id")
            student_id = callback_context.state.get("student_id")
            subject = callback_context.state.get("subject", "Unknown Subject")

            if not exam_id or not student_id:
                logger.error("Missing exam_id or student_id in state")
                return

            # Save to database
            logger.info(f"Logging grading result for exam {exam_id}")
            self.db.log_exam(
                exam_id=exam_id,
                student_id=student_id,
                subject=subject,
                total_score=grading_result.get("total_score", 0),
                max_score=grading_result.get("max_score", 0),
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
            analysis_result = parse_json_payload(analysis_result_str, "weakness_analysis")
            if not analysis_result:
                logger.error("Failed to parse weakness_analysis JSON")
                return

            # Get exam_id from state
            exam_id = callback_context.state.get("exam_id")

            if not exam_id:
                logger.error("Missing exam_id in state")
                return

            # Save to database
            logger.info(f"Logging analysis result for exam {exam_id}")
            self.db.log_analysis(
                exam_id=exam_id,
                weaknesses=analysis_result.get("weaknesses", []),
                topics=analysis_result.get("topics", [])
            )

        except json.JSONDecodeError as e:
            logger.error(f"Error parsing analysis JSON: {e}")
        except Exception as e:
            logger.error(f"Error in analysis callback: {e}", exc_info=True)

    async def _log_recommendation_callback(
        self, callback_context: CallbackContext
    ) -> None:
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

            # Parse JSON result with cleanup
            recommendation_result = parse_json_payload(
                recommendation_result_str, "learning_plan"
            )
            if not recommendation_result:
                logger.error("Failed to parse learning_plan JSON")
                return

            # Get exam_id from state
            exam_id = callback_context.state.get("exam_id")

            if not exam_id:
                logger.error("Missing exam_id in state")
                return

            # Save to database
            logger.info(f"Logging recommendation result for exam {exam_id}")
            self.db.log_analysis(
                exam_id=exam_id, recommendations=json.dumps(recommendation_result)
            )

        except json.JSONDecodeError as e:
            logger.error(f"Error parsing recommendation JSON: {e}")
        except Exception as e:
            logger.error(f"Error in recommendation callback: {e}", exc_info=True)

    def register_student(self, name: str) -> str:
        """Register a new student and return their ID."""
        existing = self.db.get_student_by_name(name)
        if existing:
            student_id = existing["student_id"]
            logger.info(f"Student already registered: {name} ({student_id})")
            return student_id

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
        user_id: str = "default_user",
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
            "answer_key": answer_key,
        }

        # Create or get session with initial state
        session = await self.session_service.create_session(
            app_name=self.app.name,
            user_id=user_id,
            session_id=session_id,
            state=initial_state,
        )

        # Create a trigger message for the pipeline
        # The message itself is empty because data is in state
        trigger_message = types.Content(
            role="user", parts=[types.Part(text="Process this exam.")]
        )

        # Run the pipeline through the Runner
        logger.info("Starting exam processing pipeline via Runner...")

        response_parts = []
        async for event in self.runner.run_async(
            user_id=user_id, session_id=session_id, new_message=trigger_message
        ):
            # Collect response parts
            if event.content and event.content.parts:
                for part in event.content.parts:
                    if part.text:
                        response_parts.append(part.text)

        # Retrieve final session state
        final_session = await self.session_service.get_session(
            app_name=self.app.name, user_id=user_id, session_id=session_id
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
                "total_score": db_result["grading"]["total_score"],
                "max_score": db_result["grading"]["max_score"],
                "percentage": (
                    db_result["grading"]["total_score"]
                    / db_result["grading"]["max_score"]
                    * 100
                )
                if db_result["grading"]["max_score"] > 0
                else 0,
                "weaknesses": db_result["analysis"]["weaknesses"],
                "topics": db_result["analysis"]["topics"],
                "recommendations": db_result["analysis"]["recommendations"],
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
                "topics": [],
                "recommendations": "",
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

    # Memory Service Methods

    def get_student_recurring_weaknesses(
        self, student_id: str, min_occurrences: int = 2
    ) -> list:
        """
        Get recurring weaknesses for a student across exams.

        Args:
            student_id: The student's unique identifier
            min_occurrences: Minimum times a weakness must appear

        Returns:
            List of WeaknessPattern objects
        """
        return self.memory.get_recurring_weaknesses(student_id, min_occurrences)

    def get_student_learning_velocity(
        self, student_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get learning velocity metrics for a student.

        Args:
            student_id: The student's unique identifier

        Returns:
            LearningVelocity object with progress metrics, or None if insufficient data
        """
        velocity = self.memory.get_learning_velocity(student_id)

        if velocity:
            # Convert dataclass to dict for easier serialization
            return {
                "student_id": velocity.student_id,
                "total_exams": velocity.total_exams,
                "average_score": velocity.average_score,
                "score_trend": velocity.score_trend,
                "improvement_rate": velocity.improvement_rate,
                "subjects_mastered": velocity.subjects_mastered,
                "subjects_struggling": velocity.subjects_struggling,
            }

        return None

    def get_student_review_recommendations(
        self, student_id: str, max_topics: int = 5
    ) -> List[Dict[str, str]]:
        """
        Get personalized review recommendations for a student.

        Args:
            student_id: The student's unique identifier
            max_topics: Maximum number of topics to recommend

        Returns:
            List of recommended topics with priority and rationale
        """
        return self.memory.recommend_review_topics(student_id, max_topics)

    def get_student_mastery_progress(
        self, student_id: str
    ) -> Dict[str, Dict[str, float]]:
        """
        Get mastery progress for each subject.

        Args:
            student_id: The student's unique identifier

        Returns:
            Dictionary mapping subjects to mastery metrics
        """
        return self.memory.get_mastery_progress(student_id)


# =============================================================================
# SINGLETON ACCESSOR FOR CONVERSATIONAL TOOLS
# =============================================================================

_feedback_system_instance: Optional[FeedbackSystem] = None


def get_feedback_system() -> FeedbackSystem:
    """
    Get or create global FeedbackSystem instance for tool use.

    This singleton pattern ensures all conversational tools share the same
    FeedbackSystem instance, maintaining consistent database and session state.

    Returns:
        FeedbackSystem: The global feedback system instance
    """
    global _feedback_system_instance
    if _feedback_system_instance is None:
        _feedback_system_instance = FeedbackSystem(
            enable_logging_plugin=False,  # Disable verbose logging for conversational use
            use_memory_sessions=True,  # Use InMemorySessionService (ADK Web UI manages its own sessions)
        )
        logger.info("Created global FeedbackSystem instance for conversational tools")
    return _feedback_system_instance


# Create conversational wrapper for ADK web
# This exposes a conversational interface that wraps the processing pipeline

# Get model from environment and pass to conversational agent
model = os.getenv("MODEL_NAME")
if not model:
    raise ValueError(
        "MODEL_NAME must be set in .env file. "
        "Add MODEL_NAME=<model-name> to feedback_agent/.env "
        "(e.g., MODEL_NAME=gemini-1.5-flash)"
    )
root_agent = create_root_agent(model=model)
