# ADR-005: Fix AnalysisAgent Topic Identification

**Status**: Accepted
**Date**: 2025-11-24
**Context**: Phase 5.6 - Evaluation Framework Analysis and Improvement

## Context and Problem Statement

During the first full evaluation run (eval_results_20251124_180849.json), we discovered a critical architectural flaw:

- **Overall Pass Rate**: 37.5% (3/8 tests passed)
- **Analysis Quality Score**: 0.302 (far below 0.70 threshold)
- **Topic Coverage**: 0% in 5 out of 8 tests
- **Root Cause**: AnalysisAgent only received graded results, not the original exam content

### Evidence from Failed Tests

**Example: physics_poor_004**
- Expected Topics: Newton's Laws, Force Calculations, Speed of Light, Kinetic Energy
- Topics Found: [] (NONE!)
- What Agent Identified: Generic weaknesses ("Calculations", "Units")
- What Was Expected: Specific topics from the exam

**Pattern Identified**:
```
Current: Student Error → Generic Description
Example: "F=ma calculation wrong" → "Calculations"

Expected: Student Error → Specific Exam Topic
Example: "F=ma calculation wrong" → "Newton's Laws" → "Force Calculations"
```

### Impact
- 5/8 test failures directly caused by poor topic identification
- Hard tests particularly affected (0/3 passed, 0.444 avg score)
- Medium tests performed well (3/4 passed), suggesting the issue scales with exam complexity

## Decision

Update AnalysisAgent to receive both graded results AND original exam content:

1. **Update agent_refactored.py pipeline**:
   - AnalysisAgent instruction now includes {exam_content} state placeholder
   - Agent can read original exam questions and topics

2. **Update AnalysisAgent class** (agents/analysis_agent.py):
   - Added exam_content parameter to analyze_performance()
   - Made parameter optional for backward compatibility
   - Added warning log if exam_content not provided

3. **Enhanced instruction prompting**:
   - Explicit 4-step process: Read exam → Review grading → Match errors to topics → List weaknesses
   - CRITICAL RULES section with specific examples
   - Clear guidance: Use "Newton's Laws" not "Physics", "WWII Timeline" not "Historical Dates"

## Implementation

### Changes to agent_refactored.py

**Before**:
```python
analysis_agent.agent.instruction = '''
You are an educational analyst.

Review the grading results: {grading_result}

Identify the student's weaknesses and knowledge gaps.
'''
```

**After**:
```python
analysis_agent.agent.instruction = '''
You are an expert educational analyst.

Input from state:
1. ORIGINAL EXAM CONTENT: {exam_content}
2. GRADING RESULTS: {grading_result}

Your analysis process:
STEP 1: Carefully read the ORIGINAL EXAM CONTENT to identify all topics/concepts being tested
STEP 2: Review the GRADING RESULTS to see which questions the student got wrong
STEP 3: Match each error to the specific topic/concept from the exam
STEP 4: List the topics where the student showed weakness

CRITICAL RULES:
- The "topic" field MUST reference specific topics/concepts from the exam content
- If the exam asks about "Newton's Laws", say "Newton's Laws" not "Physics"
- Be specific and match topics to what was actually tested
'''
```

### Changes to analysis_agent.py

**Before**:
```python
def analyze_performance(self, graded_exam: Dict[str, Any]) -> Dict[str, Any]:
    prompt = f"Please analyze the following graded exam..."
```

**After**:
```python
def analyze_performance(
    self,
    graded_exam: Dict[str, Any],
    exam_content: str = None  # NEW PARAMETER
) -> Dict[str, Any]:
    if not exam_content:
        logger.warning("No exam_content provided. Topic identification may be limited.")
        # ... proceed with graded_exam only
    else:
        prompt = f"""
        --- ORIGINAL EXAM CONTENT ---
        {exam_content}

        --- GRADED EXAM DATA ---
        {json.dumps(graded_exam, indent=2)}
        """
```

## Consequences

### Positive
- **Expected Improvement**: Analysis quality 0.302 → 0.600+ (~100% increase)
- **Expected Improvement**: Overall pass rate 37.5% → 70%+ (meeting threshold)
- **Expected Improvement**: Topic coverage 0% → 50%+ in previously failing tests
- Agent now has full context needed for accurate analysis
- Maintains backward compatibility (exam_content is optional)
- Clear error/warning messages if exam_content missing

### Negative
- Slightly more complex data flow in pipeline
- Agent receives more input tokens (exam_content + grading_result)
- Increased API costs per analysis (more tokens processed)

### Neutral
- No changes required to GradingAgent or RecommendationAgent
- Evaluation framework metrics remain unchanged
- Database schema unchanged (state-based flow handles the data)

## Verification Plan

1. **Re-run Evaluations**:
   ```bash
   python evals/run_evaluation.py
   ```

2. **Expected Results**:
   - Overall pass rate: 70%+ (currently 37.5%)
   - Analysis quality: 0.65+ (currently 0.302)
   - Topic coverage: 50%+ (currently 0% in many tests)
   - Hard tests: 50%+ pass rate (currently 0%)

3. **Monitor Specific Tests**:
   - physics_poor_004: Should now identify "Newton's Laws", "Force Calculations"
   - biology_failing_008: Should now identify "DNA Structure", "Cell Division"
   - english_grammar_007: Should now identify "Parts of Speech", "Pronouns"

## Alternatives Considered

### Alternative 1: Use More Powerful Model
- **Approach**: Switch from gemini-2.0-flash to gemini-1.5-pro
- **Rejected Because**: Doesn't fix architectural issue; same information gap exists
- **Trade-offs**: Better reasoning but 7.5x slower (2 req/min vs 15 req/min)

### Alternative 2: Post-Process Analysis Results
- **Approach**: Add a separate agent to extract topics from exam content
- **Rejected Because**: Adds complexity; better to fix at source
- **Trade-offs**: More API calls, more latency, harder to maintain

### Alternative 3: Embed Topics in Grading Results
- **Approach**: Have GradingAgent extract and include topics
- **Rejected Because**: Not GradingAgent's responsibility; violates separation of concerns
- **Trade-offs**: Couples grading and analysis logic

## References

- EVALUATION_ANALYSIS.md: Detailed breakdown of test failures
- PROGRESS.md: Phase 5 evaluation results
- eval_results_20251124_180849.json: Full evaluation data
- [Kaggle AI Agents Course - Day 5a: State Management](https://www.kaggle.com/learn/ai-agents)

## Follow-up Actions

1. Re-run evaluations with updated AnalysisAgent
2. Document results in PROGRESS.md
3. If pass rate < 70%, investigate remaining failures:
   - Check grading accuracy issues (2 tests had +12.5% errors)
   - Consider model upgrade for hard tests
   - Add few-shot examples to agent instructions
4. Create EVALUATION_SUMMARY.md comparing before/after results
