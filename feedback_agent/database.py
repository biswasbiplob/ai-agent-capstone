import sqlite3
import json
from typing import List, Dict, Optional
from datetime import datetime

class StudentDatabase:
    def __init__(self, db_path: str = "students.db"):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Students table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS students (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL
            )
        ''')
        
        # Exams table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS exams (
                id TEXT PRIMARY KEY,
                student_id TEXT NOT NULL,
                subject TEXT NOT NULL,
                date TEXT NOT NULL,
                total_score REAL,
                max_score REAL,
                FOREIGN KEY (student_id) REFERENCES students (id)
            )
        ''')
        
        # Results/Weaknesses table
        # Storing weaknesses as a JSON string for simplicity in this iteration
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS analysis (
                exam_id TEXT PRIMARY KEY,
                weaknesses TEXT,
                recommendations TEXT,
                FOREIGN KEY (exam_id) REFERENCES exams (id)
            )
        ''')
        
        conn.commit()
        conn.close()

    def add_student(self, student_id: str, name: str):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('INSERT OR IGNORE INTO students (id, name) VALUES (?, ?)', (student_id, name))
        conn.commit()
        conn.close()

    def log_exam(self, exam_id: str, student_id: str, subject: str, total_score: float, max_score: float):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        date = datetime.now().isoformat()
        cursor.execute('''
            INSERT INTO exams (id, student_id, subject, date, total_score, max_score)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (exam_id, student_id, subject, date, total_score, max_score))
        conn.commit()
        conn.close()

    def log_analysis(self, exam_id: str, weaknesses: Optional[List[str]] = None, recommendations: Optional[str] = None):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Check if record exists to decide whether to insert or update specific fields
            cursor.execute('SELECT weaknesses, recommendations FROM analysis WHERE exam_id = ?', (exam_id,))
            row = cursor.fetchone()
            
            if row:
                current_weaknesses, current_recommendations = row
                new_weaknesses = json.dumps(weaknesses) if weaknesses is not None else current_weaknesses
                new_recommendations = recommendations if recommendations is not None else current_recommendations
                
                cursor.execute('''
                    UPDATE analysis 
                    SET weaknesses = ?, recommendations = ?
                    WHERE exam_id = ?
                ''', (new_weaknesses, new_recommendations, exam_id))
            else:
                cursor.execute('''
                    INSERT INTO analysis (exam_id, weaknesses, recommendations)
                    VALUES (?, ?, ?)
                ''', (exam_id, json.dumps(weaknesses or []), recommendations or ""))
            conn.commit()

    def get_student_history(self, student_id: str) -> List[Dict]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute('''
            SELECT e.subject, e.total_score, e.max_score, a.weaknesses
            FROM exams e
            LEFT JOIN analysis a ON e.id = a.exam_id
            WHERE e.student_id = ?
        ''', (student_id,))
        rows = cursor.fetchall()
        conn.close()
        
        history = []
        for row in rows:
            history.append({
                'subject': row['subject'],
                'score': row['total_score'],
                'max_score': row['max_score'],
                'weaknesses': json.loads(row['weaknesses']) if row['weaknesses'] else []
            })
        return history

    def get_exam(self, exam_id: str) -> Optional[Dict]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute('''
            SELECT e.total_score, e.max_score, a.weaknesses, a.recommendations
            FROM exams e
            LEFT JOIN analysis a ON e.id = a.exam_id
            WHERE e.id = ?
        ''', (exam_id,))
        row = cursor.fetchone()
        conn.close()

        if row:
            return {
                'grading': {
                    'total_score': row['total_score'],
                    'max_score': row['max_score']
                },
                'analysis': {
                    'weaknesses': json.loads(row['weaknesses']) if row['weaknesses'] else [],
                    'recommendations': row['recommendations'] # This is a string (JSON or text)
                }
            }
        return None

    def get_all_students(self) -> List[Dict]:
        """Get all students in the database."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute('SELECT id, name FROM students')
        rows = cursor.fetchall()
        conn.close()

        return [{'student_id': row['id'], 'name': row['name']} for row in rows]

    def get_student(self, student_id: str) -> Optional[Dict]:
        """Get a specific student by ID."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute('SELECT id, name FROM students WHERE id = ?', (student_id,))
        row = cursor.fetchone()
        conn.close()

        if row:
            return {'student_id': row['id'], 'name': row['name']}
        return None

    def get_student_exams(self, student_id: str) -> List[Dict]:
        """Get all exams for a specific student."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id, student_id, subject, date, total_score, max_score
            FROM exams
            WHERE student_id = ?
            ORDER BY date DESC
        ''', (student_id,))
        rows = cursor.fetchall()
        conn.close()

        exams = []
        for row in rows:
            exams.append({
                'exam_id': row['id'],
                'student_id': row['student_id'],
                'subject': row['subject'],
                'date': row['date'],
                'total_score': row['total_score'],
                'max_score': row['max_score']
            })
        return exams

    def get_analysis(self, exam_id: str) -> Optional[Dict]:
        """Get analysis data for a specific exam."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute('''
            SELECT weaknesses, recommendations
            FROM analysis
            WHERE exam_id = ?
        ''', (exam_id,))
        row = cursor.fetchone()
        conn.close()

        if row:
            return {
                'weaknesses': json.loads(row['weaknesses']) if row['weaknesses'] else [],
                'recommendations': row['recommendations']
            }
        return None
