# ADR 002: Agent State Flow Pattern Using output_key and Instruction Placeholders

**Date**: 2025-11-24

**Status**: ✅ Accepted and Implemented

## Context

In a Sequential Agent pipeline, agents need to pass data to each other. The initial implementation attempted manual state injection, which created several problems:

1. **Tight Coupling**: Agents were tightly coupled to the custom wrapper code
2. **No Clear Data Contract**: Unclear what data each agent expected or produced
3. **Error-Prone**: Manual string manipulation and JSON parsing
4. **Not Testable**: Hard to test individual agents in isolation
5. **Against ADK Patterns**: Didn't follow the recommended state flow approach

### Problem Statement

How should agents in a sequential pipeline communicate?

**Example Pipeline**:
```
GradingAgent → AnalysisAgent → RecommendationAgent
```

Each agent needs:
- **Input**: Data from previous agent or initial state
- **Processing**: LLM generates structured output
- **Output**: Results available to next agent

## Decision

**We decided to use ADK's `output_key` pattern with instruction placeholders** for agent communication, as demonstrated in the Kaggle course (Day 1b: Agent Architectures and Day 5a: Agent-to-Agent Communication).

### Key Principles

1. **Each agent declares** its `output_key` (where it writes results)
2. **Next agent references** previous output using `{placeholder}` in instructions
3. **Runner handles** state propagation automatically
4. **State is typed** using JSON schemas with `response_mime_type`

### Implementation Pattern

```python
# Agent 1: GradingAgent
grading_agent.output_key = "grading_result"
grading_agent.instruction = """
Exam content: {exam_content}
Answer key: {answer_key}

Grade the exam and output JSON with this structure:
{
    "total_score": <number>,
    "max_score": <number>,
    "corrections": [...]
}
"""
grading_agent.generate_content_config = types.GenerateContentConfig(
    response_mime_type='application/json'
)

# Agent 2: AnalysisAgent
analysis_agent.output_key = "weakness_analysis"
analysis_agent.instruction = """
Review the grading results: {grading_result}

Identify weaknesses and output JSON:
{
    "weaknesses": [...],
    "summary": "..."
}
"""

# Agent 3: RecommendationAgent
recommendation_agent.output_key = "learning_plan"
recommendation_agent.instruction = """
Based on the weakness analysis: {weakness_analysis}

Create a learning plan as JSON:
{
    "learning_objectives": [...],
    "encouragement": "..."
}
"""
```

### State Flow Diagram

```
Initial State (from process_exam):
{
    "exam_id": "...",
    "student_id": "...",
    "exam_content": "...",
    "answer_key": "..."
}
        ↓
  GradingAgent reads: {exam_content}, {answer_key}
  GradingAgent writes to: "grading_result"
        ↓
State after GradingAgent:
{
    ...initial state...,
    "grading_result": "{...JSON...}"
}
        ↓
  AnalysisAgent reads: {grading_result}
  AnalysisAgent writes to: "weakness_analysis"
        ↓
State after AnalysisAgent:
{
    ...previous state...,
    "weakness_analysis": "{...JSON...}"
}
        ↓
  RecommendationAgent reads: {weakness_analysis}
  RecommendationAgent writes to: "learning_plan"
        ↓
Final State:
{
    ...all previous state...,
    "learning_plan": "{...JSON...}"
}
```

## Consequences

### Positive ✅

1. **Clear Data Contract**: Each agent explicitly declares inputs (placeholders) and outputs (output_key)
2. **Loose Coupling**: Agents don't know about each other, only about state keys
3. **Testable**: Can test each agent independently by mocking state
4. **Self-Documenting**: Instructions show exactly what data flows where
5. **Type-Safe**: JSON schemas validate output structure
6. **Debuggable**: State can be inspected at any point in the pipeline
7. **Course-Compliant**: Follows Day 5a patterns from Kaggle course
8. **Maintainable**: Easy to add, remove, or reorder agents
9. **Reusable**: Agents can be used in different pipelines
10. **Observable**: State changes are tracked in session events

### Negative ⚠️

1. **String-Based Keys**: Typos in placeholder names won't be caught until runtime
2. **No Type Checking**: Python type hints don't validate state keys
3. **JSON Strings**: Outputs are JSON strings, not Python objects (requires parsing)
4. **Placeholder Syntax**: Must remember `{key}` syntax in instructions

### Neutral ℹ️

1. **State Accumulation**: State grows with each agent (mitigated by context compaction)
2. **Naming Convention**: Must establish consistent key naming (we use snake_case)

## Implementation Details

### Output Key Naming Convention

We follow this pattern:
- Use **snake_case** for all keys
- Use **descriptive names** that indicate content
- Use **result/output/analysis/plan** suffixes

Examples:
- ✅ `grading_result` - Clear, descriptive
- ✅ `weakness_analysis` - Indicates what's in it
- ✅ `learning_plan` - Obvious purpose
- ❌ `output` - Too generic
- ❌ `data` - Unclear content
- ❌ `result1` - Non-descriptive

### Instruction Placeholder Best Practices

1. **Be Explicit**: `"Review the grading results: {grading_result}"` is better than `"Review: {grading_result}"`
2. **Show Structure**: Include example JSON in instructions for clarity
3. **Handle Missing Data**: Instructions should be robust to missing placeholders
4. **Use Context**: Provide enough context about what the placeholder contains

### JSON Output Validation

Each agent specifies its output schema in instructions:

```python
instruction = """
Output must be a JSON object with the following structure:
{
    "field1": <type>,
    "field2": <type>,
    ...
}
"""
generate_content_config = types.GenerateContentConfig(
    response_mime_type='application/json'
)
```

This ensures:
- LLM returns valid JSON
- Schema is documented
- Consumers know what to expect

### Error Handling Strategy

When accessing state in callbacks:

```python
async def _log_grading_callback(self, callback_context: CallbackContext):
    try:
        # 1. Check if key exists
        result_str = callback_context.state.get("grading_result")
        if not result_str:
            logger.error("No grading_result in state")
            return

        # 2. Parse JSON
        result = json.loads(result_str)

        # 3. Validate required fields
        if "total_score" not in result:
            logger.error("Missing total_score in grading_result")
            return

        # 4. Use data
        self.db.log_exam(...)

    except json.JSONDecodeError as e:
        logger.error(f"Error parsing grading JSON: {e}")
    except Exception as e:
        logger.error(f"Error in grading callback: {e}", exc_info=True)
```

## Alternatives Considered

### Alternative 1: Direct Agent References
```python
# Agent B gets output from Agent A directly
analysis_agent.input_agent = grading_agent
```

**Rejected** because:
- Tight coupling between agents
- Can't reorder or remove agents easily
- Doesn't work with ADK's sequential pattern
- Not the ADK-recommended approach

### Alternative 2: Event-Based Communication
```python
# Agents emit events, others subscribe
grading_agent.emit("grading_complete", result)
```

**Rejected** because:
- More complex than needed
- ADK doesn't provide event bus
- Overkill for sequential pipeline
- Would require custom infrastructure

### Alternative 3: Shared Object Pattern
```python
# All agents write to same object
class ExamContext:
    grading_result = None
    analysis_result = None
```

**Rejected** because:
- Doesn't integrate with ADK's state system
- Not visible in session history
- Can't use context compaction
- Loses observability

### Alternative 4: Database Pass-Through
```python
# Each agent writes to DB, next reads from DB
grading_agent → DB → analysis_agent → DB → ...
```

**Rejected** because:
- Unnecessary I/O overhead
- Tight coupling to database
- Harder to test
- Doesn't use ADK's state management

## Examples

### Complete Agent Configuration

```python
# In _build_pipeline()

# Configure GradingAgent
grading_agent.agent.output_key = "grading_result"
grading_agent.agent.after_agent_callback = self._log_grading_callback
grading_agent.agent.instruction = '''
You are an expert grader.

Exam content: {exam_content}
Answer key: {answer_key}

Compare the student's answers with the correct answers and calculate the score.

Output must be a JSON object with the following structure:
{{
    "total_score": <number>,
    "max_score": <number>,
    "corrections": [
        {{
            "question": <str>,
            "student_answer": <str>,
            "correct_answer": <str>,
            "is_correct": <boolean>,
            "feedback": <str>
        }}
    ],
    "general_feedback": <str>
}}
'''

# Configure AnalysisAgent
analysis_agent.agent.output_key = "weakness_analysis"
analysis_agent.agent.after_agent_callback = self._log_analysis_callback
analysis_agent.agent.instruction = '''
You are an educational analyst.

Review the grading results: {grading_result}

Identify the student's weaknesses and knowledge gaps.

Output must be a JSON object with the following structure:
{{
    "weaknesses": [
        {{
            "topic": <str>,
            "description": <str>,
            "severity": <str (low|medium|high)>
        }}
    ],
    "summary": <str>
}}
'''

# Configure RecommendationAgent
recommendation_agent.agent.output_key = "learning_plan"
recommendation_agent.agent.after_agent_callback = self._log_recommendation_callback
recommendation_agent.agent.instruction = '''
You are a learning advisor.

Based on the weakness analysis: {weakness_analysis}

Create a personalized learning plan with specific, actionable recommendations.

Output must be a JSON object with the following structure:
{{
    "learning_objectives": [
        {{
            "objective": <str>,
            "resources": [<str>],
            "estimated_time": <str>
        }}
    ],
    "encouragement": <str>
}}
'''
```

## Testing Strategy

State flow can be tested at multiple levels:

### Unit Tests (Individual Agent)
```python
async def test_grading_agent():
    # Mock state with required inputs
    mock_state = {
        "exam_content": "Q: 1+1? A: 2",
        "answer_key": "Q: 1+1? A: 2"
    }

    # Run agent
    result = await run_agent(grading_agent, mock_state)

    # Verify output_key is set
    assert "grading_result" in result
```

### Integration Tests (Full Pipeline)
```python
async def test_exam_pipeline():
    # Set initial state
    initial_state = {
        "exam_content": "...",
        "answer_key": "..."
    }

    # Run pipeline
    final_state = await run_pipeline(pipeline, initial_state)

    # Verify all agents produced output
    assert "grading_result" in final_state
    assert "weakness_analysis" in final_state
    assert "learning_plan" in final_state
```

## Migration Notes

**From old pattern:**
```python
# Old: Manual state injection
run_agent(pipeline, "", session_state={"exam_content": content})
```

**To new pattern:**
```python
# New: State in session creation
session = await session_service.create_session(
    app_name="feedback_system",
    user_id=user_id,
    session_id=session_id,
    state={"exam_content": content}  # Initial state here
)
```

## Related ADRs

- ADR-001: Migrate to ADK Runner Pattern
- ADR-003: Memory Service Integration (future)

## References

- [Kaggle Day 1b: Agent Architectures](agent_notebooks_example/day-1b-agent-architectures.ipynb)
- [Kaggle Day 5a: Agent-to-Agent Communication](agent_notebooks_example/day-5a-agent2agent-communication.ipynb)
- [ADK Documentation: State Management](https://google.github.io/adk-docs/core/state/)
- `feedback_agent/agent_refactored.py` - Implementation

## Success Metrics

- [x] Each agent has clear `output_key`
- [x] Instructions use `{placeholder}` syntax
- [x] JSON schemas defined in instructions
- [x] State flows through pipeline correctly
- [x] Callbacks can access state reliably
- [ ] All agents migrated to new pattern
- [ ] Unit tests for each agent
- [ ] Integration tests for pipeline

---

**Last Updated**: 2025-11-24
**Author**: Claude Code (AI Agent Capstone Project)
**Review Status**: Approved
