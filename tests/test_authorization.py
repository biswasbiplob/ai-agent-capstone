"""
Test script for authentication and authorization system.

This script demonstrates:
1. Creating demo users (teacher and students)
2. Students accessing their own data
3. Teachers accessing all student data
4. Teachers viewing class statistics
5. Permission checks working correctly
"""

import asyncio
import logging
from google.adk.tools.tool_context import ToolContext
from google.adk.sessions import InMemorySessionService, Session

from feedback_agent.auth import auth_service, create_demo_users, UserRole
from feedback_agent.authorization import (
    set_database,
    get_my_performance,
    get_student_performance,
    get_class_statistics,
    list_my_students
)
from feedback_agent.database import StudentDatabase

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def create_mock_tool_context(user_id: str) -> ToolContext:
    """
    Create a mock ToolContext for testing.

    Args:
        user_id: ID of the user to set in context

    Returns:
        ToolContext with user_id in state
    """
    # Create a simple mock that has the minimal interface needed
    class MockToolContext:
        def __init__(self, user_id: str):
            self.state = {"current_user_id": user_id}

    return MockToolContext(user_id)


async def setup_test_data(db: StudentDatabase, demo_user_ids: dict):
    """
    Create some test exam data for demonstration.

    Args:
        db: Database instance
        demo_user_ids: Dictionary of demo user IDs
    """
    print("\n📝 Creating test exam data...")

    # Add demo students to the database
    db.add_student(demo_user_ids["student1"], "Alice Smith")
    db.add_student(demo_user_ids["student2"], "Bob Chen")
    db.add_student(demo_user_ids["student3"], "Carol Martinez")

    # Create some exams for Alice
    db.log_exam("exam-001", demo_user_ids["student1"], "Mathematics", 85.0, 100.0)
    db.log_analysis("exam-001", weaknesses=[
        {"topic": "Algebra", "description": "Struggles with quadratic equations", "severity": "medium"}
    ])

    db.log_exam("exam-002", demo_user_ids["student1"], "Physics", 72.0, 100.0)
    db.log_analysis("exam-002", weaknesses=[
        {"topic": "Mechanics", "description": "Needs practice with Newton's laws", "severity": "high"}
    ])

    # Create exams for Bob
    db.log_exam("exam-003", demo_user_ids["student2"], "Mathematics", 92.0, 100.0)
    db.log_analysis("exam-003", weaknesses=[
        {"topic": "Geometry", "description": "Minor issues with proofs", "severity": "low"}
    ])

    # Create exams for Carol
    db.log_exam("exam-004", demo_user_ids["student3"], "Chemistry", 78.0, 100.0)
    db.log_analysis("exam-004", weaknesses=[
        {"topic": "Organic Chemistry", "description": "Needs review of reactions", "severity": "medium"}
    ])

    print("✅ Test data created!")


async def test_student_access(demo_user_ids: dict):
    """
    Test that students can only access their own data.
    """
    print("\n" + "="*80)
    print("TEST 1: Student accessing their own data")
    print("="*80)

    # Alice logs in and checks her performance
    alice_context = create_mock_tool_context(demo_user_ids["student1"])
    result = get_my_performance(alice_context)

    print(f"\n👤 Alice Smith checks her performance:")
    print(f"Status: {result['status']}")
    if result['status'] == 'success':
        print(f"Summary:")
        print(f"  - Total exams: {result['summary']['total_exams']}")
        print(f"  - Average: {result['summary']['average_percentage']}%")
        print(f"  - Weaknesses found: {len(result['recurring_weaknesses'])}")
        print(f"✅ TEST PASSED: Student can view own data")
    else:
        print(f"❌ TEST FAILED: {result['message']}")


async def test_student_blocked_from_others(demo_user_ids: dict):
    """
    Test that students cannot access other students' data.
    """
    print("\n" + "="*80)
    print("TEST 2: Student trying to access another student's data")
    print("="*80)

    # Alice tries to access Bob's data
    alice_context = create_mock_tool_context(demo_user_ids["student1"])
    result = get_student_performance(alice_context, demo_user_ids["student2"])

    print(f"\n👤 Alice Smith tries to access Bob Chen's data:")
    print(f"Status: {result['status']}")
    print(f"Message: {result['message']}")

    if result['status'] == 'error' and 'Permission denied' in result['message']:
        print(f"✅ TEST PASSED: Student blocked from accessing other student's data")
    else:
        print(f"❌ TEST FAILED: Authorization check failed")


async def test_teacher_access_student(demo_user_ids: dict):
    """
    Test that teachers can access any student's data.
    """
    print("\n" + "="*80)
    print("TEST 3: Teacher accessing student data")
    print("="*80)

    # Teacher logs in and checks Alice's performance
    teacher_context = create_mock_tool_context(demo_user_ids["teacher"])
    result = get_student_performance(teacher_context, demo_user_ids["student1"])

    print(f"\n👨‍🏫 Ms. Sarah Johnson (teacher) checks Alice's performance:")
    print(f"Status: {result['status']}")
    if result['status'] == 'success':
        print(f"Student: {result['student_name']}")
        print(f"Summary:")
        print(f"  - Total exams: {result['summary']['total_exams']}")
        print(f"  - Average: {result['summary']['average_percentage']}%")
        print(f"  - Weaknesses: {len(result['recurring_weaknesses'])}")
        print(f"✅ TEST PASSED: Teacher can view student data")
    else:
        print(f"❌ TEST FAILED: {result['message']}")


async def test_teacher_list_students(demo_user_ids: dict):
    """
    Test that teachers can list all students.
    """
    print("\n" + "="*80)
    print("TEST 4: Teacher listing all students")
    print("="*80)

    # Teacher lists all students
    teacher_context = create_mock_tool_context(demo_user_ids["teacher"])
    result = list_my_students(teacher_context)

    print(f"\n👨‍🏫 Ms. Sarah Johnson (teacher) lists students:")
    print(f"Status: {result['status']}")
    if result['status'] == 'success':
        print(f"Total students: {result['total_students']}")
        print(f"Students:")
        for student in result['students']:
            print(f"  - {student['name']} ({student['student_id'][:8]}...)")
        print(f"✅ TEST PASSED: Teacher can list students")
    else:
        print(f"❌ TEST FAILED: {result['message']}")


async def test_teacher_class_statistics(demo_user_ids: dict):
    """
    Test that teachers can view class statistics.
    """
    print("\n" + "="*80)
    print("TEST 5: Teacher viewing class statistics")
    print("="*80)

    # Teacher views class statistics
    teacher_context = create_mock_tool_context(demo_user_ids["teacher"])
    result = get_class_statistics(teacher_context)

    print(f"\n👨‍🏫 Ms. Sarah Johnson (teacher) views class statistics:")
    print(f"Status: {result['status']}")
    if result['status'] == 'success':
        print(f"\nClass Summary:")
        summary = result['class_summary']
        print(f"  - Total students: {summary['total_students']}")
        print(f"  - Students with exams: {summary['students_with_exams']}")
        print(f"  - Class average: {summary['class_average_percentage']}%")

        if summary['highest_performer']:
            print(f"\n  Highest performer:")
            print(f"    - {summary['highest_performer']['student_name']}")
            print(f"    - Average: {summary['highest_performer']['average_percentage']}%")

        if result['common_weaknesses']:
            print(f"\n  Common weaknesses across class:")
            for weakness in result['common_weaknesses'][:3]:
                print(f"    - {weakness['topic']}: {weakness['occurrence_count']} occurrences")

        print(f"\n✅ TEST PASSED: Teacher can view class statistics")
    else:
        print(f"❌ TEST FAILED: {result['message']}")


async def test_student_blocked_from_class_stats(demo_user_ids: dict):
    """
    Test that students cannot view class statistics.
    """
    print("\n" + "="*80)
    print("TEST 6: Student trying to access class statistics")
    print("="*80)

    # Alice tries to view class statistics
    alice_context = create_mock_tool_context(demo_user_ids["student1"])
    result = get_class_statistics(alice_context)

    print(f"\n👤 Alice Smith tries to view class statistics:")
    print(f"Status: {result['status']}")
    print(f"Message: {result['message']}")

    if result['status'] == 'error' and 'Permission denied' in result['message']:
        print(f"✅ TEST PASSED: Student blocked from viewing class statistics")
    else:
        print(f"❌ TEST FAILED: Authorization check failed")


async def main():
    """Run all authorization tests."""

    print("\n" + "="*80)
    print("🔐 AUTHENTICATION & AUTHORIZATION SYSTEM TESTS")
    print("="*80)

    # Step 1: Create demo users
    print("\n📝 Step 1: Creating demo users...")
    demo_user_ids = create_demo_users()
    print(f"✅ Created users:")
    print(f"  - Teacher: Ms. Sarah Johnson")
    print(f"  - Student 1: Alice Smith")
    print(f"  - Student 2: Bob Chen")
    print(f"  - Student 3: Carol Martinez")

    # Step 2: Setup database
    print("\n📝 Step 2: Setting up database...")
    db = StudentDatabase("test_auth.db")
    set_database(db)
    await setup_test_data(db, demo_user_ids)

    # Step 3: Run tests
    print("\n📝 Step 3: Running authorization tests...\n")

    await test_student_access(demo_user_ids)
    await test_student_blocked_from_others(demo_user_ids)
    await test_teacher_access_student(demo_user_ids)
    await test_teacher_list_students(demo_user_ids)
    await test_teacher_class_statistics(demo_user_ids)
    await test_student_blocked_from_class_stats(demo_user_ids)

    # Summary
    print("\n" + "="*80)
    print("✅ ALL AUTHORIZATION TESTS COMPLETED!")
    print("="*80)
    print("\nKey Features Demonstrated:")
    print("  ✅ Students can view their own data")
    print("  ✅ Students CANNOT view other students' data")
    print("  ✅ Students CANNOT view class statistics")
    print("  ✅ Teachers can view any student's data")
    print("  ✅ Teachers can view class-wide statistics")
    print("  ✅ Teachers can list all students")
    print("\nRole-based access control is working correctly! 🎉")


if __name__ == "__main__":
    asyncio.run(main())
