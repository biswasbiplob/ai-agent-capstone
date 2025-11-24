# ADR-006: Observability with Custom Plugin System

**Status**: Accepted
**Date**: 2025-11-24
**Decision Makers**: Development Team
**Tags**: observability, monitoring, metrics, ADK

## Context

The feedback system processes student exams through a multi-agent pipeline (grading → analysis → recommendations). To demonstrate production-ready practices and monitor system health, we need comprehensive observability including:

- Tracking exam processing metrics (duration, scores, success rates)
- Monitoring agent execution times
- Measuring system performance over time
- Identifying bottlenecks and failures
- Providing structured logging for debugging

## Decision

Implement a dual-layer observability approach using:

1. **ADK's Built-in LoggingPlugin**: For standard agent lifecycle logging
2. **Custom ExamMetricsPlugin**: For domain-specific metrics tracking

### Architecture

```
App
├── LoggingPlugin (ADK built-in)
│   ├── Logs invocation start/end
│   ├── Logs LLM requests/responses
│   ├── Tracks token usage
│   └── Outputs to console
│
└── ExamMetricsPlugin (Custom)
    ├── Tracks exam processing metrics
    ├── Monitors agent execution times
    ├── Extracts scores and weaknesses
    ├── Calculates statistics
    └── Writes JSONL metrics file
```

### Plugin System Design

**BasePlugin Implementation**:
```python
class ExamMetricsPlugin(BasePlugin):
    def __init__(self, log_to_file: bool = True, metrics_file: str = "exam_metrics.jsonl"):
        super().__init__(name="exam_metrics_plugin")
        # ... storage initialization

    async def before_run_callback(self, **kwargs) -> None:
        """Called when exam processing starts"""
        invocation_context = kwargs.get('invocation_context')
        session = invocation_context.session
        # Track start time, extract metadata from session.state

    async def after_run_callback(self, **kwargs) -> None:
        """Called when exam processing completes"""
        # Calculate metrics, write to file

    async def before_agent_callback(self, **kwargs) -> None:
        """Track agent start time"""

    async def after_agent_callback(self, **kwargs) -> None:
        """Calculate agent duration"""
```

**Key Patterns Discovered**:

1. **Plugin Registration**: Plugins must be registered in `App`, not `Runner`
   ```python
   self.app = App(
       name="feedback_system",
       root_agent=self.pipeline,
       plugins=[logging_plugin, metrics_plugin],  # HERE, not in Runner
       events_compaction_config=...
   )
   ```

2. **Callback Signatures**: All callback methods must be async
   ```python
   async def after_run_callback(self, **kwargs) -> None:
   ```

3. **Context Access**:
   - `invocation_context.session.id` - Session ID (not `session_id`)
   - `invocation_context.session.state` - Session state (not `invocation_context.state`)
   - `agent_context.agent.name` - Agent name

4. **State Flow**: Exam data flows through session state:
   ```
   initial_state → grading_result → weakness_analysis → learning_plan
   ```

### Metrics Tracked

**Per-Exam Metrics** (written to JSONL):
- `session_id`: Unique session identifier
- `exam_id`, `student_id`, `subject`: Exam metadata
- `start_time`, `end_time`: Timestamps
- `total_duration`: Processing time in seconds
- `agent_timings`: Duration for each agent (grading, analysis, recommendation)
- `total_score`, `max_score`, `percentage`: Grading results
- `weaknesses_count`: Number of weaknesses identified
- `weakness_severities`: Breakdown by low/medium/high
- `status`: "completed" or "failed"

**Aggregated Statistics**:
- Total exams processed
- Success/failure counts and rates
- Total and average processing time
- Score distribution (min, max, avg)

### Output Formats

**JSONL Metrics File** (`exam_metrics.jsonl`):
```jsonl
{"session_id": "exam_123", "total_duration": 5.5, "total_score": 8, "max_score": 10, ...}
{"session_id": "exam_124", "total_duration": 4.2, "total_score": 9, "max_score": 10, ...}
```

**Structured Logs** (`feedback_system.log`):
```
2025-11-24 18:55:03,307 - feedback_agent.plugins - INFO - 📊 Exam 85ce59b0... processed in 5.50s
```

**Summary Statistics** (programmatic access):
```python
system.get_metrics_summary()
# Returns: {"total_exams_processed": 3, "avg_processing_time": 4.99, ...}
```

## Alternatives Considered

### 1. Use Only LoggingPlugin
**Pros**: Simpler, no custom code
**Cons**: No domain-specific metrics, no aggregation, no JSONL output
**Why Rejected**: Insufficient for production monitoring needs

### 2. External Monitoring Service (Datadog, New Relic)
**Pros**: Enterprise-grade features, dashboards, alerting
**Cons**: Overkill for capstone project, requires external dependencies
**Why Rejected**: Not suitable for educational demonstration

### 3. Database-Only Metrics
**Pros**: Centralized storage, queryable
**Cons**: No real-time monitoring, no aggregation, requires separate tooling
**Why Rejected**: Less flexible than JSONL + in-memory approach

### 4. OpenTelemetry Integration
**Pros**: Industry standard, distributed tracing
**Cons**: Complex setup, steep learning curve
**Why Rejected**: Too heavyweight for this project scope

## Consequences

### Positive

1. **Production-Ready Observability**: Demonstrates best practices for monitoring AI agent systems
2. **Performance Insights**: Clear visibility into processing times and bottlenecks
3. **Debugging Support**: Structured logs help diagnose issues quickly
4. **Metrics Export**: JSONL format enables easy integration with analysis tools
5. **Flexible Access**: Both file-based (JSONL) and programmatic (API) access to metrics
6. **Capstone Demonstration**: Shows understanding of ADK plugin system and production practices

### Negative

1. **Async Complexity**: All callbacks must be async, adding complexity
2. **Context Access Patterns**: Non-obvious attribute access (e.g., `session.id` not `session_id`)
3. **Error Handling**: Plugin errors can crash the entire pipeline if not handled
4. **Testing Overhead**: Requires integration tests to verify metrics capture
5. **Documentation Burden**: Plugin API patterns need to be documented

### Neutral

1. **Two Observability Layers**: More powerful but requires understanding both systems
2. **JSONL vs Database**: Trade-off between simplicity and queryability
3. **In-Memory Aggregation**: Fast but lost on restart

## Implementation Notes

### Bug Fixes During Implementation

1. **ImportError**: Changed `Plugin` to `BasePlugin`
2. **TypeError**: Added required `name` parameter to `__init__`
3. **ValueError**: Moved plugins from Runner to App
4. **TypeError**: Made all callbacks async
5. **AttributeError**: Fixed session attribute access patterns:
   - `invocation_context.session_id` → `invocation_context.session.id`
   - `session.session_id` → `session.id`
   - `invocation_context.state` → `invocation_context.session.state`

### Testing Strategy

Integration test (`tests/test_observability.py`) verifies:
- Plugin registration and initialization
- Metrics capture during exam processing
- JSONL file creation and format
- Summary statistics accuracy
- Structured logging functionality

**Test Results**: ✅ All tests passing (3 exams processed, 100% success rate)

## References

- Google ADK Plugin Documentation
- Day 5b Kaggle Course: Production Patterns
- `feedback_agent/plugins.py`: Implementation
- `tests/test_observability.py`: Integration tests
- ADR-001: Migration to ADK Runner pattern (foundational architecture)

## Review and Approval

**Reviewed By**: Development Team
**Approved By**: Technical Lead
**Review Date**: 2025-11-24

---

**Related ADRs**:
- ADR-001: Migrate to ADK Runner Pattern
- ADR-002: Agent State Flow Pattern

**Supersedes**: None
**Superseded By**: None
