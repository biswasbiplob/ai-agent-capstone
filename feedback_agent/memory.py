"""
Memory Service for Cross-Session Student Tracking

This module provides memory capabilities for tracking student performance
across multiple exam sessions, identifying learning patterns, and making
intelligent recommendations based on historical data.
"""

import json
from typing import Any, List, Dict, Optional, Tuple
from datetime import datetime, timedelta
from collections import Counter, defaultdict
from dataclasses import dataclass

from feedback_agent.database import StudentDatabase


@dataclass
class WeaknessPattern:
    """Represents a recurring weakness pattern."""
    topic: str
    occurrences: int
    severity_trend: str  # "improving", "stable", "worsening"
    last_seen: str
    first_seen: str


@dataclass
class LearningVelocity:
    """Represents learning progress metrics."""
    student_id: str
    total_exams: int
    average_score: float
    score_trend: str  # "improving", "stable", "declining"
    improvement_rate: float  # Percentage change per exam
    subjects_mastered: List[str]
    subjects_struggling: List[str]


class MemoryService:
    """
    Memory service for tracking student learning patterns across sessions.

    This service analyzes historical exam data to:
    - Identify recurring weaknesses
    - Measure learning velocity and improvement rates
    - Generate personalized review recommendations
    - Track mastery of topics over time
    """

    def __init__(self, db: StudentDatabase):
        self.db = db

    def get_recurring_weaknesses(
        self,
        student_id: str,
        min_occurrences: int = 2,
        lookback_days: Optional[int] = None
    ) -> List[WeaknessPattern]:
        """
        Identify topics that appear repeatedly in student's weaknesses.

        Args:
            student_id: The student's unique identifier
            min_occurrences: Minimum times a weakness must appear to be considered recurring
            lookback_days: Only consider exams within this many days (None = all exams)

        Returns:
            List of WeaknessPattern objects sorted by occurrence count
        """
        history = self.db.get_student_history(student_id)

        if not history:
            return []

        # Filter by date if lookback_days specified
        if lookback_days:
            cutoff_date = datetime.now() - timedelta(days=lookback_days)
            filtered_history = []
            for exam in history:
                exam_date = exam.get("date")
                if not exam_date:
                    continue
                try:
                    exam_dt = datetime.fromisoformat(exam_date)
                except ValueError:
                    continue
                if exam_dt >= cutoff_date:
                    filtered_history.append(exam)
            history = filtered_history

        # Track weakness occurrences and metadata
        weakness_tracker: Dict[str, List[Dict[str, Any]]] = defaultdict(list)

        for idx, exam in enumerate(history):
            weaknesses = exam.get('weaknesses', [])
            exam_date = exam.get("date")
            exam_id = exam.get("exam_id")

            for weakness in weaknesses:
                # Extract topic from weakness dict or string
                if isinstance(weakness, dict):
                    topic = weakness.get('topic', '')
                    severity = weakness.get('severity', 'medium')
                elif isinstance(weakness, str):
                    topic = weakness
                    severity = 'medium'
                else:
                    continue

                if topic:
                    weakness_tracker[topic].append({
                        "index": idx,
                        "severity": severity,
                        "date": exam_date,
                        "exam_id": exam_id,
                    })

        # Build WeaknessPattern objects for recurring weaknesses
        patterns = []

        for topic, occurrences in weakness_tracker.items():
            if len(occurrences) >= min_occurrences:
                # Analyze severity trend
                severities = [o["severity"] for o in occurrences]
                severity_trend = self._analyze_severity_trend(severities)

                # Get first and last occurrence indices
                first_occurrence = min(occurrences, key=lambda o: o["index"])
                last_occurrence = max(occurrences, key=lambda o: o["index"])

                def _label(occ: Dict[str, Optional[str]]) -> str:
                    if occ.get("date"):
                        return occ["date"]
                    if occ.get("exam_id"):
                        return occ["exam_id"]
                    return f"exam_{occ['index']}"

                pattern = WeaknessPattern(
                    topic=topic,
                    occurrences=len(occurrences),
                    severity_trend=severity_trend,
                    last_seen=_label(last_occurrence),
                    first_seen=_label(first_occurrence),
                )
                patterns.append(pattern)

        # Sort by occurrence count (descending)
        patterns.sort(key=lambda p: p.occurrences, reverse=True)

        return patterns

    def get_learning_velocity(self, student_id: str) -> Optional[LearningVelocity]:
        """
        Calculate student's learning velocity and improvement metrics.

        Args:
            student_id: The student's unique identifier

        Returns:
            LearningVelocity object with progress metrics, or None if insufficient data
        """
        history = self.db.get_student_history(student_id)

        if len(history) < 2:
            return None  # Need at least 2 exams to calculate velocity

        # Calculate score percentages
        scores = []
        for exam in history:
            if exam['max_score'] > 0:
                percentage = (exam['score'] / exam['max_score']) * 100
                scores.append(percentage)

        if not scores:
            return None

        # Calculate average score
        avg_score = sum(scores) / len(scores)

        # Determine score trend
        if len(scores) >= 3:
            recent_avg = sum(scores[-3:]) / len(scores[-3:])
            earlier_avg = sum(scores[:-3]) / len(scores[:-3]) if len(scores) > 3 else scores[0]

            if recent_avg > earlier_avg + 5:
                score_trend = "improving"
            elif recent_avg < earlier_avg - 5:
                score_trend = "declining"
            else:
                score_trend = "stable"
        else:
            if scores[-1] > scores[0] + 5:
                score_trend = "improving"
            elif scores[-1] < scores[0] - 5:
                score_trend = "declining"
            else:
                score_trend = "stable"

        # Calculate improvement rate (percentage change per exam)
        if len(scores) >= 2:
            total_change = scores[-1] - scores[0]
            improvement_rate = total_change / (len(scores) - 1)
        else:
            improvement_rate = 0.0

        # Identify subjects mastered vs struggling
        subject_scores: Dict[str, List[float]] = defaultdict(list)
        for exam in history:
            subject = exam['subject']
            if exam['max_score'] > 0:
                percentage = (exam['score'] / exam['max_score']) * 100
                subject_scores[subject].append(percentage)

        subjects_mastered = []
        subjects_struggling = []

        for subject, subj_scores in subject_scores.items():
            avg_subj_score = sum(subj_scores) / len(subj_scores)
            if avg_subj_score >= 85:
                subjects_mastered.append(subject)
            elif avg_subj_score < 70:
                subjects_struggling.append(subject)

        return LearningVelocity(
            student_id=student_id,
            total_exams=len(history),
            average_score=avg_score,
            score_trend=score_trend,
            improvement_rate=improvement_rate,
            subjects_mastered=subjects_mastered,
            subjects_struggling=subjects_struggling
        )

    def recommend_review_topics(
        self,
        student_id: str,
        max_topics: int = 5
    ) -> List[Dict[str, str]]:
        """
        Generate personalized review recommendations based on historical performance.

        Args:
            student_id: The student's unique identifier
            max_topics: Maximum number of topics to recommend

        Returns:
            List of recommended topics with rationale
        """
        recommendations = []

        # Get recurring weaknesses
        recurring = self.get_recurring_weaknesses(student_id, min_occurrences=2)

        # Get learning velocity
        velocity = self.get_learning_velocity(student_id)

        # Priority 1: Recurring weaknesses that are worsening
        worsening = [p for p in recurring if p.severity_trend == "worsening"]
        for pattern in worsening[:max_topics]:
            recommendations.append({
                "topic": pattern.topic,
                "priority": "high",
                "rationale": f"Appears {pattern.occurrences} times and severity is worsening. "
                           f"First seen in {pattern.first_seen}, last seen in {pattern.last_seen}."
            })

        # Priority 2: Recurring weaknesses that are stable
        stable = [p for p in recurring if p.severity_trend == "stable"]
        remaining = max_topics - len(recommendations)
        for pattern in stable[:remaining]:
            recommendations.append({
                "topic": pattern.topic,
                "priority": "medium",
                "rationale": f"Appears {pattern.occurrences} times with stable severity. "
                           f"Needs consistent practice to overcome."
            })

        # Priority 3: Struggling subjects (if velocity data available)
        if velocity and len(recommendations) < max_topics:
            remaining = max_topics - len(recommendations)
            for subject in velocity.subjects_struggling[:remaining]:
                recommendations.append({
                    "topic": f"{subject} fundamentals",
                    "priority": "medium",
                    "rationale": f"Average score in {subject} is below 70%. "
                               f"Consider reviewing core concepts."
                })

        # Priority 4: Recent weaknesses (even if not recurring)
        if len(recommendations) < max_topics:
            history = self.db.get_student_history(student_id)
            if history:
                recent_exam = history[-1]  # Most recent exam
                recent_weaknesses = recent_exam.get('weaknesses', [])

                # Filter out already recommended topics
                recommended_topics = {rec['topic'] for rec in recommendations}

                remaining = max_topics - len(recommendations)
                for weakness in recent_weaknesses[:remaining]:
                    if isinstance(weakness, dict):
                        topic = weakness.get('topic', '')
                    elif isinstance(weakness, str):
                        topic = weakness
                    else:
                        continue

                    if topic and topic not in recommended_topics:
                        recommendations.append({
                            "topic": topic,
                            "priority": "low",
                            "rationale": "Identified in most recent exam. Review while still fresh."
                        })

        return recommendations[:max_topics]

    def get_mastery_progress(self, student_id: str) -> Dict[str, Dict[str, float]]:
        """
        Track mastery level for each topic based on historical performance.

        Args:
            student_id: The student's unique identifier

        Returns:
            Dictionary mapping subjects to mastery metrics
        """
        history = self.db.get_student_history(student_id)

        if not history:
            return {}

        # Track subject performance over time
        subject_data: Dict[str, List[float]] = defaultdict(list)

        for exam in history:
            subject = exam['subject']
            if exam['max_score'] > 0:
                percentage = (exam['score'] / exam['max_score']) * 100
                subject_data[subject].append(percentage)

        # Calculate mastery metrics for each subject
        mastery_progress = {}

        for subject, scores in subject_data.items():
            if not scores:
                continue

            # Current mastery (most recent score)
            current_mastery = scores[-1]

            # Trend (comparing recent vs earlier)
            if len(scores) >= 2:
                recent_avg = sum(scores[-2:]) / 2
                earlier_avg = sum(scores[:-2]) / len(scores[:-2]) if len(scores) > 2 else scores[0]
                trend = recent_avg - earlier_avg
            else:
                trend = 0.0

            # Consistency (standard deviation)
            if len(scores) > 1:
                mean = sum(scores) / len(scores)
                variance = sum((s - mean) ** 2 for s in scores) / len(scores)
                consistency = 100 - (variance ** 0.5)  # Higher is more consistent
            else:
                consistency = 100.0

            mastery_progress[subject] = {
                "current_mastery": current_mastery,
                "average_score": sum(scores) / len(scores),
                "trend": trend,
                "consistency": consistency,
                "total_attempts": len(scores)
            }

        return mastery_progress

    @staticmethod
    def _analyze_severity_trend(severities: List[str]) -> str:
        """
        Analyze whether severity is improving, worsening, or stable.

        Args:
            severities: List of severity strings in chronological order

        Returns:
            Trend classification: "improving", "stable", or "worsening"
        """
        if len(severities) < 2:
            return "stable"

        # Map severity to numeric values
        severity_map = {"low": 1, "medium": 2, "high": 3}

        numeric_severities = [severity_map.get(s.lower(), 2) for s in severities]

        # Compare recent vs earlier
        if len(numeric_severities) >= 3:
            recent = sum(numeric_severities[-2:]) / 2
            earlier = sum(numeric_severities[:-2]) / len(numeric_severities[:-2])
        else:
            recent = numeric_severities[-1]
            earlier = numeric_severities[0]

        if recent < earlier - 0.3:
            return "improving"
        elif recent > earlier + 0.3:
            return "worsening"
        else:
            return "stable"
