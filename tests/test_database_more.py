import uuid

from feedback_agent.database import StudentDatabase


def test_get_student_exams_sorted_desc(tmp_path):
    db_path = tmp_path / "students.db"
    db = StudentDatabase(str(db_path))
    student_id = str(uuid.uuid4())
    db.add_student(student_id, "Sort Test")

    exam_id_1 = str(uuid.uuid4())
    exam_id_2 = str(uuid.uuid4())

    db.log_exam(exam_id_1, student_id, "Math", 8, 10)
    db.log_exam(exam_id_2, student_id, "Science", 9, 10)

    exams = db.get_student_exams(student_id)
    assert len(exams) == 2
    assert exams[0]["exam_id"] == exam_id_2
    assert exams[1]["exam_id"] == exam_id_1


def test_get_analysis_topics_and_recommendations(tmp_path):
    db_path = tmp_path / "students.db"
    db = StudentDatabase(str(db_path))
    student_id = str(uuid.uuid4())
    db.add_student(student_id, "Analysis Test")

    exam_id = str(uuid.uuid4())
    db.log_exam(exam_id, student_id, "History", 5, 10)

    db.log_analysis(
        exam_id,
        weaknesses=[{"topic": "Revolutions"}],
        topics=["Revolutions"],
        recommendations='{"plan": "review"}',
    )

    analysis = db.get_analysis(exam_id)
    assert analysis is not None
    assert analysis["weaknesses"][0]["topic"] == "Revolutions"
    assert analysis["topics"] == ["Revolutions"]
    assert analysis["recommendations"] == '{"plan": "review"}'
