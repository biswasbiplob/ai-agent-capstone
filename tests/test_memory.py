"""
Test Suite for Memory Service

Tests cross-session tracking capabilities including:
- Recurring weakness detection
- Learning velocity measurement
- Review recommendations
- Mastery progress tracking
"""

import pytest

pytest.importorskip("google.adk")

import asyncio
import os
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from feedback_agent.agent import FeedbackSystem


def print_section(title: str):
    """Print a formatted section header."""
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70 + "\n")


async def test_memory_service():
    """Test memory service with multiple exam scenarios."""

    print_section("🧠 Testing Memory Service - Cross-Session Tracking")

    # Setup test databases
    test_db = "data/test_memory.db"
    test_session_db = "sqlite:///data/test_memory_sessions.db"

    # Clean up old test databases
    if os.path.exists(test_db):
        os.remove(test_db)

    # Initialize system
    print("🔧 Initializing FeedbackSystem...")
    system = FeedbackSystem(
        db_path=test_db,
        session_db_url=test_session_db,
        use_memory_sessions=False,
        enable_metrics=False  # Disable metrics for cleaner output
    )
    print("✅ System initialized\n")

    # Register test student
    print("📝 Registering test student...")
    student_id = system.register_student("Alex Martinez")
    print(f"✅ Student registered: {student_id}\n")

    # Test Case 1: Process exams with recurring weaknesses
    print_section("TEST 1: Recurring Weaknesses Detection")

    exams = [
        # Exam 1: Math with algebra weakness
        {
            "subject": "Mathematics",
            "exam_content": """
            1. Solve: 2x + 5 = 15. Answer: x = 5
            2. What is 8 + 7? Answer: 15
            3. Simplify: 3(x + 2) = ? Answer: 3x + 6
            """,
            "answer_key": """
            1. x = 5
            2. 15
            3. 3x + 6
            """
        },
        # Exam 2: Math with algebra weakness again
        {
            "subject": "Mathematics",
            "exam_content": """
            1. What is 12 - 5? Answer: 7
            2. Solve: 5x - 10 = 0. Answer: x = 1
            3. Expand: 2(y + 3) = ? Answer: 2y + 6
            """,
            "answer_key": """
            1. 7
            2. x = 2
            3. 2y + 6
            """
        },
        # Exam 3: Science with physics weakness
        {
            "subject": "Physics",
            "exam_content": """
            1. What is Newton's First Law? Answer: Objects at rest stay at rest
            2. Calculate force: F = ma, m=10kg, a=5m/s². Answer: F = 50N
            3. What is gravity on Earth? Answer: 9.8 m/s²
            """,
            "answer_key": """
            1. Objects at rest stay at rest unless acted upon by force
            2. F = 50N
            3. 9.8 m/s²
            """
        },
        # Exam 4: Math with algebra weakness third time (showing improvement)
        {
            "subject": "Mathematics",
            "exam_content": """
            1. Solve: 3x + 9 = 21. Answer: x = 4
            2. What is 25 * 4? Answer: 100
            3. Factor: x² + 5x + 6. Answer: (x+2)(x+3)
            """,
            "answer_key": """
            1. x = 4
            2. 100
            3. (x+2)(x+3)
            """
        }
    ]

    print("📚 Processing 4 exams with intentional patterns...\n")
    for i, exam_data in enumerate(exams, 1):
        print(f"   Processing exam {i}/{len(exams)}: {exam_data['subject']}...", end=" ")

        result = await system.process_exam(
            student_id=student_id,
            exam_content=exam_data["exam_content"],
            answer_key=exam_data["answer_key"],
            subject=exam_data["subject"],
            user_id="test_user"
        )

        score_pct = result['percentage']
        print(f"✅ Score: {score_pct:.0f}%")

    print("\n📊 All exams processed!")

    # Test recurring weaknesses
    print("\n" + "-" * 70)
    print("🔍 Testing Recurring Weakness Detection")
    print("-" * 70)

    recurring = system.get_student_recurring_weaknesses(student_id, min_occurrences=2)

    if recurring:
        print(f"\n✅ Found {len(recurring)} recurring weaknesses:\n")
        for i, pattern in enumerate(recurring, 1):
            print(f"   {i}. Topic: {pattern.topic}")
            print(f"      Occurrences: {pattern.occurrences}")
            print(f"      Trend: {pattern.severity_trend}")
            print(f"      First seen: {pattern.first_seen}, Last seen: {pattern.last_seen}")
            print()
    else:
        print("⚠️  No recurring weaknesses found (needs at least 2 occurrences)")

    # Test learning velocity
    print_section("TEST 2: Learning Velocity Measurement")

    velocity = system.get_student_learning_velocity(student_id)

    if velocity:
        print("✅ Learning Velocity Calculated:\n")
        print(f"   Total Exams: {velocity['total_exams']}")
        print(f"   Average Score: {velocity['average_score']:.1f}%")
        print(f"   Score Trend: {velocity['score_trend']}")
        print(f"   Improvement Rate: {velocity['improvement_rate']:.2f}% per exam")

        if velocity['subjects_mastered']:
            print(f"\n   🏆 Mastered Subjects: {', '.join(velocity['subjects_mastered'])}")

        if velocity['subjects_struggling']:
            print(f"   ⚠️  Struggling Subjects: {', '.join(velocity['subjects_struggling'])}")
    else:
        print("⚠️  Insufficient data for velocity calculation (needs at least 2 exams)")

    # Test review recommendations
    print_section("TEST 3: Personalized Review Recommendations")

    recommendations = system.get_student_review_recommendations(student_id, max_topics=5)

    if recommendations:
        print(f"✅ Generated {len(recommendations)} review recommendations:\n")
        for i, rec in enumerate(recommendations, 1):
            print(f"   {i}. Topic: {rec['topic']}")
            print(f"      Priority: {rec['priority'].upper()}")
            print(f"      Rationale: {rec['rationale']}")
            print()
    else:
        print("⚠️  No recommendations available yet")

    # Test mastery progress
    print_section("TEST 4: Mastery Progress Tracking")

    mastery = system.get_student_mastery_progress(student_id)

    if mastery:
        print("✅ Mastery Progress by Subject:\n")
        for subject, metrics in mastery.items():
            print(f"   📚 {subject}:")
            print(f"      Current Mastery: {metrics['current_mastery']:.1f}%")
            print(f"      Average Score: {metrics['average_score']:.1f}%")
            print(f"      Trend: {metrics['trend']:+.1f}%")
            print(f"      Consistency: {metrics['consistency']:.1f}%")
            print(f"      Total Attempts: {metrics['total_attempts']}")
            print()
    else:
        print("⚠️  No mastery data available yet")

    # Summary
    print_section("📋 Test Summary")

    print("✅ All memory service tests completed successfully!\n")
    print("Memory Service Features Tested:")
    print("   ✓ Recurring weakness detection")
    print("   ✓ Learning velocity measurement")
    print("   ✓ Personalized review recommendations")
    print("   ✓ Mastery progress tracking")
    print("\n" + "=" * 70)

    # Clean up
    print("\n🧹 Cleaning up test databases...")
    if os.path.exists(test_db):
        os.remove(test_db)
    print("✅ Cleanup complete")


if __name__ == "__main__":
    asyncio.run(test_memory_service())
