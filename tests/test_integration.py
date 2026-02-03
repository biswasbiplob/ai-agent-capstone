import asyncio
from unittest.mock import patch

from feedback_agent.database import StudentDatabase


def test_full_flow_mocked(tmp_path):
    import pytest
    pytest.importorskip("google.adk")
    db_path = tmp_path / "students.db"
    _ = StudentDatabase(str(db_path))

    def mock_run_agent(agent, prompt, image_path=None, image_bytes=None, session_state=None):
        import json

        if "grading_agent" in agent.name:
            return json.dumps({
                "total_score": 8,
                "max_score": 10,
                "corrections": [
                    {
                        "question_id": "Q1",
                        "student_answer": "Paris",
                        "correct_answer": "Paris",
                        "is_correct": True,
                        "score": 5,
                        "feedback": "Correct"
                    },
                    {
                        "question_id": "Q2",
                        "student_answer": "5",
                        "correct_answer": "4",
                        "is_correct": False,
                        "score": 3,
                        "feedback": "Incorrect"
                    }
                ],
                "general_feedback": "Good effort."
            })
        elif "analysis_agent" in agent.name:
            return json.dumps({
                "topics": ["Arithmetic"],
                "weaknesses": [
                    {"topic": "Arithmetic", "description": "Struggled with subtraction", "severity": "medium"}
                ],
                "summary": "Weak in math."
            })
        elif "study_materials_agent" in agent.name:
            return json.dumps({
                "study_materials": [
                    {"topic": "Arithmetic", "resources": [{"type": "textbook", "title": "Math 101", "description": "Basics", "difficulty": "beginner"}]}
                ]
            })
        elif "practice_problems_agent" in agent.name:
            return json.dumps({
                "practice_problems": [
                    {"topic": "Arithmetic", "problems": [{"difficulty": "easy", "problem": "2+2", "hint": "Add", "learning_goal": "Addition"}]}
                ]
            })
        elif "learning_strategy_agent" in agent.name:
            return json.dumps({
                "learning_strategy": {
                    "study_schedule": {"weekly_hours": 2, "sessions_per_week": 2, "session_duration": "30m"},
                    "learning_techniques": [{"technique": "Flashcards", "when_to_use": "Daily", "expected_benefit": "Recall"}],
                    "milestones": [{"timeline": "1 week", "goal": "Basics", "success_criteria": "80% correct"}]
                }
            })
        elif "recommendation_synthesizer" in agent.name:
            return json.dumps({
                "learning_objectives": [
                    {
                        "objective": "Learn addition",
                        "resources": ["Math 101"],
                        "practice_activities": ["2+2"],
                        "estimated_time": "1 week",
                        "priority": "high"
                    }
                ],
                "weekly_plan": {
                    "total_hours": 2,
                    "activities": [{"day": "Mon", "activity": "Practice", "duration": "30m", "resources_needed": ["Math 101"]}]
                },
                "encouragement": "Keep practicing!",
                "success_metrics": ["80% on quizzes"]
            })
        return "{}"

    with patch("feedback_agent.agent.run_agent", side_effect=mock_run_agent, create=True):
        from feedback_agent.agent import FeedbackSystem

        system = FeedbackSystem(
            db_path=str(db_path),
            use_memory_sessions=True,
            enable_metrics=False,
            enable_logging_plugin=False,
        )

        student_id = system.register_student("Alice")
        assert student_id is not None

        result = asyncio.run(
            system.process_exam(student_id, "...", "...", "General Knowledge")
        )

        assert result["total_score"] == 8
        assert "Arithmetic" in result["weaknesses"][0]["topic"]
        assert result["recommendations"]

        history = system.db.get_student_history(student_id)
        assert len(history) == 1
        assert history[0]["subject"] == "General Knowledge"
