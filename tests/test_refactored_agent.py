"""
Test script for the refactored FeedbackSystem.

This script validates that the new Runner-based implementation works correctly
and follows ADK best practices.
"""

import asyncio
import logging
import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
env_path = Path(__file__).parent / "feedback_agent" / ".env"
load_dotenv(env_path)

# Verify API key is loaded
if not os.getenv("GOOGLE_API_KEY"):
    print("⚠️  Warning: GOOGLE_API_KEY not found in environment!")
    print(f"   Tried loading from: {env_path}")
else:
    print(f"✅ API Key loaded successfully")

from feedback_agent.agent_refactored import FeedbackSystemRefactored

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def test_refactored_system():
    """Test the refactored feedback system."""

    print("\n" + "=" * 80)
    print("Testing Refactored FeedbackSystem with ADK Runner Pattern")
    print("=" * 80 + "\n")

    # Initialize system with in-memory sessions for testing
    system = FeedbackSystemRefactored(
        db_path="test_students_refactored.db",
        use_memory_sessions=True  # Use memory for quick testing
    )

    # Test 1: Register a student
    print("\n📝 Test 1: Registering a student...")
    student_name = "Alice Johnson"
    student_id = system.register_student(student_name)
    print(f"✅ Student registered: {student_name} (ID: {student_id})")

    # Test 2: Process an exam
    print("\n📝 Test 2: Processing an exam...")

    exam_content = """
    Question 1: What is the capital of France?
    Answer: London

    Question 2: What is 2 + 2?
    Answer: 4

    Question 3: Name the largest planet in our solar system.
    Answer: Earth
    """

    answer_key = """
    Question 1: Paris
    Question 2: 4
    Question 3: Jupiter
    """

    try:
        result = await system.process_exam(
            student_id=student_id,
            exam_content=exam_content,
            answer_key=answer_key,
            subject="General Knowledge",
            user_id="test_user"
        )

        print("\n✅ Exam processing complete!")
        print(f"\nExam ID: {result['exam_id']}")
        print(f"Subject: {result['subject']}")
        print(f"Database Status: {result.get('db_confirmation', 'Unknown')}")

        # Display results
        print("\n" + "-" * 80)
        print("📊 GRADING RESULT:")
        print("-" * 80)
        if result.get('grading_result'):
            print(result['grading_result'][:500] + "..." if len(result['grading_result']) > 500 else result['grading_result'])
        else:
            print("⚠️ No grading result found")

        print("\n" + "-" * 80)
        print("🔍 WEAKNESS ANALYSIS:")
        print("-" * 80)
        if result.get('weakness_analysis'):
            print(result['weakness_analysis'][:500] + "..." if len(result['weakness_analysis']) > 500 else result['weakness_analysis'])
        else:
            print("⚠️ No weakness analysis found")

        print("\n" + "-" * 80)
        print("📚 LEARNING PLAN:")
        print("-" * 80)
        if result.get('learning_plan'):
            print(result['learning_plan'][:500] + "..." if len(result['learning_plan']) > 500 else result['learning_plan'])
        else:
            print("⚠️ No learning plan found")

        print("\n" + "=" * 80)
        print("✅ ALL TESTS PASSED!")
        print("=" * 80)

    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return False

    return True


async def test_session_persistence():
    """Test that sessions persist correctly (when using DatabaseSessionService)."""

    print("\n" + "=" * 80)
    print("Testing Session Persistence")
    print("=" * 80 + "\n")

    # Initialize with database sessions
    system = FeedbackSystemRefactored(
        db_path="test_students_refactored.db",
        session_db_url="sqlite:///test_feedback_sessions.db",
        use_memory_sessions=False  # Use database for persistence test
    )

    student_id = system.register_student("Bob Smith")

    exam_content = "Q: What is 1+1? A: 2"
    answer_key = "Q: What is 1+1? A: 2"

    print("📝 Processing exam with persistent sessions...")
    result = await system.process_exam(
        student_id=student_id,
        exam_content=exam_content,
        answer_key=answer_key,
        subject="Math",
        user_id="test_user_2"
    )

    exam_id = result['exam_id']
    print(f"✅ Exam {exam_id} processed")

    # Verify in database
    db_result = system.db.get_exam(exam_id)
    if db_result:
        print("✅ Session data persisted to database successfully!")
        return True
    else:
        print("❌ Session data NOT found in database")
        return False


if __name__ == "__main__":
    print("\n🚀 Starting Refactored FeedbackSystem Tests\n")

    # Run basic test
    success = asyncio.run(test_refactored_system())

    if success:
        # Run persistence test
        print("\n")
        asyncio.run(test_session_persistence())

    print("\n🎉 Test suite complete!\n")
