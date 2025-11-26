"""
Conversational tools for the educational feedback assistant.

This module provides tool functions that the conversational agent can call
to interact with the backend FeedbackSystem. Tools handle:
- User authentication and role management
- Exam processing (from text or images)
- Results viewing and analytics
- Learning recommendations

Tools follow ADK best practices:
- Accept ToolContext for session state access
- Return structured dictionaries
- Include proper authorization checks
- Handle errors gracefully
"""

import json
import logging
import os
import uuid
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from google.adk.tools.tool_context import ToolContext

logger = logging.getLogger(__name__)


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================


def check_authorization(
    tool_context: ToolContext,
    required_role: Optional[str] = None,
    allow_own_data: bool = False,
    target_student_id: Optional[str] = None,
) -> Tuple[bool, str]:
    """
    Check if current user is authorized for an action.

    Args:
        tool_context: ADK tool context with session state
        required_role: Role required ("teacher" or None for any authenticated)
        allow_own_data: If True, students can access their own data
        target_student_id: Student ID being accessed (for own-data checks)

    Returns:
        Tuple of (is_authorized, error_message)
    """
    # Check if authenticated
    if not tool_context.state.get("is_authenticated"):
        return False, "Not authenticated. Please tell me your name and role first."

    current_role = tool_context.state.get("current_user_role")
    current_user_id = tool_context.state.get("current_user_id")

    # No specific role required - any authenticated user is allowed
    if required_role is None:
        return True, ""

    # Check teacher role
    if required_role == "teacher" and current_role != "teacher":
        # But allow students to access their own data if enabled
        if allow_own_data and target_student_id and current_user_id == target_student_id:
            return True, ""
        return False, "This action requires teacher privileges."

    return True, ""


def is_url(path: str) -> bool:
    """Check if the given path is a URL."""
    return path.startswith(("http://", "https://"))


async def fetch_image_from_url(url: str) -> Tuple[bool, bytes, str, str]:
    """
    Fetch image bytes from a URL.

    Args:
        url: The URL to fetch the image from

    Returns:
        Tuple of (success, image_bytes, mime_type, error_message)
    """
    import aiohttp

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status != 200:
                    return False, b"", "", f"Failed to fetch image: HTTP {response.status}"

                # Get content type from response headers
                content_type = response.headers.get("Content-Type", "image/jpeg")
                mime_type = content_type.split(";")[0].strip()

                # Read image bytes
                image_bytes = await response.read()

                return True, image_bytes, mime_type, ""
    except Exception as e:
        return False, b"", "", f"Error fetching image: {str(e)}"


def validate_image_source(image_source: str) -> Tuple[bool, str, bool]:
    """
    Validate an image source (local path or URL).

    Args:
        image_source: Path to image file or URL

    Returns:
        Tuple of (is_valid, resolved_path_or_error, is_url)
    """
    # Check if it's a URL
    if is_url(image_source):
        # For URLs, we just validate the format and return
        return True, image_source, True

    # Otherwise, validate as local path
    # Expand ~ to home directory
    expanded_path = os.path.expanduser(image_source)

    # Resolve to absolute path
    resolved_path = Path(expanded_path).resolve()

    # Check if file exists
    if not resolved_path.exists():
        return False, f"File not found: {image_source}", False

    # Check if file is readable
    if not resolved_path.is_file():
        return False, f"Not a file: {image_source}", False

    # Check extension
    valid_extensions = {".jpg", ".jpeg", ".png", ".gif", ".webp"}
    if resolved_path.suffix.lower() not in valid_extensions:
        return False, f"Invalid image format. Supported: {', '.join(valid_extensions)}", False

    return True, str(resolved_path), False


def extract_image_from_user_content(tool_context: ToolContext) -> Tuple[bool, bytes, str]:
    """
    Extract image data from the user's message content.

    When images are uploaded via ADK Web UI, they are passed as inline_data
    in the user_content parts. This function extracts that image data.

    Args:
        tool_context: ADK tool context with user_content

    Returns:
        Tuple of (found, image_bytes, mime_type)
    """
    user_content = tool_context.user_content
    if not user_content or not user_content.parts:
        return False, b"", ""

    # Look for image parts in user content
    for part in user_content.parts:
        # Check for inline_data (uploaded images)
        if hasattr(part, "inline_data") and part.inline_data:
            inline_data = part.inline_data
            if hasattr(inline_data, "data") and inline_data.data:
                mime_type = getattr(inline_data, "mime_type", "image/jpeg")
                # Check if it's an image MIME type
                if mime_type and mime_type.startswith("image/"):
                    logger.info(f"Found inline image data in user_content: {mime_type}")
                    return True, inline_data.data, mime_type

    return False, b"", ""


def format_exam_results(results: Dict[str, Any]) -> str:
    """
    Format exam results for human-readable display.

    Args:
        results: Dictionary with exam results from process_exam()

    Returns:
        Formatted string for display
    """
    lines = []

    # Header
    subject = results.get("subject", "Unknown Subject")
    lines.append(f"**{subject} Exam Results**")
    lines.append("")

    # Score
    total = results.get("total_score", 0)
    max_score = results.get("max_score", 0)
    percentage = results.get("percentage", 0)
    lines.append(f"**Score:** {total}/{max_score} ({percentage:.1f}%)")
    lines.append("")

    # Weaknesses
    weaknesses = results.get("weaknesses", [])
    if weaknesses:
        lines.append("**Areas for Improvement:**")
        for w in weaknesses:
            topic = w.get("topic", "Unknown")
            severity = w.get("severity", "medium")
            description = w.get("description", "")
            lines.append(f"- {topic} ({severity}): {description}")
        lines.append("")
    else:
        lines.append("**Great job!** No weaknesses identified.")
        lines.append("")

    # Topics covered
    topics = results.get("topics", [])
    if topics:
        lines.append(f"**Topics Tested:** {', '.join(topics)}")
        lines.append("")

    return "\n".join(lines)


def format_learning_plan(plan: str) -> str:
    """
    Format learning plan for human-readable display.

    Args:
        plan: JSON string or dict with learning plan

    Returns:
        Formatted string for display
    """
    try:
        if isinstance(plan, str):
            plan_data = json.loads(plan)
        else:
            plan_data = plan
    except json.JSONDecodeError:
        return plan  # Return as-is if not valid JSON

    lines = []
    lines.append("**Personalized Learning Plan**")
    lines.append("")

    # Learning objectives
    objectives = plan_data.get("learning_objectives", [])
    if objectives:
        lines.append("**Learning Objectives:**")
        for i, obj in enumerate(objectives, 1):
            objective = obj.get("objective", "")
            priority = obj.get("priority", "medium")
            lines.append(f"{i}. {objective} (Priority: {priority})")
        lines.append("")

    # Weekly plan
    weekly = plan_data.get("weekly_plan", {})
    if weekly:
        hours = weekly.get("total_hours", 0)
        lines.append(f"**Suggested Study Time:** {hours} hours/week")
        activities = weekly.get("activities", [])
        if activities:
            lines.append("**Weekly Activities:**")
            for activity in activities[:5]:  # Limit to first 5
                day = activity.get("day", "")
                act = activity.get("activity", "")
                duration = activity.get("duration", "")
                lines.append(f"- {day}: {act} ({duration})")
        lines.append("")

    # Encouragement
    encouragement = plan_data.get("encouragement", "")
    if encouragement:
        lines.append(f"**Encouragement:** {encouragement}")

    return "\n".join(lines)


# =============================================================================
# AUTHENTICATION TOOL
# =============================================================================


def authenticate_user(
    tool_context: ToolContext,
    name: str,
    role: str,
) -> Dict[str, Any]:
    """
    Authenticate and register a user for the current conversation session.

    This tool should be called at the start of a conversation to identify
    the user and their role (teacher or student).

    Args:
        tool_context: ADK tool context with session state
        name: User's full name
        role: User's role - must be "teacher" or "student"

    Returns:
        Dictionary with authentication result and available actions
    """
    # Validate role
    role_lower = role.lower().strip()
    if role_lower not in ("teacher", "student"):
        return {
            "status": "error",
            "message": f"Invalid role '{role}'. Please specify 'teacher' or 'student'.",
        }

    # Generate user ID
    user_id = str(uuid.uuid4())

    # Store in session state
    tool_context.state["current_user_id"] = user_id
    tool_context.state["current_user_role"] = role_lower
    tool_context.state["current_user_name"] = name
    tool_context.state["is_authenticated"] = True

    logger.info(f"Authenticated user: {name} ({role_lower}) - ID: {user_id}")

    # Return capabilities based on role
    if role_lower == "teacher":
        capabilities = [
            "Grade exams from images or text",
            "View any student's results",
            "See class-wide analytics",
            "List all students",
            "Get learning recommendations for any student",
        ]
    else:
        capabilities = [
            "View your own exam results",
            "Get personalized learning recommendations",
        ]

    return {
        "status": "success",
        "message": f"Welcome, {name}! You are logged in as a {role_lower}.",
        "user_id": user_id,
        "role": role_lower,
        "capabilities": capabilities,
    }


# =============================================================================
# EXAM PROCESSING TOOLS
# =============================================================================


async def process_exam_from_image(
    tool_context: ToolContext,
    image_path: str,
    student_name: str,
    subject: str = "Unknown",
) -> Dict[str, Any]:
    """
    Process and grade an exam from an image file or URL.

    This tool extracts exam content from an image using OCR, then grades it
    through the full processing pipeline (grading, analysis, recommendations).

    Supports multiple image sources:
    - ADK Web UI uploads (extracted from user_content)
    - URLs (fetched via HTTP)
    - Local file paths

    Args:
        tool_context: ADK tool context with session state
        image_path: Path to the exam image file or URL (can be placeholder for ADK uploads)
        student_name: Name of the student whose exam this is
        subject: Subject of the exam (optional, will be inferred from image if not provided)

    Returns:
        Dictionary with grading results, weaknesses, and learning plan
    """
    # Check authorization - only teachers can grade exams
    authorized, error = check_authorization(tool_context, required_role="teacher")
    if not authorized:
        return {"status": "error", "message": error}

    logger.info(f"Processing exam for student: {student_name}")

    try:
        # Import here to avoid circular imports
        from feedback_agent.agent import get_feedback_system
        from feedback_agent.agents.image_processing_agent import ImageProcessingAgent

        image_agent = ImageProcessingAgent()
        extracted = None

        # Strategy 1: Try to extract image from user_content (ADK Web UI uploads)
        found, image_bytes, mime_type = extract_image_from_user_content(tool_context)
        if found:
            logger.info(f"Using image from user_content (ADK Web UI upload): {mime_type}")
            extracted = await image_agent.process_image(
                image_bytes=image_bytes,
                mime_type=mime_type
            )
        else:
            # Strategy 2: Try URL or local path
            valid, result, is_url_source = validate_image_source(image_path)

            if is_url_source:
                # Fetch image from URL
                logger.info(f"Fetching image from URL: {result}")
                success, image_bytes, mime_type, fetch_error = await fetch_image_from_url(result)
                if not success:
                    return {"status": "error", "message": fetch_error}
                extracted = await image_agent.process_image(
                    image_bytes=image_bytes,
                    mime_type=mime_type
                )
            elif valid:
                # Process with local path
                logger.info(f"Processing local image: {result}")
                extracted = await image_agent.process_image(image_path=result)
            else:
                # No image found anywhere
                return {
                    "status": "error",
                    "message": f"Could not find image. {result} Please upload an image via the chat or provide a valid file path.",
                }

        if "error" in extracted:
            return {
                "status": "error",
                "message": f"Failed to extract exam content: {extracted['error']}",
            }

        exam_content = extracted.get("exam_content", "")
        answer_key = extracted.get("answer_key", "Not found")
        detected_subject = extracted.get("subject", subject)

        if not exam_content:
            return {
                "status": "error",
                "message": "Could not extract exam content from image. Please ensure the image is clear and contains exam questions.",
            }

        # If no answer key found in image, we need one
        if answer_key == "Not found":
            return {
                "status": "needs_answer_key",
                "message": "I extracted the exam content but couldn't find an answer key in the image. Please provide the answer key.",
                "exam_content": exam_content,
                "subject": detected_subject,
            }

        # Get FeedbackSystem and process exam
        system = get_feedback_system()

        # Register student if not exists
        student_id = system.register_student(student_name)

        # Process through the full pipeline
        results = await system.process_exam(
            student_id=student_id,
            exam_content=exam_content,
            answer_key=answer_key,
            subject=detected_subject if subject == "Unknown" else subject,
            user_id=tool_context.state.get("current_user_id", "default"),
        )

        # Format results for display
        formatted = format_exam_results(results)

        return {
            "status": "success",
            "message": f"Exam graded successfully for {student_name}!",
            "student_name": student_name,
            "student_id": student_id,
            "results": results,
            "formatted_results": formatted,
        }

    except Exception as e:
        logger.error(f"Error processing exam image: {e}", exc_info=True)
        return {
            "status": "error",
            "message": f"An error occurred while processing the exam: {str(e)}",
        }


async def process_exam_from_text(
    tool_context: ToolContext,
    student_name: str,
    exam_content: str,
    answer_key: str,
    subject: str = "General",
) -> Dict[str, Any]:
    """
    Process and grade an exam from text content.

    This tool grades an exam where the questions, student answers, and answer key
    are provided as text.

    Args:
        tool_context: ADK tool context with session state
        student_name: Name of the student whose exam this is
        exam_content: The exam questions and student's answers
        answer_key: The correct answers for grading
        subject: Subject of the exam

    Returns:
        Dictionary with grading results, weaknesses, and learning plan
    """
    # Check authorization - only teachers can grade exams
    authorized, error = check_authorization(tool_context, required_role="teacher")
    if not authorized:
        return {"status": "error", "message": error}

    # Validate inputs
    if not exam_content or not exam_content.strip():
        return {
            "status": "error",
            "message": "Exam content cannot be empty. Please provide the exam questions and student answers.",
        }

    if not answer_key or not answer_key.strip():
        return {
            "status": "error",
            "message": "Answer key cannot be empty. Please provide the correct answers.",
        }

    logger.info(f"Processing text exam for student: {student_name}, subject: {subject}")

    try:
        # Import here to avoid circular imports
        from feedback_agent.agent import get_feedback_system

        # Get FeedbackSystem
        system = get_feedback_system()

        # Register student if not exists
        student_id = system.register_student(student_name)

        # Process through the full pipeline
        results = await system.process_exam(
            student_id=student_id,
            exam_content=exam_content,
            answer_key=answer_key,
            subject=subject,
            user_id=tool_context.state.get("current_user_id", "default"),
        )

        # Format results for display
        formatted = format_exam_results(results)

        return {
            "status": "success",
            "message": f"Exam graded successfully for {student_name}!",
            "student_name": student_name,
            "student_id": student_id,
            "results": results,
            "formatted_results": formatted,
        }

    except Exception as e:
        logger.error(f"Error processing text exam: {e}", exc_info=True)
        return {
            "status": "error",
            "message": f"An error occurred while processing the exam: {str(e)}",
        }


# =============================================================================
# RESULTS VIEWING TOOLS
# =============================================================================


def get_my_results(tool_context: ToolContext) -> Dict[str, Any]:
    """
    View the current user's own exam results.

    This tool retrieves all exam results for the currently authenticated user.
    Available to any authenticated user (students see their own, teachers can
    use get_student_results for others).

    Args:
        tool_context: ADK tool context with session state

    Returns:
        Dictionary with exam history and performance summary
    """
    # Check authentication
    authorized, error = check_authorization(tool_context)
    if not authorized:
        return {"status": "error", "message": error}

    user_name = tool_context.state.get("current_user_name")
    user_role = tool_context.state.get("current_user_role")

    logger.info(f"get_my_results called by {user_name} ({user_role})")

    try:
        from feedback_agent.agent import get_feedback_system

        system = get_feedback_system()
        db = system.db

        # Find student by name (simplified - in production would use proper user mapping)
        all_students = db.get_all_students()
        student = next(
            (s for s in all_students if s["name"].lower() == user_name.lower()),
            None,
        )

        if not student:
            return {
                "status": "success",
                "message": f"No exam records found for {user_name}.",
                "exams": [],
            }

        student_id = student["student_id"]
        exams = db.get_student_exams(student_id)

        if not exams:
            return {
                "status": "success",
                "message": f"No exams recorded yet for {user_name}.",
                "exams": [],
            }

        # Calculate statistics
        total_score = sum(e.get("total_score", 0) for e in exams)
        total_max = sum(e.get("max_score", 0) for e in exams)
        avg_percentage = (total_score / total_max * 100) if total_max > 0 else 0

        # Get weaknesses
        all_weaknesses = []
        for exam in exams:
            analysis = db.get_analysis(exam["exam_id"])
            if analysis and analysis.get("weaknesses"):
                all_weaknesses.extend(analysis["weaknesses"])

        return {
            "status": "success",
            "student_name": user_name,
            "summary": {
                "total_exams": len(exams),
                "average_percentage": round(avg_percentage, 1),
                "total_score": total_score,
                "total_max_score": total_max,
            },
            "exams": exams,
            "recurring_weaknesses": all_weaknesses,
        }

    except Exception as e:
        logger.error(f"Error getting results: {e}", exc_info=True)
        return {
            "status": "error",
            "message": f"An error occurred: {str(e)}",
        }


def get_student_results(
    tool_context: ToolContext,
    student_name: Optional[str] = None,
    student_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    View a specific student's exam results (teacher only).

    This tool retrieves all exam results for a specified student.
    Only available to teachers.

    Args:
        tool_context: ADK tool context with session state
        student_name: Name of the student to look up
        student_id: ID of the student (alternative to name)

    Returns:
        Dictionary with student's exam history and performance summary
    """
    # Check authorization - teachers only
    authorized, error = check_authorization(tool_context, required_role="teacher")
    if not authorized:
        return {"status": "error", "message": error}

    if not student_name and not student_id:
        return {
            "status": "error",
            "message": "Please specify either a student name or student ID.",
        }

    logger.info(f"get_student_results for: {student_name or student_id}")

    try:
        from feedback_agent.agent import get_feedback_system

        system = get_feedback_system()
        db = system.db

        # Find student
        if student_id:
            student = db.get_student(student_id)
        else:
            all_students = db.get_all_students()
            student = next(
                (s for s in all_students if student_name.lower() in s["name"].lower()),
                None,
            )

        if not student:
            return {
                "status": "error",
                "message": f"Student not found: {student_name or student_id}",
            }

        student_id = student["student_id"]
        student_name = student["name"]
        exams = db.get_student_exams(student_id)

        if not exams:
            return {
                "status": "success",
                "message": f"No exams recorded for {student_name}.",
                "student_name": student_name,
                "student_id": student_id,
                "exams": [],
            }

        # Calculate statistics
        total_score = sum(e.get("total_score", 0) for e in exams)
        total_max = sum(e.get("max_score", 0) for e in exams)
        avg_percentage = (total_score / total_max * 100) if total_max > 0 else 0

        # Get weaknesses and recommendations
        all_weaknesses = []
        all_recommendations = []
        for exam in exams:
            analysis = db.get_analysis(exam["exam_id"])
            if analysis:
                if analysis.get("weaknesses"):
                    all_weaknesses.extend(analysis["weaknesses"])
                if analysis.get("recommendations"):
                    all_recommendations.append(analysis["recommendations"])

        return {
            "status": "success",
            "student_name": student_name,
            "student_id": student_id,
            "summary": {
                "total_exams": len(exams),
                "average_percentage": round(avg_percentage, 1),
                "total_score": total_score,
                "total_max_score": total_max,
            },
            "exams": exams,
            "recurring_weaknesses": all_weaknesses,
            "recommendations": all_recommendations,
        }

    except Exception as e:
        logger.error(f"Error getting student results: {e}", exc_info=True)
        return {
            "status": "error",
            "message": f"An error occurred: {str(e)}",
        }


def get_class_analytics(tool_context: ToolContext) -> Dict[str, Any]:
    """
    View class-wide statistics and analytics (teacher only).

    This tool provides an overview of class performance including:
    - Class average scores
    - Highest and lowest performers
    - Common weaknesses across all students

    Args:
        tool_context: ADK tool context with session state

    Returns:
        Dictionary with class-wide statistics
    """
    # Check authorization - teachers only
    authorized, error = check_authorization(tool_context, required_role="teacher")
    if not authorized:
        return {"status": "error", "message": error}

    logger.info("get_class_analytics called")

    try:
        from feedback_agent.agent import get_feedback_system

        system = get_feedback_system()
        db = system.db

        all_students = db.get_all_students()

        if not all_students:
            return {
                "status": "success",
                "message": "No students registered in the system.",
                "statistics": {},
            }

        # Collect student performances
        student_performances = []
        all_class_weaknesses = []

        for student in all_students:
            student_id = student["student_id"]
            exams = db.get_student_exams(student_id)

            if exams:
                total_score = sum(e.get("total_score", 0) for e in exams)
                total_max = sum(e.get("max_score", 0) for e in exams)
                avg_percentage = (total_score / total_max * 100) if total_max > 0 else 0

                student_performances.append({
                    "student_id": student_id,
                    "student_name": student["name"],
                    "exams_taken": len(exams),
                    "average_percentage": round(avg_percentage, 1),
                })

                # Collect weaknesses
                for exam in exams:
                    analysis = db.get_analysis(exam["exam_id"])
                    if analysis and analysis.get("weaknesses"):
                        all_class_weaknesses.extend(analysis["weaknesses"])

        if not student_performances:
            return {
                "status": "success",
                "message": "No exam data available yet.",
                "total_students": len(all_students),
                "students_with_exams": 0,
            }

        # Calculate class statistics
        class_average = (
            sum(s["average_percentage"] for s in student_performances)
            / len(student_performances)
        )
        highest = max(student_performances, key=lambda s: s["average_percentage"])
        lowest = min(student_performances, key=lambda s: s["average_percentage"])

        # Find common weaknesses
        weakness_counts = {}
        for w in all_class_weaknesses:
            topic = w.get("topic", "Unknown")
            weakness_counts[topic] = weakness_counts.get(topic, 0) + 1

        common_weaknesses = sorted(
            weakness_counts.items(), key=lambda x: x[1], reverse=True
        )[:5]

        return {
            "status": "success",
            "class_summary": {
                "total_students": len(all_students),
                "students_with_exams": len(student_performances),
                "class_average_percentage": round(class_average, 1),
                "highest_performer": highest,
                "lowest_performer": lowest,
            },
            "student_performances": student_performances,
            "common_weaknesses": [
                {"topic": topic, "occurrence_count": count}
                for topic, count in common_weaknesses
            ],
        }

    except Exception as e:
        logger.error(f"Error getting class analytics: {e}", exc_info=True)
        return {
            "status": "error",
            "message": f"An error occurred: {str(e)}",
        }


def list_students(tool_context: ToolContext) -> Dict[str, Any]:
    """
    List all students in the system (teacher only).

    This tool provides a list of all registered students.

    Args:
        tool_context: ADK tool context with session state

    Returns:
        Dictionary with list of students
    """
    # Check authorization - teachers only
    authorized, error = check_authorization(tool_context, required_role="teacher")
    if not authorized:
        return {"status": "error", "message": error}

    logger.info("list_students called")

    try:
        from feedback_agent.agent import get_feedback_system

        system = get_feedback_system()
        db = system.db

        students = db.get_all_students()

        return {
            "status": "success",
            "total_students": len(students),
            "students": [
                {"student_id": s["student_id"], "name": s["name"]}
                for s in students
            ],
        }

    except Exception as e:
        logger.error(f"Error listing students: {e}", exc_info=True)
        return {
            "status": "error",
            "message": f"An error occurred: {str(e)}",
        }


# =============================================================================
# LEARNING RECOMMENDATIONS TOOL
# =============================================================================


def get_learning_recommendations(
    tool_context: ToolContext,
    student_name: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Get personalized learning recommendations.

    For students: Returns recommendations based on their own exam history.
    For teachers: Can specify a student name to get their recommendations.

    Args:
        tool_context: ADK tool context with session state
        student_name: Name of student (teachers can specify, students use own)

    Returns:
        Dictionary with learning recommendations
    """
    # Check authentication
    authorized, error = check_authorization(tool_context)
    if not authorized:
        return {"status": "error", "message": error}

    current_role = tool_context.state.get("current_user_role")
    current_name = tool_context.state.get("current_user_name")

    # Students can only get their own recommendations
    if current_role == "student":
        student_name = current_name
    elif not student_name:
        return {
            "status": "error",
            "message": "Please specify which student to get recommendations for.",
        }

    logger.info(f"get_learning_recommendations for: {student_name}")

    try:
        from feedback_agent.agent import get_feedback_system

        system = get_feedback_system()
        db = system.db

        # Find student
        all_students = db.get_all_students()
        student = next(
            (s for s in all_students if student_name.lower() in s["name"].lower()),
            None,
        )

        if not student:
            return {
                "status": "error",
                "message": f"Student not found: {student_name}",
            }

        student_id = student["student_id"]

        # Get latest exam with recommendations
        exams = db.get_student_exams(student_id)

        if not exams:
            return {
                "status": "success",
                "message": f"No exam data for {student_name} yet. Recommendations will be available after grading exams.",
            }

        # Get the most recent analysis with recommendations
        latest_recommendations = None
        all_weaknesses = []

        for exam in exams:
            analysis = db.get_analysis(exam["exam_id"])
            if analysis:
                if analysis.get("weaknesses"):
                    all_weaknesses.extend(analysis["weaknesses"])
                if analysis.get("recommendations"):
                    latest_recommendations = analysis["recommendations"]

        if not latest_recommendations:
            return {
                "status": "success",
                "message": f"No detailed recommendations available yet for {student_name}.",
                "weaknesses": all_weaknesses,
            }

        # Format learning plan
        formatted = format_learning_plan(latest_recommendations)

        return {
            "status": "success",
            "student_name": student_name,
            "weaknesses": all_weaknesses,
            "learning_plan": latest_recommendations,
            "formatted_plan": formatted,
        }

    except Exception as e:
        logger.error(f"Error getting recommendations: {e}", exc_info=True)
        return {
            "status": "error",
            "message": f"An error occurred: {str(e)}",
        }
