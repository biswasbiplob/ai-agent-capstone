"""
Authorization layer with role-based access control tools.

This module provides tools that can be used by agents to access student data
with proper authorization checks. Tools verify user roles and permissions
before returning data.

Tools follow ADK best practices:
- Accept ToolContext for session access
- Return structured dictionaries
- Log authorization decisions
- Handle errors gracefully
"""

import logging
from typing import Dict, Any, List, Optional
from google.adk.tools.tool_context import ToolContext

from feedback_agent.auth import auth_service, UserRole
from feedback_agent.database import StudentDatabase

logger = logging.getLogger(__name__)


# Global database instance (will be set by main application)
_db: Optional[StudentDatabase] = None


def set_database(db: StudentDatabase):
    """Set the global database instance for authorization tools."""
    global _db
    _db = db
    logger.info("Database configured for authorization tools")


def _get_user_from_context(tool_context: ToolContext) -> Optional[Any]:
    """
    Extract user from tool context.

    The user should be stored in session state with key 'current_user_id'.

    Returns:
        User object if found, None otherwise
    """
    user_id = tool_context.state.get("current_user_id")
    if not user_id:
        logger.warning("No current_user_id in session state")
        return None

    user = auth_service.get_user(user_id)
    if not user:
        logger.warning(f"User {user_id} not found in auth service")
        return None

    return user


def get_my_performance(tool_context: ToolContext) -> Dict[str, Any]:
    """
    Tool for students to view their own exam performance.

    This tool:
    - Verifies the user is authenticated
    - Retrieves all exams for the current user
    - Returns performance summary

    Available to: STUDENTS (their own data), TEACHERS (any student), ADMINS

    Returns:
        Dictionary with exam performance data or error message
    """
    if _db is None:
        return {
            "status": "error",
            "message": "Database not configured"
        }

    # Get current user
    user = _get_user_from_context(tool_context)
    if not user:
        return {
            "status": "error",
            "message": "Not authenticated. Please log in first."
        }

    logger.info(f"get_my_performance called by {user.name} ({user.role.value})")

    # Students can only see their own data
    if user.is_student():
        student_id = user.user_id
    else:
        # Teachers/admins should use get_student_performance instead
        return {
            "status": "error",
            "message": "Teachers should use get_student_performance tool instead."
        }

    # Get all exams for this student
    exams = _db.get_student_exams(student_id)

    if not exams:
        return {
            "status": "success",
            "message": "No exams found for your account.",
            "exams": []
        }

    # Calculate statistics
    total_exams = len(exams)
    total_score = sum(exam.get("total_score", 0) for exam in exams)
    total_max_score = sum(exam.get("max_score", 0) for exam in exams)
    average_percentage = (total_score / total_max_score * 100) if total_max_score > 0 else 0

    # Get weaknesses across all exams
    all_weaknesses = []
    for exam in exams:
        exam_id = exam.get("exam_id")
        if exam_id:
            analysis = _db.get_analysis(exam_id)
            if analysis and analysis.get("weaknesses"):
                all_weaknesses.extend(analysis["weaknesses"])

    return {
        "status": "success",
        "student_name": user.name,
        "student_id": student_id,
        "summary": {
            "total_exams": total_exams,
            "average_percentage": round(average_percentage, 2),
            "total_score": total_score,
            "total_max_score": total_max_score
        },
        "exams": exams,
        "recurring_weaknesses": all_weaknesses
    }


def get_student_performance(
    tool_context: ToolContext,
    student_id: str
) -> Dict[str, Any]:
    """
    Tool for teachers to view a specific student's performance.

    This tool:
    - Verifies the user is a TEACHER or ADMIN
    - Retrieves all exams for the specified student
    - Returns performance summary and recommendations

    Available to: TEACHERS, ADMINS

    Args:
        student_id: ID of the student to retrieve performance for

    Returns:
        Dictionary with student performance data or error message
    """
    if _db is None:
        return {
            "status": "error",
            "message": "Database not configured"
        }

    # Get current user
    user = _get_user_from_context(tool_context)
    if not user:
        return {
            "status": "error",
            "message": "Not authenticated. Please log in first."
        }

    # Check authorization
    if not user.can_view_student_data(student_id):
        logger.warning(
            f"User {user.user_id} ({user.role.value}) attempted to access "
            f"student {student_id} data without permission"
        )
        return {
            "status": "error",
            "message": "Permission denied. You can only view your own performance."
        }

    logger.info(
        f"get_student_performance called by {user.name} ({user.role.value}) "
        f"for student {student_id}"
    )

    # Get student info
    student = _db.get_student(student_id)
    if not student:
        return {
            "status": "error",
            "message": f"Student {student_id} not found"
        }

    # Get all exams for this student
    exams = _db.get_student_exams(student_id)

    if not exams:
        return {
            "status": "success",
            "message": f"No exams found for {student['name']}",
            "student_name": student["name"],
            "student_id": student_id,
            "exams": []
        }

    # Calculate statistics
    total_exams = len(exams)
    total_score = sum(exam.get("total_score", 0) for exam in exams)
    total_max_score = sum(exam.get("max_score", 0) for exam in exams)
    average_percentage = (total_score / total_max_score * 100) if total_max_score > 0 else 0

    # Get weaknesses and recommendations
    all_weaknesses = []
    all_recommendations = []
    for exam in exams:
        exam_id = exam.get("exam_id")
        if exam_id:
            analysis = _db.get_analysis(exam_id)
            if analysis:
                if analysis.get("weaknesses"):
                    all_weaknesses.extend(analysis["weaknesses"])
                if analysis.get("recommendations"):
                    all_recommendations.append(analysis["recommendations"])

    return {
        "status": "success",
        "student_name": student["name"],
        "student_id": student_id,
        "summary": {
            "total_exams": total_exams,
            "average_percentage": round(average_percentage, 2),
            "total_score": total_score,
            "total_max_score": total_max_score
        },
        "exams": exams,
        "recurring_weaknesses": all_weaknesses,
        "recommendations": all_recommendations
    }


def get_class_statistics(tool_context: ToolContext) -> Dict[str, Any]:
    """
    Tool for teachers to view class-wide statistics.

    This tool:
    - Verifies the user is a TEACHER or ADMIN
    - Retrieves performance data for all students
    - Calculates class-wide metrics and trends

    Available to: TEACHERS, ADMINS

    Returns:
        Dictionary with class statistics or error message
    """
    if _db is None:
        return {
            "status": "error",
            "message": "Database not configured"
        }

    # Get current user
    user = _get_user_from_context(tool_context)
    if not user:
        return {
            "status": "error",
            "message": "Not authenticated. Please log in first."
        }

    # Check authorization
    if not user.can_view_class_statistics():
        logger.warning(
            f"User {user.user_id} ({user.role.value}) attempted to access "
            f"class statistics without permission"
        )
        return {
            "status": "error",
            "message": "Permission denied. Only teachers can view class statistics."
        }

    logger.info(f"get_class_statistics called by {user.name} ({user.role.value})")

    # Get all students
    all_students = _db.get_all_students()

    if not all_students:
        return {
            "status": "success",
            "message": "No students found in the system",
            "statistics": {}
        }

    # Calculate class-wide statistics
    student_performances = []
    all_class_weaknesses = []

    for student in all_students:
        student_id = student["student_id"]
        exams = _db.get_student_exams(student_id)

        if exams:
            total_score = sum(exam.get("total_score", 0) for exam in exams)
            total_max_score = sum(exam.get("max_score", 0) for exam in exams)
            avg_percentage = (total_score / total_max_score * 100) if total_max_score > 0 else 0

            student_performances.append({
                "student_id": student_id,
                "student_name": student["name"],
                "exams_taken": len(exams),
                "average_percentage": round(avg_percentage, 2)
            })

            # Collect weaknesses
            for exam in exams:
                exam_id = exam.get("exam_id")
                if exam_id:
                    analysis = _db.get_analysis(exam_id)
                    if analysis and analysis.get("weaknesses"):
                        all_class_weaknesses.extend(analysis["weaknesses"])

    # Calculate class averages
    if student_performances:
        class_average = sum(s["average_percentage"] for s in student_performances) / len(student_performances)
        highest_performer = max(student_performances, key=lambda s: s["average_percentage"])
        lowest_performer = min(student_performances, key=lambda s: s["average_percentage"])
    else:
        class_average = 0
        highest_performer = None
        lowest_performer = None

    # Find most common weaknesses
    weakness_counts: Dict[str, int] = {}
    for weakness in all_class_weaknesses:
        topic = weakness.get("topic", "Unknown")
        weakness_counts[topic] = weakness_counts.get(topic, 0) + 1

    common_weaknesses = sorted(
        weakness_counts.items(),
        key=lambda x: x[1],
        reverse=True
    )[:5]  # Top 5 common weaknesses

    return {
        "status": "success",
        "class_summary": {
            "total_students": len(all_students),
            "students_with_exams": len(student_performances),
            "class_average_percentage": round(class_average, 2),
            "highest_performer": highest_performer,
            "lowest_performer": lowest_performer
        },
        "student_performances": student_performances,
        "common_weaknesses": [
            {"topic": topic, "occurrence_count": count}
            for topic, count in common_weaknesses
        ]
    }


def list_my_students(tool_context: ToolContext) -> Dict[str, Any]:
    """
    Tool for teachers to list all students in the system.

    Available to: TEACHERS, ADMINS

    Returns:
        Dictionary with list of students or error message
    """
    if _db is None:
        return {
            "status": "error",
            "message": "Database not configured"
        }

    # Get current user
    user = _get_user_from_context(tool_context)
    if not user:
        return {
            "status": "error",
            "message": "Not authenticated. Please log in first."
        }

    # Check authorization
    if not (user.is_teacher() or user.is_admin()):
        logger.warning(
            f"User {user.user_id} ({user.role.value}) attempted to list "
            f"students without permission"
        )
        return {
            "status": "error",
            "message": "Permission denied. Only teachers can list students."
        }

    logger.info(f"list_my_students called by {user.name} ({user.role.value})")

    # Get all students
    students = _db.get_all_students()

    return {
        "status": "success",
        "total_students": len(students),
        "students": [
            {
                "student_id": s["student_id"],
                "name": s["name"]
            }
            for s in students
        ]
    }
