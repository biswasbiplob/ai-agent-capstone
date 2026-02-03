"""
Test script for the image processing agent.

This script tests multimodal support by processing exam images and extracting content.
"""

import importlib.util

import pytest

if importlib.util.find_spec("google.adk") is None:
    pytest.skip("google.adk not installed", allow_module_level=True)

import asyncio
import logging
import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
env_path = Path(__file__).resolve().parent.parent / "feedback_agent" / ".env"
load_dotenv(env_path)

# Verify API key
if not os.getenv("GOOGLE_API_KEY"):
    print("⚠️  Warning: GOOGLE_API_KEY not found in environment!")
    print(f"   Tried loading from: {env_path}")
else:
    print(f"✅ API Key loaded successfully")

from feedback_agent.agents.image_processing_agent import ImageProcessingAgent

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


async def test_image_processing():
    """Test the image processing agent."""

    print("\n" + "=" * 80)
    print("🖼️  IMAGE PROCESSING AGENT TESTS")
    print("=" * 80)

    # Initialize agent
    print("\n📝 Step 1: Initializing image processing agent...")
    agent = ImageProcessingAgent()
    print("✅ Agent initialized\n")

    # Find test images
    image_dir = Path("feedback_agent/input_images")
    if not image_dir.exists():
        print(f"❌ Image directory not found: {image_dir}")
        return

    image_files = list(image_dir.glob("*.png")) + list(image_dir.glob("*.jpg"))

    if not image_files:
        print(f"❌ No image files found in {image_dir}")
        return

    print(f"📁 Found {len(image_files)} test images\n")

    # Process each image
    for i, image_path in enumerate(image_files[:3], 1):  # Limit to first 3 images
        print("\n" + "-" * 80)
        print(f"TEST {i}: Processing {image_path.name}")
        print("-" * 80)

        try:
            result = await agent.process_image(image_path=str(image_path))

            print(f"\n✅ Image processed successfully!")
            print(f"\nExtracted Data:")
            print(f"  Subject: {result.get('subject', 'Unknown')}")
            print(
                f"  Exam Content Length: {len(result.get('exam_content', ''))} characters"
            )
            print(f"  Answer Key: {result.get('answer_key', 'Not found')[:50]}...")

            # Show first 200 chars of exam content
            exam_content = result.get("exam_content", "")
            if exam_content:
                print(f"\n  Exam Content Preview:")
                print(f"  {exam_content[:200]}...")
            else:
                print(f"\n  ⚠️  No exam content extracted")

            if "error" in result:
                print(f"\n  ⚠️  Warning: {result['error']}")

        except Exception as e:
            print(f"\n❌ Test failed with error: {e}")
            import traceback

            traceback.print_exc()

    print("\n" + "=" * 80)
    print("✅ IMAGE PROCESSING TESTS COMPLETED!")
    print("=" * 80)


async def test_with_sample_content():
    """
    Test with a generated sample exam for demonstration.

    This creates a simple text-based "image" to demonstrate the concept.
    """
    print("\n" + "=" * 80)
    print("🎨 DEMO: Processing Sample Exam Content")
    print("=" * 80)

    print("\nNote: This would typically process an actual exam photo.")
    print("For demonstration, showing how the agent would process extracted text.\n")

    # Simulate what would be extracted from an image
    sample_result = {
        "subject": "Mathematics",
        "exam_content": """
        Question 1: What is 2 + 2?
        Student Answer: 5

        Question 2: Solve for x: 2x + 5 = 15
        Student Answer: x = 5

        Question 3: What is the capital of France?
        Student Answer: London
        """,
        "answer_key": """
        Q1: 4
        Q2: x = 5 ✓
        Q3: Paris
        """,
    }

    print(f"Subject: {sample_result['subject']}")
    print(f"\nExam Content:")
    print(sample_result["exam_content"])
    print(f"\nAnswer Key:")
    print(sample_result["answer_key"])

    print("\n✅ This extracted content would then flow to the grading pipeline")


if __name__ == "__main__":
    print("\n🚀 Starting Image Processing Tests\n")

    # Test with actual images
    asyncio.run(test_image_processing())

    # Show demo with sample
    asyncio.run(test_with_sample_content())

    print("\n🎉 All tests complete!\n")
