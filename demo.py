"""
Interactive Demo of the AI Agent Feedback System

This demo showcases all key features:
1. Student registration
2. Exam processing (grading, analysis, recommendations)
3. Role-based access control
4. Metrics tracking
5. Image-based exam processing
"""

import asyncio
import json
import uuid
from pathlib import Path

from feedback_agent.agent import FeedbackSystem
from feedback_agent.auth import UserRole, auth_service
from feedback_agent.authorization import (
    get_class_statistics,
    get_my_performance,
    get_student_performance,
    list_my_students,
    set_database,
)


def print_section(title: str):
    """Print a formatted section header"""
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70 + "\n")


def create_mock_tool_context(user_id: str):
    """
    Create a mock ToolContext for testing authorization tools.

    Args:
        user_id: ID of the user to set in context

    Returns:
        Mock object with user_id in state
    """

    class MockToolContext:
        def __init__(self, user_id: str):
            self.state = {"current_user_id": user_id}

    return MockToolContext(user_id)


async def demo_basic_exam_processing():
    """Demo 1: Basic exam processing workflow"""
    print_section("DEMO 1: Basic Exam Processing")

    # Initialize system
    print("🔧 Initializing FeedbackSystem...")
    system = FeedbackSystem(
        db_path="data/demo.db",
        session_db_url="sqlite:///data/demo_sessions.db",
        enable_metrics=True,
        metrics_file="demo_metrics.jsonl",
    )
    print("✅ System initialized\n")

    # Register a student
    print("📝 Registering student...")
    student_name = "Alice Johnson"
    student_id = system.register_student(student_name)
    print(f"✅ Registered: {student_name} (ID: {student_id})\n")

    # Create sample exam
    print("📋 Processing math exam...")
    exam_content = """
    1. What is 5 + 3? Answer: 8
    2. What is 10 - 4? Answer: 5
    3. What is 3 × 4? Answer: 12
    4. What is 20 ÷ 5? Answer: 4
    5. What is 7 + 2? Answer: 9
    """

    answer_key = """
    1. 8
    2. 6
    3. 12
    4. 4
    5. 9
    """

    # Process exam
    result = await system.process_exam(
        student_id=student_id,
        exam_content=exam_content,
        answer_key=answer_key,
        subject="Mathematics",
        user_id="demo_user",
    )

    # Display results
    print("\n📊 RESULTS:")
    print(
        f"   Score: {result['total_score']}/{result['max_score']} ({result['percentage']:.1f}%)"
    )
    print(f"   Weaknesses identified: {len(result['weaknesses'])}")

    if result["weaknesses"]:
        print("\n   Weaknesses:")
        for i, weakness in enumerate(result["weaknesses"], 1):
            print(f"      {i}. {weakness['topic']} ({weakness['severity']})")
            print(f"         {weakness['description']}")

    print("\n   Recommendations:")
    try:
        recommendations = json.loads(result["recommendations"])
        for i, obj in enumerate(recommendations.get("learning_objectives", []), 1):
            print(f"      {i}. {obj['objective']}")
            print(f"         Time: {obj.get('estimated_time', 'N/A')}")
    except (json.JSONDecodeError, KeyError):
        print(f"      {result['recommendations'][:200]}...")

    # Show metrics
    print("\n📈 PERFORMANCE METRICS:")
    summary = system.get_metrics_summary()
    if summary:
        print(f"   Total exams processed: {summary['total_exams_processed']}")
        print(f"   Average processing time: {summary['avg_processing_time']:.2f}s")
        print(f"   Success rate: {summary['success_rate'] * 100:.1f}%")

    return system, student_id


async def demo_role_based_access():
    """Demo 2: Role-based access control"""
    print_section("DEMO 2: Role-Based Access Control")

    # Initialize database
    from feedback_agent.database import StudentDatabase

    db = StudentDatabase("data/demo.db")

    # Configure authorization tools with database
    set_database(db)

    # Register users
    print("👥 Registering users...")
    student_user = auth_service.register_user(
        "student_001", "Bob Smith", UserRole.STUDENT
    )
    teacher_user = auth_service.register_user(
        "teacher_001", "Dr. Jane Doe", UserRole.TEACHER
    )
    print(f"✅ Student: {student_user.name} ({student_user.role.value})")
    print(f"✅ Teacher: {teacher_user.name} ({teacher_user.role.value})\n")

    # Add students to database and create test exam data
    print("📝 Creating test exam data...")
    db.add_student(student_user.user_id, student_user.name)
    exam_id = str(uuid.uuid4())
    db.log_exam(exam_id, student_user.user_id, "Mathematics", 85.0, 100.0)
    db.log_analysis(
        exam_id,
        weaknesses=[
            {
                "topic": "Algebra",
                "description": "Struggles with quadratic equations",
                "severity": "medium",
            }
        ],
    )
    print("✅ Test data created!\n")

    # Demo: Student accessing own data
    print("📊 Student accessing own performance...")
    try:
        student_context = create_mock_tool_context(student_user.user_id)
        performance = get_my_performance(student_context)
        if performance.get("status") == "success":
            print("✅ Success! Student can see own data")
            print(
                f"   Exams found: {performance.get('summary', {}).get('total_exams', 0)}"
            )
        else:
            print(f"⚠️  Warning: {performance.get('message', 'Unknown error')}")
    except Exception as e:
        print(f"❌ Error: {e}")

    # Demo: Student trying to access other student
    print("\n🔒 Student trying to access another student's data...")
    try:
        student_context = create_mock_tool_context(student_user.user_id)
        other_performance = get_student_performance(student_context, "other_student_id")
        if other_performance.get(
            "status"
        ) == "error" and "Permission denied" in other_performance.get("message", ""):
            print(f"✅ Correctly blocked: {other_performance['message']}")
        else:
            print("⚠️ Unexpected: Student accessed other student's data!")
    except Exception as e:
        print(f"❌ Error: {e}")

    # Demo: Teacher accessing student data
    print("\n👨‍🏫 Teacher accessing student performance...")
    try:
        teacher_context = create_mock_tool_context(teacher_user.user_id)
        student_list = list_my_students(teacher_context)
        if student_list.get("status") == "success":
            print("✅ Success! Teacher can see all students")
            print(f"   Total students: {len(student_list.get('students', []))}")
        else:
            print(f"⚠️  Warning: {student_list.get('message', 'Unknown error')}")
    except Exception as e:
        print(f"❌ Error: {e}")

    # Demo: Teacher viewing class statistics
    print("\n📈 Teacher viewing class statistics...")
    try:
        teacher_context = create_mock_tool_context(teacher_user.user_id)
        stats = get_class_statistics(teacher_context)
        if stats.get("status") == "success":
            print("✅ Success! Teacher can see class stats")
            print(f"   Total exams: {stats.get('total_exams', 0)}")
            print(f"   Average score: {stats.get('average_score', 0):.1f}%")
        else:
            print(f"⚠️  Warning: {stats.get('message', 'Unknown error')}")
    except Exception as e:
        print(f"❌ Error: {e}")


async def demo_image_processing():
    """Demo 3: Image-based exam processing"""
    print_section("DEMO 3: Image-Based Exam Processing")

    from feedback_agent.agents.image_processing_agent import (
        ImageProcessingAgentRefactored,
    )

    print("🖼️  Looking for sample exam images...")
    image_dir = Path("feedback_agent/input_images")

    if not image_dir.exists():
        print("⚠️  No sample images found. Skipping image processing demo.")
        return

    image_files = list(image_dir.glob("*.png")) + list(image_dir.glob("*.jpg"))

    if not image_files:
        print("⚠️  No image files found. Skipping image processing demo.")
        return

    # Process first image
    sample_image = image_files[1]
    print(f"📸 Processing: {sample_image.name}\n")

    try:
        agent = ImageProcessingAgentRefactored()
        result = await agent.process_image(image_path=str(sample_image))

        print("✅ Image processed successfully!\n")
        print("📋 Extracted Data:")
        print(f"   Subject: {result.get('subject', 'N/A')}")
        print(f"   Exam Content: {result.get('exam_content', 'N/A')[:150]}...")
        print(f"   Answer Key: {result.get('answer_key', 'N/A')[:150]}...")

    except Exception as e:
        print(f"❌ Error processing image: {e}")


async def demo_metrics_tracking():
    """Demo 4: Metrics and observability"""
    print_section("DEMO 4: Metrics & Observability")

    print("📊 Creating system with metrics enabled...")
    system = FeedbackSystem(
        db_path="data/demo.db",
        session_db_url="sqlite:///data/demo_sessions.db",
        enable_metrics=True,
        metrics_file="demo_metrics.jsonl",
    )

    # Register student
    student_id = system.register_student("Charlie Brown")

    # Process multiple exams to generate metrics
    print("\n🔄 Processing 3 sample exams...\n")

    exams = [
        ("Math", "1. 2+2=? A: 4\n2. 3+3=? A: 6", "1. 4\n2. 6"),
        (
            "Science",
            "1. H2O is? A: Water\n2. CO2 is? A: Carbon dioxide",
            "1. Water\n2. Carbon dioxide",
        ),
        (
            "History",
            "1. Who discovered America? A: Columbus\n2. Year? A: 1492",
            "1. Columbus\n2. 1492",
        ),
    ]

    for i, (subject, content, key) in enumerate(exams, 1):
        print(f"   Processing exam {i}/{len(exams)}: {subject}...")
        await system.process_exam(
            student_id=student_id,
            exam_content=content,
            answer_key=key,
            subject=subject,
            user_id="demo_user",
        )

    print("\n✅ All exams processed!\n")

    # Display metrics summary
    print("📈 METRICS SUMMARY:")
    system.print_metrics_summary()

    # Check metrics file
    metrics_file = Path("demo_metrics.jsonl")
    if metrics_file.exists():
        print(f"\n📄 Metrics file created: {metrics_file}")
        with open(metrics_file, "r") as f:
            lines = f.readlines()
            print(f"   Total metrics entries: {len(lines)}")
            if lines:
                sample = json.loads(lines[0])
                print("\n   Sample metric entry:")
                print(f"      Session ID: {sample.get('session_id')}")
                print(f"      Duration: {sample.get('total_duration', 0):.2f}s")
                print(
                    f"      Score: {sample.get('total_score', 0)}/{sample.get('max_score', 0)}"
                )


async def demo_complete_workflow():
    """Demo 5: Complete end-to-end workflow"""
    print_section("DEMO 5: Complete Workflow")

    print("🚀 Running complete workflow demonstration...\n")

    # 1. System initialization
    print("1️⃣  Initialize system")
    system = FeedbackSystem(
        db_path="data/demo_complete.db",
        session_db_url="sqlite:///data/demo_complete_sessions.db",
        enable_metrics=True,
    )
    print("   ✅ System ready\n")

    # 2. Register student
    print("2️⃣  Register student")
    student_name = "Emma Watson"
    student_id = system.register_student(student_name)
    print(f"   ✅ {student_name} registered\n")

    # 3. Process exam
    print("3️⃣  Submit and process exam")
    exam_content = """
    1. What is the capital of France? Answer: Paris
    2. What is 15 - 7? Answer: 9
    3. Who wrote Hamlet? Answer: Shakespeare
    """

    answer_key = """
    1. Paris
    2. 8
    3. Shakespeare
    """

    result = await system.process_exam(
        student_id=student_id,
        exam_content=exam_content,
        answer_key=answer_key,
        subject="General Knowledge",
        user_id="demo_user",
    )
    print("   ✅ Exam processed\n")

    # 4. View results
    print("4️⃣  View results")
    print(
        f"   📊 Score: {result['total_score']}/{result['max_score']} ({result['percentage']:.1f}%)"
    )
    print(f"   📋 Weaknesses: {len(result['weaknesses'])} identified")
    print("   💡 Recommendations: Generated\n")

    # 5. Track metrics
    print("5️⃣  Track performance metrics")
    summary = system.get_metrics_summary()
    if summary:
        print(f"   📈 Processing time: {summary['avg_processing_time']:.2f}s")
        print(f"   ✅ Success rate: {summary['success_rate'] * 100:.0f}%\n")

    print("🎉 Complete workflow demonstration finished!")


async def main():
    """Run all demos"""
    print("""
╔═══════════════════════════════════════════════════════════════════╗
║                                                                   ║
║           AI AGENT CAPSTONE - FEEDBACK SYSTEM DEMO                ║
║                                                                   ║
║  A sophisticated AI agent system for automated exam correction    ║
║  Built with Google Agent Development Kit (ADK)                    ║
║                                                                   ║
╚═══════════════════════════════════════════════════════════════════╝
""")

    demos = [
        ("Basic Exam Processing", demo_basic_exam_processing),
        ("Role-Based Access Control", demo_role_based_access),
        ("Image Processing", demo_image_processing),
        ("Metrics Tracking", demo_metrics_tracking),
        ("Complete Workflow", demo_complete_workflow),
    ]

    print("\n📋 Available Demos:")
    for i, (name, _) in enumerate(demos, 1):
        print(f"   {i}. {name}")
    print(f"   {len(demos) + 1}. Run All Demos")

    print("\n" + "=" * 70)
    choice = input("Select demo to run (1-6): ").strip()

    try:
        choice_num = int(choice)
        if 1 <= choice_num <= len(demos):
            _, demo_func = demos[choice_num - 1]
            await demo_func()
        elif choice_num == len(demos) + 1:
            for i, (name, demo_func) in enumerate(demos, 1):
                if i > 1:
                    input("\n\nPress Enter to continue to next demo...")
                await demo_func()
        else:
            print("Invalid choice!")
    except ValueError:
        print("Invalid input!")
    except KeyboardInterrupt:
        print("\n\n👋 Demo interrupted by user")
    except Exception as e:
        print(f"\n❌ Error running demo: {e}")
        import traceback

        traceback.print_exc()

    print("\n\n" + "=" * 70)
    print("  Demo Complete!")
    print("=" * 70)
    print("\n📚 For more information:")
    print("   - README.md: User documentation")
    print("   - ARCHITECTURE.md: Technical architecture")
    print("   - PROGRESS.md: Development progress")
    print("\n")


if __name__ == "__main__":
    asyncio.run(main())
