# ADR-007: Conversational Agent Tool Integration

## Status
Accepted

## Date
2024-11-26

## Context

The existing `conversational_agent.py` was a guidance-only agent that explained how to use the system but could not actually invoke any backend processing. Users had to use the `demo.py` CLI or call the Python API directly to process exams.

The goal was to create a conversational interface via ADK Web UI that:
1. Allows users to simulate being a teacher or student
2. Accepts exam question images via file paths
3. Connects to the backend FeedbackSystem pipeline
4. Provides grading results and learning recommendations

## Decision

We chose to implement the conversational agent using **ADK's tool pattern** rather than alternatives like:
- Direct pipeline invocation from the agent's instruction
- Custom middleware layer
- Separate microservice architecture

### Architecture

```
ConversationalAgent (LlmAgent)
    │
    │ tools=[...]
    │
    ▼
conversational_tools.py
    │
    ├── authenticate_user()      ─── Session state management
    ├── process_exam_from_image() ─► ImageProcessingAgent + FeedbackSystem
    ├── process_exam_from_text() ──► FeedbackSystem.process_exam()
    ├── get_my_results()         ──► StudentDatabase
    ├── get_student_results()    ──► StudentDatabase + authorization
    ├── get_class_analytics()    ──► StudentDatabase + authorization
    ├── list_students()          ──► StudentDatabase + authorization
    └── get_learning_recommendations() ─► StudentDatabase
```

### Key Design Choices

1. **Session-based authentication via ToolContext.state**
   - User authenticates once at conversation start
   - Role stored in session state (`current_user_role`, `current_user_id`)
   - Each tool checks authorization before executing

2. **Singleton FeedbackSystem accessor**
   - Added `get_feedback_system()` to `agent.py`
   - Ensures all tools share the same database and session instances
   - Avoids creating multiple FeedbackSystem instances per conversation

3. **Tool-based invocation over direct instructions**
   - Tools provide structured interfaces for complex operations
   - Enables proper error handling and authorization checks
   - Results can be formatted for human-readable display

4. **Image path input rather than base64**
   - Simpler for ADK Web UI users
   - Validates paths before processing
   - Supports common image formats (jpg, png, gif, webp)

## Consequences

### Positive
- Clean separation between conversation logic and backend processing
- Role-based access control enforced at tool level
- Reusable tools can be extended for other interfaces
- Natural language interaction with structured backend operations
- Session state managed through ADK's ToolContext pattern

### Negative
- Image paths must be accessible from the server running ADK
- Session state is in-memory (not persistent across server restarts)
- Tool results need formatting for conversational display

### Neutral
- Requires ADK Web UI for testing (not standard CLI)
- Tools are async-aware for image processing

## Files Changed

| File | Change |
|------|--------|
| `feedback_agent/agent.py` | Added `get_feedback_system()` singleton |
| `feedback_agent/conversational_tools.py` | NEW - 8 tools + helpers |
| `feedback_agent/conversational_agent.py` | REWRITTEN - LlmAgent with tools |

## Alternatives Considered

### 1. Direct Pipeline Invocation from Instructions
- **Rejected**: No way to handle structured input/output, authorization, or error states cleanly

### 2. Custom Middleware Layer
- **Rejected**: Adds unnecessary complexity; ADK tools are the idiomatic pattern

### 3. Separate Microservice
- **Rejected**: Over-engineering for capstone project scope

## References

- ADK Tool Pattern: https://google.github.io/adk-docs/
- Original guidance-only agent: `conversational_agent.py` (94 lines)
- FeedbackSystem architecture: ADR-001, ADR-002
