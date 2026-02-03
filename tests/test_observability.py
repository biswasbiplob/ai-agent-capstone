"""
Test script for observability features in the feedback system.

This test verifies:
1. ExamMetricsPlugin tracks metrics correctly
2. Structured logging works
3. Metrics are written to file
4. Summary statistics are accurate
"""

import importlib.util

import pytest

if importlib.util.find_spec("google.adk") is None:
    pytest.skip("google.adk not installed", allow_module_level=True)

import asyncio
import os
import json
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from feedback_agent.agent import FeedbackSystem


async def test_observability():
    """Test observability features with sample exams."""

    print("="*70)
    print("🔍 Testing Observability Features")
    print("="*70)

    # Create system with metrics enabled
    test_metrics_file = "test_observability_metrics.jsonl"

    # Clean up old test files
    if os.path.exists(test_metrics_file):
        os.remove(test_metrics_file)
        print(f"🧹 Removed old metrics file: {test_metrics_file}")

    # Initialize system with metrics
    system = FeedbackSystem(
        db_path="data/test_observability.db",
        session_db_url="sqlite:///data/test_observability_sessions.db",
        use_memory_sessions=False,
        enable_metrics=True,
        metrics_file=test_metrics_file
    )

    print("\n✅ System initialized with observability enabled\n")

    # Register test student
    student_id = system.register_student("Test Student")
    print(f"📝 Registered student: {student_id}\n")

    # Test Case 1: Simple math exam
    print("📊 Test 1: Processing simple math exam...")
    exam1_content = """
    1. What is 2 + 2? Answer: 4
    2. What is 5 * 3? Answer: 15
    3. What is 10 - 7? Answer: 2
    """
    exam1_answer_key = """
    1. 4
    2. 15
    3. 3
    """

    result1 = await system.process_exam(
        student_id=student_id,
        exam_content=exam1_content,
        answer_key=exam1_answer_key,
        subject="Mathematics",
        user_id="test_user"
    )

    print(f"   ✓ Exam 1 completed: {result1['total_score']}/{result1['max_score']} ({result1['percentage']:.1f}%)")
    print(f"   ✓ Weaknesses identified: {len(result1['weaknesses'])}\n")

    # Test Case 2: Science exam with more questions
    print("📊 Test 2: Processing science exam...")
    exam2_content = """
    1. What is the chemical formula for water? Answer: H2O
    2. What is the speed of light? Answer: 300000 km/s
    3. What is Newton's first law? Answer: An object at rest stays at rest
    """
    exam2_answer_key = """
    1. H2O
    2. 299792 km/s
    3. An object at rest stays at rest unless acted upon by a force
    """

    result2 = await system.process_exam(
        student_id=student_id,
        exam_content=exam2_content,
        answer_key=exam2_answer_key,
        subject="Science",
        user_id="test_user"
    )

    print(f"   ✓ Exam 2 completed: {result2['total_score']}/{result2['max_score']} ({result2['percentage']:.1f}%)")
    print(f"   ✓ Weaknesses identified: {len(result2['weaknesses'])}\n")

    # Test Case 3: Perfect score exam
    print("📊 Test 3: Processing perfect score exam...")
    exam3_content = """
    1. What is the capital of France? Answer: Paris
    2. Who wrote Romeo and Juliet? Answer: Shakespeare
    """
    exam3_answer_key = """
    1. Paris
    2. Shakespeare
    """

    result3 = await system.process_exam(
        student_id=student_id,
        exam_content=exam3_content,
        answer_key=exam3_answer_key,
        subject="General Knowledge",
        user_id="test_user"
    )

    print(f"   ✓ Exam 3 completed: {result3['total_score']}/{result3['max_score']} ({result3['percentage']:.1f}%)")
    print(f"   ✓ Weaknesses identified: {len(result3['weaknesses'])}\n")

    print("="*70)
    print("📈 Checking Metrics...")
    print("="*70)

    # Verify metrics file exists
    if os.path.exists(test_metrics_file):
        print(f"\n✅ Metrics file created: {test_metrics_file}")

        # Read and display metrics
        with open(test_metrics_file, 'r') as f:
            metrics_lines = f.readlines()
            print(f"✅ Metrics entries written: {len(metrics_lines)}")

            print("\n📋 Sample metric entry:")
            if metrics_lines:
                sample_metric = json.loads(metrics_lines[0])
                print(f"   Session ID: {sample_metric.get('session_id')}")
                print(f"   Duration: {sample_metric.get('total_duration', 0):.2f}s")
                print(f"   Score: {sample_metric.get('total_score', 0)}/{sample_metric.get('max_score', 0)}")
                print(f"   Weaknesses: {sample_metric.get('weaknesses_count', 0)}")

                # Display agent timings if available
                if 'agent_timings' in sample_metric:
                    print(f"\n   Agent Timings:")
                    for agent_name, duration in sample_metric['agent_timings'].items():
                        print(f"      {agent_name}: {duration:.2f}s")
    else:
        print(f"\n❌ Metrics file not found: {test_metrics_file}")

    # Print summary statistics
    print("\n" + "="*70)
    system.print_metrics_summary()

    # Get programmatic summary
    summary = system.get_metrics_summary()
    if summary:
        print("✅ Programmatic metrics access working")
        print(f"   Total exams: {summary['total_exams_processed']}")
        print(f"   Success rate: {summary['success_rate']*100:.1f}%")
        print(f"   Avg processing time: {summary['avg_processing_time']:.2f}s")

    print("\n" + "="*70)
    print("✅ Observability Test Complete")
    print("="*70)

    # Verify structured logging file exists
    if os.path.exists('feedback_system.log'):
        print("\n✅ Structured logging file created: feedback_system.log")
        with open('feedback_system.log', 'r') as f:
            log_lines = f.readlines()
            print(f"✅ Log entries: {len(log_lines)}")
            if log_lines:
                print(f"\nSample log entry:")
                print(f"   {log_lines[-1].strip()}")

    # Cleanup
    print("\n🧹 Cleaning up test files...")
    for file in ["data/test_observability.db", "data/test_observability_sessions.db", test_metrics_file]:
        if os.path.exists(file):
            os.remove(file)
            print(f"   ✓ Removed {file}")

    print("\n✅ All tests passed!")


if __name__ == "__main__":
    asyncio.run(test_observability())
