"""
Evaluation metrics for the feedback agent system.

This module defines metrics to evaluate:
1. Grading Accuracy - How well the agent scores exams
2. Analysis Quality - How well the agent identifies weaknesses
3. Recommendation Relevance - How well recommendations align with identified weaknesses
"""

from typing import Dict, List, Any, Tuple
import logging

logger = logging.getLogger(__name__)


class GradingAccuracyMetric:
    """
    Measures how accurately the agent grades exams compared to ground truth.

    Metrics:
    - Score Accuracy: Exact match of total_score
    - Score Tolerance: Score within ±10% of expected
    - Percentage Accuracy: Within ±5% of expected percentage
    """

    @staticmethod
    def evaluate(predicted: Dict[str, Any], ground_truth: Dict[str, Any]) -> Dict[str, Any]:
        """
        Evaluate grading accuracy.

        Args:
            predicted: Agent's grading result with total_score, max_score, percentage
            ground_truth: Expected grading result

        Returns:
            Dictionary with accuracy metrics
        """
        pred_score = predicted.get('total_score', 0)
        expected_score = ground_truth.get('total_score', 0)
        max_score = ground_truth.get('max_score', 1)

        pred_percentage = predicted.get('percentage', (pred_score / max_score * 100) if max_score > 0 else 0)
        expected_percentage = ground_truth.get('percentage', 0)

        # Exact match
        exact_match = pred_score == expected_score

        # Within tolerance (10% of max score)
        tolerance = max_score * 0.1
        within_tolerance = abs(pred_score - expected_score) <= tolerance

        # Percentage accuracy (within 5%)
        percentage_accurate = abs(pred_percentage - expected_percentage) <= 5.0

        # Score difference
        score_diff = pred_score - expected_score
        percentage_diff = pred_percentage - expected_percentage

        return {
            'exact_match': exact_match,
            'within_tolerance': within_tolerance,
            'percentage_accurate': percentage_accurate,
            'score_difference': score_diff,
            'percentage_difference': percentage_diff,
            'predicted_score': pred_score,
            'expected_score': expected_score,
            'predicted_percentage': pred_percentage,
            'expected_percentage': expected_percentage
        }


class AnalysisQualityMetric:
    """
    Measures how well the agent identifies student weaknesses.

    Metrics:
    - Topic Coverage: Percentage of expected topics identified
    - Weakness Precision: How many identified weaknesses are relevant
    - Weakness Recall: How many expected weaknesses were found
    """

    @staticmethod
    def evaluate(predicted: Dict[str, Any], ground_truth: Dict[str, Any]) -> Dict[str, Any]:
        """
        Evaluate analysis quality.

        Args:
            predicted: Agent's analysis with weaknesses list
            ground_truth: Expected weaknesses and topics

        Returns:
            Dictionary with analysis quality metrics
        """
        pred_weaknesses = predicted.get('weaknesses', [])
        expected_weaknesses = ground_truth.get('expected_weaknesses', [])
        expected_topics = ground_truth.get('expected_topics', [])

        # Extract topics from predicted analysis
        # Prefer the 'topics' field if available, otherwise fall back to extracting from weaknesses
        pred_topics = set()
        topics_list = predicted.get('topics', [])

        if topics_list:
            # Use the topics field (contains ALL topics tested, not just weaknesses)
            pred_topics = {topic.lower() for topic in topics_list if topic}
        else:
            # Fallback: extract from weaknesses for backward compatibility
            for weakness in pred_weaknesses:
                if isinstance(weakness, dict):
                    topic = weakness.get('topic', '')
                    if topic:
                        pred_topics.add(topic.lower())
                elif isinstance(weakness, str):
                    # Simple string weakness
                    pred_topics.add(weakness.lower())

        # Expected topics (normalized)
        expected_topics_set = {t.lower() for t in expected_topics}
        expected_weaknesses_set = {w.lower() for w in expected_weaknesses}

        # Calculate metrics
        if expected_topics_set:
            # Topic coverage: intersection / expected
            topics_found = pred_topics.intersection(expected_topics_set)
            topic_coverage = len(topics_found) / len(expected_topics_set)
        else:
            topic_coverage = 1.0 if not pred_topics else 0.0

        # Weakness recall: how many expected weaknesses were identified
        if expected_weaknesses_set:
            weaknesses_found = pred_topics.intersection(expected_weaknesses_set)
            weakness_recall = len(weaknesses_found) / len(expected_weaknesses_set)
        else:
            weakness_recall = 1.0 if not pred_weaknesses else 0.0

        # Weakness precision: of identified weaknesses, how many are relevant
        if pred_topics:
            relevant_weaknesses = pred_topics.intersection(expected_weaknesses_set.union(expected_topics_set))
            weakness_precision = len(relevant_weaknesses) / len(pred_topics)
        else:
            weakness_precision = 1.0 if not expected_weaknesses_set else 0.0

        return {
            'topic_coverage': topic_coverage,
            'weakness_recall': weakness_recall,
            'weakness_precision': weakness_precision,
            'topics_found': list(topics_found) if expected_topics_set else [],
            'topics_expected': list(expected_topics_set),
            'weaknesses_identified': len(pred_weaknesses),
            'weaknesses_expected': len(expected_weaknesses)
        }


class RecommendationRelevanceMetric:
    """
    Measures how relevant recommendations are to identified weaknesses.

    Metrics:
    - Alignment: How well recommendations address identified weaknesses
    - Specificity: How specific/actionable recommendations are
    - Coverage: Whether all weaknesses have recommendations
    """

    @staticmethod
    def evaluate(
        predicted: Dict[str, Any],
        analysis: Dict[str, Any],
        ground_truth: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Evaluate recommendation relevance.

        Args:
            predicted: Agent's recommendations
            analysis: Agent's weakness analysis (for context)
            ground_truth: Expected recommendations (if any)

        Returns:
            Dictionary with recommendation relevance metrics
        """
        recommendations = predicted.get('recommendations', '')
        weaknesses = analysis.get('weaknesses', [])
        expected_recs = ground_truth.get('expected_recommendations', [])

        # Count recommendations (simple heuristic: split by newlines or periods)
        if isinstance(recommendations, str):
            rec_list = [r.strip() for r in recommendations.split('\n') if r.strip() and not r.strip().startswith('#')]
        else:
            rec_list = recommendations if isinstance(recommendations, list) else []

        num_recommendations = len(rec_list)
        num_weaknesses = len(weaknesses)

        # Coverage: at least one recommendation per weakness
        coverage = min(num_recommendations / num_weaknesses, 1.0) if num_weaknesses > 0 else 0.0

        # Specificity: check if recommendations mention specific topics from weaknesses
        specificity_score = 0
        if rec_list and weaknesses:
            weakness_topics = set()
            for weakness in weaknesses:
                if isinstance(weakness, dict):
                    topic = weakness.get('topic', '')
                    if topic:
                        weakness_topics.add(topic.lower())

            for rec in rec_list:
                rec_lower = rec.lower()
                # Check if recommendation mentions any weakness topic
                if any(topic in rec_lower for topic in weakness_topics):
                    specificity_score += 1

            specificity = specificity_score / len(rec_list) if rec_list else 0
        else:
            specificity = 0.0

        # Alignment with expected recommendations (if provided)
        alignment = 0.0
        if expected_recs and rec_list:
            # Simple keyword matching
            expected_keywords = set()
            for exp_rec in expected_recs:
                # Extract key terms (words > 4 chars)
                keywords = [w.lower() for w in exp_rec.split() if len(w) > 4]
                expected_keywords.update(keywords)

            matched_keywords = 0
            for rec in rec_list:
                rec_words = {w.lower() for w in rec.split() if len(w) > 4}
                if rec_words.intersection(expected_keywords):
                    matched_keywords += 1

            alignment = matched_keywords / len(rec_list) if rec_list else 0.0

        return {
            'coverage': coverage,
            'specificity': specificity,
            'alignment': alignment,
            'num_recommendations': num_recommendations,
            'num_weaknesses': num_weaknesses,
            'has_expected_recommendations': len(expected_recs) > 0
        }


def calculate_overall_score(
    grading_metrics: Dict[str, Any],
    analysis_metrics: Dict[str, Any],
    recommendation_metrics: Dict[str, Any]
) -> Dict[str, float]:
    """
    Calculate overall performance score across all metrics.

    Weights:
    - Grading Accuracy: 40%
    - Analysis Quality: 35%
    - Recommendation Relevance: 25%

    Returns:
        Dictionary with component scores and overall score
    """
    # Grading score: average of exact match and tolerance
    grading_score = (
        (1.0 if grading_metrics['exact_match'] else 0.0) * 0.6 +
        (1.0 if grading_metrics['within_tolerance'] else 0.0) * 0.4
    )

    # Analysis score: average of coverage, recall, precision
    analysis_score = (
        analysis_metrics['topic_coverage'] * 0.4 +
        analysis_metrics['weakness_recall'] * 0.3 +
        analysis_metrics['weakness_precision'] * 0.3
    )

    # Recommendation score: average of coverage, specificity, alignment
    recommendation_score = (
        recommendation_metrics['coverage'] * 0.4 +
        recommendation_metrics['specificity'] * 0.4 +
        (recommendation_metrics['alignment'] * 0.2 if recommendation_metrics['has_expected_recommendations'] else 0.3)
    )

    # Overall score (weighted average)
    overall_score = (
        grading_score * 0.40 +
        analysis_score * 0.35 +
        recommendation_score * 0.25
    )

    return {
        'grading_score': grading_score,
        'analysis_score': analysis_score,
        'recommendation_score': recommendation_score,
        'overall_score': overall_score
    }
