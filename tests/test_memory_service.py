import time
import uuid

from feedback_agent.database import StudentDatabase
from feedback_agent.memory import MemoryService


def _log_exam(db: StudentDatabase, student_id: str, subject: str, score: int, max_score: int, weaknesses):
    exam_id = str(uuid.uuid4())
    db.log_exam(exam_id, student_id, subject, score, max_score)
    db.log_analysis(exam_id, weaknesses=weaknesses, topics=[subject])
    return exam_id


def test_memory_service_recurring_and_velocity(tmp_path):
    db_path = tmp_path / "students.db"
    db = StudentDatabase(str(db_path))
    student_id = str(uuid.uuid4())
    db.add_student(student_id, "Test Student")
    memory = MemoryService(db)

    _log_exam(db, student_id, "Math", 6, 10, [{"topic": "Algebra", "severity": "high"}])
    time.sleep(0.01)
    _log_exam(db, student_id, "Math", 7, 10, [{"topic": "Algebra", "severity": "medium"}])
    time.sleep(0.01)
    _log_exam(db, student_id, "Science", 9, 10, [{"topic": "Chemistry", "severity": "low"}])

    recurring = memory.get_recurring_weaknesses(student_id, min_occurrences=2)
    assert any(p.topic == "Algebra" and p.occurrences == 2 for p in recurring)

    velocity = memory.get_learning_velocity(student_id)
    assert velocity is not None
    assert velocity.total_exams == 3
    assert 0 <= velocity.average_score <= 100


def test_memory_service_recommendations(tmp_path):
    db_path = tmp_path / "students.db"
    db = StudentDatabase(str(db_path))
    student_id = str(uuid.uuid4())
    db.add_student(student_id, "Test Student")
    memory = MemoryService(db)

    _log_exam(db, student_id, "History", 5, 10, [{"topic": "Revolutions", "severity": "high"}])
    time.sleep(0.01)
    _log_exam(db, student_id, "History", 6, 10, [{"topic": "Revolutions", "severity": "high"}])

    recommendations = memory.recommend_review_topics(student_id, max_topics=3)
    assert recommendations
    assert recommendations[0]["topic"] == "Revolutions"
