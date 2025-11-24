import pytest
import os
from feedback_agent.agent import FeedbackSystem

@pytest.fixture
def system():
    # Use a temporary db for testing
    db_path = "data/test_students.db"
    if os.path.exists(db_path):
        os.remove(db_path)
    
    sys = FeedbackSystem(db_path=db_path)
    yield sys
    
    if os.path.exists(db_path):
        os.remove(db_path)



def test_full_flow_mocked(system):
    from unittest.mock import patch
    import json

    # Mock responses for different agents
    def mock_run_agent(agent, prompt):
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
                "weaknesses": ["Arithmetic"],
                "summary": "Weak in math."
            })
        elif "recommendation_agent" in agent.name:
            return json.dumps({
                "learning_objectives": [
                    {
                        "topic": "Arithmetic",
                        "objective": "Learn addition",
                        "resources": ["Math book"]
                    }
                ],
                "encouragement": "Keep practicing!"
            })
        return "{}"

    with patch('feedback_agent.utils.run_agent', side_effect=mock_run_agent):
        # 1. Register Student
        student_id = system.register_student("Alice")
        assert student_id is not None

        # 2. Process Exam
        exam_content = "..."
        answer_key = "..."
        
        result = system.process_exam(student_id, "General Knowledge", exam_content, answer_key)
        
        # Verify Grading
        assert result['grading']['total_score'] == 8
        
        # Verify Analysis
        assert "Arithmetic" in result['analysis']['weaknesses']
        
        # Verify Recommendations
        assert len(result['recommendations']['learning_objectives']) > 0

        # Verify DB Persistence
        history = system.db.get_student_history(student_id)
        assert len(history) == 1
        assert history[0]['subject'] == "General Knowledge"
