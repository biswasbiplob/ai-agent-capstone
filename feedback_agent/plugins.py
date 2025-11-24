"""
Custom plugins for observability and metrics tracking in the feedback system.

This module provides custom plugins that integrate with Google ADK's Runner
to track exam processing metrics, performance data, and system health.
"""

import time
import json
import logging
from typing import Any, Dict, Optional
from datetime import datetime
from collections import defaultdict

from google.adk.plugins import BasePlugin

logger = logging.getLogger(__name__)


class ExamMetricsPlugin(BasePlugin):
    """
    Custom plugin to track exam processing metrics and performance.

    Metrics tracked:
    - Exam processing duration (total and per-agent)
    - Grading scores and distributions
    - Number of weaknesses identified
    - Success/failure rates
    - Agent execution times

    Usage:
        plugin = ExamMetricsPlugin()
        app = App(..., plugins=[plugin])
    """

    def __init__(self, log_to_file: bool = True, metrics_file: str = "exam_metrics.jsonl"):
        """
        Initialize the ExamMetricsPlugin.

        Args:
            log_to_file: Whether to log metrics to a JSONL file
            metrics_file: Path to metrics file
        """
        super().__init__(name="exam_metrics_plugin")
        self.log_to_file = log_to_file
        self.metrics_file = metrics_file

        # In-memory metrics storage
        self.session_metrics: Dict[str, Dict[str, Any]] = {}
        self.agent_timings: Dict[str, Dict[str, float]] = defaultdict(dict)

        # Aggregated statistics
        self.total_exams_processed = 0
        self.total_processing_time = 0.0
        self.score_distribution = []
        self.success_count = 0
        self.failure_count = 0

        logger.info(f"✅ ExamMetricsPlugin initialized (logging to {metrics_file})")

    async def before_run_callback(self, **kwargs) -> None:
        """Called when exam processing starts."""
        # Get invocation_context which contains session
        invocation_context = kwargs.get('invocation_context')
        if not invocation_context or not invocation_context.session:
            return

        session_id = invocation_context.session.id
        state = invocation_context.session.state or {}

        if session_id and session_id not in self.session_metrics:
            self.session_metrics[session_id] = {
                "session_id": session_id,
                "start_time": time.time(),
                "start_timestamp": datetime.now().isoformat(),
                "agent_timings": {},
                "exam_id": state.get("exam_id"),
                "student_id": state.get("student_id"),
                "subject": state.get("subject"),
                "status": "in_progress"
            }
            logger.debug(f"📊 Started tracking metrics for session {session_id}")

    async def before_agent_callback(self, **kwargs) -> None:
        """Called when an agent starts execution."""
        invocation_context = kwargs.get('invocation_context')
        agent_context = kwargs.get('agent_context')

        if not invocation_context or not agent_context or not invocation_context.session:
            return

        session_id = invocation_context.session.id
        agent_name = agent_context.agent.name

        if session_id:
            if session_id not in self.agent_timings:
                self.agent_timings[session_id] = {}
            self.agent_timings[session_id][f"{agent_name}_start"] = time.time()
            logger.debug(f"▶️ Agent '{agent_name}' started for session {session_id}")

    async def after_agent_callback(self, **kwargs) -> None:
        """Called when an agent completes execution."""
        invocation_context = kwargs.get('invocation_context')
        agent_context = kwargs.get('agent_context')

        if not invocation_context or not agent_context or not invocation_context.session:
            return

        session_id = invocation_context.session.id
        agent_name = agent_context.agent.name

        if session_id and session_id in self.agent_timings:
            start_key = f"{agent_name}_start"
            if start_key in self.agent_timings[session_id]:
                start_time = self.agent_timings[session_id][start_key]
                duration = time.time() - start_time

                # Store in session metrics
                if session_id in self.session_metrics:
                    self.session_metrics[session_id]["agent_timings"][agent_name] = duration

                logger.debug(f"⏱️ Agent '{agent_name}' completed in {duration:.2f}s")

    async def after_run_callback(self, **kwargs) -> None:
        """Called when exam processing completes."""
        invocation_context = kwargs.get('invocation_context')
        if not invocation_context or not invocation_context.session:
            return

        session_id = invocation_context.session.id
        state = invocation_context.session.state or {}

        if not session_id or session_id not in self.session_metrics:
            return

        metrics = self.session_metrics[session_id]

        # Calculate total duration
        start_time = metrics.get("start_time")
        if start_time:
            total_duration = time.time() - start_time
            metrics["total_duration"] = total_duration
            metrics["end_timestamp"] = datetime.now().isoformat()
            self.total_processing_time += total_duration

        # Extract results from state if available
        if state:
            # Extract grading results
            grading_result_str = state.get("grading_result")
            if grading_result_str:
                try:
                    grading_result = json.loads(grading_result_str)
                    metrics["total_score"] = grading_result.get("total_score", 0)
                    metrics["max_score"] = grading_result.get("max_score", 0)
                    metrics["percentage"] = (
                        (metrics["total_score"] / metrics["max_score"] * 100)
                        if metrics["max_score"] > 0 else 0
                    )
                    self.score_distribution.append(metrics["percentage"])
                except json.JSONDecodeError:
                    logger.warning(f"Failed to parse grading result for {session_id}")

            # Extract analysis results
            analysis_result_str = state.get("weakness_analysis")
            if analysis_result_str:
                try:
                    analysis_result = json.loads(analysis_result_str)
                    weaknesses = analysis_result.get("weaknesses", [])
                    metrics["weaknesses_count"] = len(weaknesses)
                    metrics["weakness_severities"] = {
                        "low": sum(1 for w in weaknesses if w.get("severity") == "low"),
                        "medium": sum(1 for w in weaknesses if w.get("severity") == "medium"),
                        "high": sum(1 for w in weaknesses if w.get("severity") == "high")
                    }
                except json.JSONDecodeError:
                    logger.warning(f"Failed to parse analysis result for {session_id}")

        # Mark as successful
        metrics["status"] = "completed"
        self.total_exams_processed += 1
        self.success_count += 1

        # Log metrics
        logger.info(
            f"📊 Exam {metrics.get('exam_id', 'unknown')} processed in {metrics.get('total_duration', 0):.2f}s"
        )

        # Write to file if enabled
        if self.log_to_file:
            self._write_metrics_to_file(metrics)

    def _write_metrics_to_file(self, metrics: Dict[str, Any]) -> None:
        """
        Write metrics to JSONL file.

        Args:
            metrics: Metrics dictionary to write
        """
        try:
            with open(self.metrics_file, 'a') as f:
                f.write(json.dumps(metrics) + '\n')
            logger.debug(f"✍️ Metrics written to {self.metrics_file}")
        except Exception as e:
            logger.error(f"Failed to write metrics to file: {e}")

    def get_summary_statistics(self) -> Dict[str, Any]:
        """
        Get aggregated summary statistics across all processed exams.

        Returns:
            Dictionary with summary statistics
        """
        avg_processing_time = (
            self.total_processing_time / self.total_exams_processed
            if self.total_exams_processed > 0 else 0
        )

        avg_score = (
            sum(self.score_distribution) / len(self.score_distribution)
            if self.score_distribution else 0
        )

        success_rate = (
            self.success_count / (self.success_count + self.failure_count)
            if (self.success_count + self.failure_count) > 0 else 0
        )

        return {
            "total_exams_processed": self.total_exams_processed,
            "total_processing_time": self.total_processing_time,
            "avg_processing_time": avg_processing_time,
            "avg_score_percentage": avg_score,
            "success_count": self.success_count,
            "failure_count": self.failure_count,
            "success_rate": success_rate,
            "score_distribution": {
                "min": min(self.score_distribution) if self.score_distribution else 0,
                "max": max(self.score_distribution) if self.score_distribution else 0,
                "avg": avg_score
            }
        }

    def print_summary(self) -> None:
        """Print human-readable summary statistics."""
        stats = self.get_summary_statistics()

        print("\n" + "="*60)
        print("📊 EXAM PROCESSING METRICS SUMMARY")
        print("="*60)
        print(f"Total Exams Processed: {stats['total_exams_processed']}")
        print(f"Success Rate: {stats['success_rate']*100:.1f}%")
        print(f"Total Processing Time: {stats['total_processing_time']:.2f}s")
        print(f"Average Processing Time: {stats['avg_processing_time']:.2f}s")
        print(f"\nScore Statistics:")
        print(f"  Average Score: {stats['avg_score_percentage']:.1f}%")
        print(f"  Min Score: {stats['score_distribution']['min']:.1f}%")
        print(f"  Max Score: {stats['score_distribution']['max']:.1f}%")
        print("="*60 + "\n")
