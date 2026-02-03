import uuid

from feedback_agent.database import StudentDatabase


def test_add_student_idempotent(tmp_path):
    db_path = tmp_path / "students.db"
    db = StudentDatabase(str(db_path))
    db.add_student("s1", "Alice")
    db.add_student("s1", "Alice")
    students = db.get_all_students()
    assert len(students) == 1


def test_student_lookup_and_history_order(tmp_path):
    db_path = tmp_path / "students.db"
    db = StudentDatabase(str(db_path))

    student_id = str(uuid.uuid4())
    db.add_student(student_id, "Alice Johnson")

    fetched = db.get_student_by_name("alice johnson")
    assert fetched is not None
    assert fetched["student_id"] == student_id

    exam_id_1 = str(uuid.uuid4())
    exam_id_2 = str(uuid.uuid4())

    db.log_exam(exam_id_1, student_id, "Math", 8, 10)
    db.log_analysis(exam_id_1, weaknesses=["Algebra"], topics=["Algebra"])

    db.log_exam(exam_id_2, student_id, "Science", 9, 10)
    db.log_analysis(exam_id_2, weaknesses=["Chemistry"], topics=["Chemistry"])

    history = db.get_student_history(student_id)
    assert len(history) == 2
    assert history[0]["exam_id"] == exam_id_1
    assert history[1]["exam_id"] == exam_id_2
