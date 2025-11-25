"""
Comprehensive evaluation runner for the feedback agent system.

This script:
1. Loads the evaluation dataset
2. Processes each test case through the agent
3. Calculates metrics
4. Generates a detailed evaluation report
"""

import asyncio
import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from dotenv import load_dotenv

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Load environment variables
env_path = Path(__file__).parent.parent / "feedback_agent" / ".env"
load_dotenv(env_path)

from evals.metrics import (
    AnalysisQualityMetric,
    GradingAccuracyMetric,
    RecommendationRelevanceMetric,
    calculate_overall_score,
)
from feedback_agent.agent import FeedbackSystem

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


# Suppress verbose ADK logs during evaluation
logging.getLogger("google_adk").setLevel(logging.WARNING)
logging.getLogger("google_genai").setLevel(logging.WARNING)
logging.getLogger("feedback_agent").setLevel(logging.WARNING)


# ============================================================================
# Model Rate Limit Configuration
# ============================================================================
# Maps model names to minimum wait time between API calls (in seconds)
# Formula: (60 / requests_per_minute) * 1.1 buffer
# 10% buffer accounts for network latency and multiple agent calls per test
# ============================================================================

MODEL_RATE_LIMITS = {
    # 15 RPM models: (60/15) * 1.1 = 4.4 → 5 seconds
    "gemini-1.5-flash": 5,
    "gemini-2.0-flash": 5,
    "gemini-2.0-flash-exp": 5,
    # 10 RPM models: (60/10) * 1.1 = 6.6 → 7 seconds
    "gemini-2.5-flash": 7,
    # 2 RPM models: (60/2) * 1.1 = 33 seconds
    "gemini-1.5-pro": 33,
    "gemini-2.5-pro": 33,
}


class EvaluationRunner:
    """Runs comprehensive evaluations on the feedback agent system."""

    def __init__(self, dataset_path: str, db_path: str = "eval_students.db"):
        """
        Initialize evaluation runner.

        Args:
            dataset_path: Path to evaluation dataset JSON file
            db_path: Path to database for evaluation (will be cleaned between runs)
        """
        self.dataset_path = dataset_path
        self.db_path = db_path
        self.results = []
        self.summary = {}

        # Initialize agent system
        logger.info("Initializing feedback agent system...")
        self.feedback_system = FeedbackSystem(
            db_path=self.db_path,
            use_memory_sessions=True,  # Use in-memory sessions for evaluation
        )
        logger.info("Agent system initialized successfully")

    def _get_rate_limit_wait_time(self) -> int:
        """
        Get the appropriate wait time based on MODEL_NAME environment variable.
        Raises ValueError if MODEL_NAME is not set or unknown.
        """
        model_name = os.getenv("MODEL_NAME")

        if not model_name:
            raise ValueError(
                "MODEL_NAME environment variable not set. "
                "Set MODEL_NAME in feedback_agent/.env to run evaluations. "
                f"Supported models: {', '.join(sorted(MODEL_RATE_LIMITS.keys()))}"
            )

        if model_name not in MODEL_RATE_LIMITS:
            raise ValueError(
                f"Unknown model '{model_name}'. "
                f"Supported models: {', '.join(sorted(MODEL_RATE_LIMITS.keys()))}. "
                "Update MODEL_NAME in feedback_agent/.env with a supported model."
            )

        return MODEL_RATE_LIMITS[model_name]

    def load_dataset(self) -> Dict[str, Any]:
        """Load evaluation dataset from JSON file."""
        logger.info(f"Loading evaluation dataset from {self.dataset_path}")
        with open(self.dataset_path, "r") as f:
            dataset = json.load(f)
        logger.info(f"Loaded {len(dataset['test_cases'])} test cases")
        return dataset

    async def run_single_test(self, test_case: Dict[str, Any]) -> Dict[str, Any]:
        """
        Run a single test case through the agent system.

        Args:
            test_case: Test case dictionary

        Returns:
            Result dictionary with predictions and metrics
        """
        test_id = test_case["id"]
        logger.info(f"\n{'=' * 80}")
        logger.info(
            f"Running test: {test_id} ({test_case['category']} - {test_case['difficulty']})"
        )
        logger.info(f"{'=' * 80}")

        try:
            # Extract test case data
            student_name = test_case["student_name"]
            subject = test_case["subject"]
            exam_content = test_case["exam_content"]
            answer_key = test_case["answer_key"]
            ground_truth = test_case["ground_truth"]

            # Register student (generate unique ID)
            student_id = f"eval_{test_id}_{student_name.replace(' ', '_')}"
            self.feedback_system.db.add_student(student_id, student_name)
            logger.info(f"Processing exam for {student_name} ({subject})")

            # Process exam through agent
            result = await self.feedback_system.process_exam(
                student_id=student_id,
                exam_content=exam_content,
                answer_key=answer_key,
                subject=subject,
                user_id="evaluator",
            )

            logger.info(f"Agent processing complete for {test_id}")

            # Extract predictions
            predicted_grading = {
                "total_score": result.get("total_score", 0),
                "max_score": result.get("max_score", 0),
                "percentage": result.get("percentage", 0.0),
            }

            predicted_analysis = {"weaknesses": result.get("weaknesses", [])}

            predicted_recommendations = {
                "recommendations": result.get("recommendations", "")
            }

            # Calculate metrics
            logger.info("Calculating metrics...")

            grading_metrics = GradingAccuracyMetric.evaluate(
                predicted=predicted_grading, ground_truth=ground_truth
            )

            analysis_metrics = AnalysisQualityMetric.evaluate(
                predicted=predicted_analysis, ground_truth=ground_truth
            )

            recommendation_metrics = RecommendationRelevanceMetric.evaluate(
                predicted=predicted_recommendations,
                analysis=predicted_analysis,
                ground_truth=ground_truth,
            )

            overall_scores = calculate_overall_score(
                grading_metrics=grading_metrics,
                analysis_metrics=analysis_metrics,
                recommendation_metrics=recommendation_metrics,
            )

            # Determine pass/fail
            # Pass if overall score >= 0.70 (70%)
            status = "passed" if overall_scores["overall_score"] >= 0.70 else "failed"

            logger.info(
                f"Test {test_id}: {status.upper()} (overall score: {overall_scores['overall_score']:.2f})"
            )

            return {
                "test_id": test_id,
                "category": test_case["category"],
                "difficulty": test_case["difficulty"],
                "subject": test_case["subject"],
                "student_name": student_name,
                "status": status,
                "predicted": {
                    "grading": predicted_grading,
                    "analysis": predicted_analysis,
                    "recommendations": predicted_recommendations,
                },
                "ground_truth": ground_truth,
                "metrics": {
                    "grading": grading_metrics,
                    "analysis": analysis_metrics,
                    "recommendations": recommendation_metrics,
                    "overall": overall_scores,
                },
            }

        except Exception as e:
            logger.error(f"Test {test_id}: Error - {e}", exc_info=True)
            return {
                "test_id": test_id,
                "category": test_case.get("category", "unknown"),
                "difficulty": test_case.get("difficulty", "unknown"),
                "subject": test_case.get("subject", "unknown"),
                "status": "error",
                "error": str(e),
            }

    async def run_all_tests(self) -> List[Dict[str, Any]]:
        """
        Run all tests in the dataset.

        Returns:
            List of results for all test cases
        """
        dataset = self.load_dataset()
        test_cases = dataset["test_cases"]

        logger.info(f"\nStarting evaluation run with {len(test_cases)} test cases")
        logger.info(f"Timestamp: {datetime.now().isoformat()}")

        wait_time = self._get_rate_limit_wait_time()
        estimated_time_per_test = wait_time + 5  # wait + processing time
        total_estimated_time = len(test_cases) * estimated_time_per_test
        total_minutes = total_estimated_time // 60
        total_seconds = total_estimated_time % 60
        model_name = os.getenv("MODEL_NAME", "unknown")

        logger.info(
            f"Note: This will take approximately {total_estimated_time} seconds "
            f"({total_minutes}m {total_seconds}s) for {len(test_cases)} test cases\n"
            f"Model: {model_name} | Rate limit wait: {wait_time}s between tests\n"
        )

        results = []
        for i, test_case in enumerate(test_cases, 1):
            logger.info(f"\n{'=' * 80}")
            logger.info(f"Progress: {i}/{len(test_cases)}")
            logger.info(f"{'=' * 80}")

            result = await self.run_single_test(test_case)
            results.append(result)

            # Pause between tests to respect API rate limits
            # Wait time is dynamically determined based on MODEL_NAME
            if i < len(test_cases):
                wait_time = self._get_rate_limit_wait_time()
                model_name = os.getenv("MODEL_NAME", "unknown")
                logger.info(
                    f"Waiting {wait_time} seconds before next test "
                    f"(rate limit compliance for {model_name})..."
                )
                await asyncio.sleep(wait_time)

        self.results = results
        return results

    def generate_summary(self) -> Dict[str, Any]:
        """
        Generate summary statistics from evaluation results.

        Returns:
            Summary dictionary
        """
        if not self.results:
            return {}

        total = len(self.results)
        passed = sum(1 for r in self.results if r.get("status") == "passed")
        failed = sum(1 for r in self.results if r.get("status") == "failed")
        errors = sum(1 for r in self.results if r.get("status") == "error")

        # Calculate average scores across all successful tests
        successful_tests = [
            r for r in self.results if r.get("status") in ["passed", "failed"]
        ]

        if successful_tests:
            avg_grading_score = sum(
                r["metrics"]["overall"]["grading_score"]
                for r in successful_tests
                if "metrics" in r
            ) / len(successful_tests)

            avg_analysis_score = sum(
                r["metrics"]["overall"]["analysis_score"]
                for r in successful_tests
                if "metrics" in r
            ) / len(successful_tests)

            avg_recommendation_score = sum(
                r["metrics"]["overall"]["recommendation_score"]
                for r in successful_tests
                if "metrics" in r
            ) / len(successful_tests)

            avg_overall_score = sum(
                r["metrics"]["overall"]["overall_score"]
                for r in successful_tests
                if "metrics" in r
            ) / len(successful_tests)
        else:
            avg_grading_score = 0
            avg_analysis_score = 0
            avg_recommendation_score = 0
            avg_overall_score = 0

        # Group by category
        by_category = {}
        for result in self.results:
            category = result.get("category", "unknown")
            if category not in by_category:
                by_category[category] = {
                    "total": 0,
                    "passed": 0,
                    "failed": 0,
                    "avg_score": 0.0,
                }
            by_category[category]["total"] += 1
            if result.get("status") == "passed":
                by_category[category]["passed"] += 1
            elif result.get("status") == "failed":
                by_category[category]["failed"] += 1

        # Calculate average score per category
        for category in by_category:
            category_results = [
                r
                for r in self.results
                if r.get("category") == category and "metrics" in r
            ]
            if category_results:
                by_category[category]["avg_score"] = sum(
                    r["metrics"]["overall"]["overall_score"] for r in category_results
                ) / len(category_results)

        # Group by difficulty
        by_difficulty = {}
        for result in self.results:
            difficulty = result.get("difficulty", "unknown")
            if difficulty not in by_difficulty:
                by_difficulty[difficulty] = {
                    "total": 0,
                    "passed": 0,
                    "failed": 0,
                    "avg_score": 0.0,
                }
            by_difficulty[difficulty]["total"] += 1
            if result.get("status") == "passed":
                by_difficulty[difficulty]["passed"] += 1
            elif result.get("status") == "failed":
                by_difficulty[difficulty]["failed"] += 1

        # Calculate average score per difficulty
        for difficulty in by_difficulty:
            difficulty_results = [
                r
                for r in self.results
                if r.get("difficulty") == difficulty and "metrics" in r
            ]
            if difficulty_results:
                by_difficulty[difficulty]["avg_score"] = sum(
                    r["metrics"]["overall"]["overall_score"] for r in difficulty_results
                ) / len(difficulty_results)

        summary = {
            "timestamp": datetime.now().isoformat(),
            "total_tests": total,
            "passed": passed,
            "failed": failed,
            "errors": errors,
            "pass_rate": (passed / total * 100) if total > 0 else 0,
            "average_scores": {
                "grading": avg_grading_score,
                "analysis": avg_analysis_score,
                "recommendations": avg_recommendation_score,
                "overall": avg_overall_score,
            },
            "by_category": by_category,
            "by_difficulty": by_difficulty,
        }

        self.summary = summary
        return summary

    def save_results(self, output_path: str):
        """
        Save evaluation results to JSON file.

        Args:
            output_path: Path to save results
        """
        output = {"summary": self.summary, "results": self.results}

        with open(output_path, "w") as f:
            json.dump(output, f, indent=2)

        logger.info(f"\n{'=' * 80}")
        logger.info(f"Results saved to: {output_path}")
        logger.info(f"{'=' * 80}")

    def print_summary(self):
        """Print summary to console."""
        if not self.summary:
            logger.warning("No summary available. Run evaluations first.")
            return

        print("\n" + "=" * 80)
        print("EVALUATION SUMMARY")
        print("=" * 80)
        print(f"\nTimestamp: {self.summary['timestamp']}")
        print("\nOverall Results:")
        print(f"  Total Tests: {self.summary['total_tests']}")
        print(f"  Passed: {self.summary['passed']}")
        print(f"  Failed: {self.summary['failed']}")
        print(f"  Errors: {self.summary['errors']}")
        print(f"  Pass Rate: {self.summary['pass_rate']:.2f}%")

        print("\nAverage Scores (0-1 scale):")
        avg_scores = self.summary.get("average_scores", {})
        print(f"  Grading Accuracy: {avg_scores.get('grading', 0):.3f}")
        print(f"  Analysis Quality: {avg_scores.get('analysis', 0):.3f}")
        print(f"  Recommendation Relevance: {avg_scores.get('recommendations', 0):.3f}")
        print(f"  Overall Score: {avg_scores.get('overall', 0):.3f}")

        print("\nBy Category:")
        for category, stats in self.summary["by_category"].items():
            pass_rate = (
                (stats["passed"] / stats["total"] * 100) if stats["total"] > 0 else 0
            )
            avg_score = stats.get("avg_score", 0)
            print(f"  {category}:")
            print(
                f"    Tests: {stats['total']}, Passed: {stats['passed']}, Failed: {stats['failed']} ({pass_rate:.1f}%)"
            )
            print(f"    Avg Score: {avg_score:.3f}")

        print("\nBy Difficulty:")
        for difficulty, stats in self.summary["by_difficulty"].items():
            pass_rate = (
                (stats["passed"] / stats["total"] * 100) if stats["total"] > 0 else 0
            )
            avg_score = stats.get("avg_score", 0)
            print(f"  {difficulty}:")
            print(
                f"    Tests: {stats['total']}, Passed: {stats['passed']}, Failed: {stats['failed']} ({pass_rate:.1f}%)"
            )
            print(f"    Avg Score: {avg_score:.3f}")

        print("\n" + "=" * 80)


async def main():
    """Main evaluation entry point."""
    logger.info("🚀 Starting Feedback Agent Evaluation Framework")
    logger.info("=" * 80)

    # Paths
    dataset_path = Path(__file__).parent / "evalset.json"
    output_path = (
        Path(__file__).parent
        / f"eval_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    )

    # Create runner
    runner = EvaluationRunner(str(dataset_path))

    # Run evaluations
    await runner.run_all_tests()

    # Generate and print summary
    runner.generate_summary()
    runner.print_summary()

    # Save results
    runner.save_results(str(output_path))

    logger.info("\n✅ Evaluation complete!")
    logger.info("\nNote: Agent integration is pending (Phase 5.2)")
    logger.info("Current run validates evaluation framework structure.")


if __name__ == "__main__":
    asyncio.run(main())
