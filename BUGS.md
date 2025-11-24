# Known Issues and Bugs

**Project**: Feedback Agent Capstone
**Last Updated**: 2025-11-24

---

## Critical Bugs 🔴

### BUG-001: Missing `run_agent_multimodal()` Function
**Severity**: Critical
**Status**: Known (Pre-refactor)
**Location**: `feedback_agent/utils.py`, referenced by `feedback_agent/agents/image_processing_agent.py:40`

**Description**:
The `ImageProcessingAgent` calls `run_agent_multimodal()` which doesn't exist in utils.py. Only `run_agent()` is implemented.

**Impact**:
Image processing functionality is completely broken. Cannot process exam photos.

**Workaround**:
None. Feature is non-functional.

**Fix Plan**:
Will be resolved in Phase 4 by implementing proper multimodal Runner support.

---

### BUG-002: Improper Session State Management
**Severity**: Critical
**Status**: Known (Pre-refactor)
**Location**: `feedback_agent/agent.py`, entire `FeedbackSystem` class

**Description**:
Custom `run_agent()` wrapper bypasses ADK's proper session management. Manual session_state injection doesn't follow ADK patterns.

**Impact**:
- No conversation history tracking
- State may not propagate correctly between agents
- Can't use ADK features like memory service, context compaction
- Agents reference session state that doesn't exist properly

**Example**:
```python
# feedback_agent/agents/grading_agent.py:19-45
instruction='''
The exam content and answer key are available in the session state.
Access them using the session state variables:
- exam_content: The student's exam with their answers
- answer_key: The correct answers
'''
```
Instructions reference session state, but our custom runner doesn't set it up correctly.

**Fix Plan**:
Will be resolved in Phase 1 by replacing custom runner with proper ADK Runner and SessionService.

---

## High Priority Issues 🟡

### BUG-003: Callback Pattern Anti-Pattern
**Severity**: High
**Status**: Known (Pre-refactor)
**Location**: `feedback_agent/agent.py:39-88`

**Description**:
Callbacks are instance methods instead of standalone async functions. Access pattern is incorrect.

**Issues**:
1. Using `callback_context.state.get()` instead of proper event access
2. Not async/await pattern
3. Manual JSON parsing with brittle string search
4. Errors silently logged instead of propagated

**Example**:
```python
def _log_grading(self, callback_context: CallbackContext) -> None:
    try:
        response_text = callback_context.state.get("grading_output")
        # Should be async and access via proper event structure
```

**Fix Plan**:
Will be resolved in Phase 1.3 by converting to async standalone functions.

---

### BUG-004: No Error Propagation
**Severity**: High
**Status**: Known (Pre-refactor)
**Location**: Multiple files

**Description**:
Most errors are caught and logged, but not re-raised or handled properly.

**Example**:
```python
# feedback_agent/agent.py:80
except Exception as e:
    logger.error(f"Error logging analysis: {e}")
    # Error is swallowed!
```

**Impact**:
Silent failures. System may appear to work but data isn't being saved.

**Fix Plan**:
Add proper error handling during Phase 1 refactor.

---

## Medium Priority Issues 🟠

### BUG-005: No Authentication System
**Severity**: Medium
**Status**: Known (Pre-refactor)
**Location**: Entire codebase

**Description**:
No user authentication or role-based access control. Anyone can access any student's data.

**Impact**:
Privacy violation. Not suitable for real-world use.

**Fix Plan**:
Will be implemented in Phase 2.

---

### BUG-006: Fragile JSON Parsing
**Severity**: Medium
**Status**: Known (Pre-refactor)
**Location**: `feedback_agent/agent.py:42-48, 66-71, 84-87`

**Description**:
Manual JSON extraction using string search for `{` and `}`. Will break if LLM output format changes.

**Example**:
```python
start_idx = response_text.find("{")
end_idx = response_text.rfind("}") + 1
grading_result = json.loads(response_text[start_idx:end_idx])
```

**Fix Plan**:
Use ADK's `response_mime_type="application/json"` and proper output parsing.

---

### BUG-007: Database Design Issues
**Severity**: Medium
**Status**: Known (Pre-refactor)
**Location**: `feedback_agent/database.py`

**Issues**:
1. Storing JSON as TEXT (weaknesses, recommendations)
2. No schema versioning
3. No migration system
4. No foreign key constraints enabled

**Fix Plan**:
Acceptable for capstone, but document as technical debt. May enhance in Phase 3.

---

## Low Priority Issues 🟢

### BUG-008: Missing Type Validation
**Severity**: Low
**Status**: Known (Pre-refactor)
**Location**: `feedback_agent/database.py`

**Description**:
Database operations don't validate input types. Could lead to SQL errors.

**Fix Plan**:
Add Pydantic models in Phase 2 for validation.

---

### BUG-009: No Logging Configuration
**Severity**: Low
**Status**: Known (Pre-refactor)

**Description**:
Using basic Python logging without configuration. Log levels, formats, and outputs are defaults.

**Fix Plan**:
Will be addressed in Phase 6 with LoggingPlugin.

---

## Resolved Bugs ✅

### BUG-001: Missing `run_agent_multimodal()` Function ✅
**Resolution Date**: 2025-11-24
**Fixed In**: Phase 4

**Solution**:
Completely refactored `feedback_agent/agents/image_processing_agent.py` to use direct Gemini API calls instead of non-existent wrapper function.

**Changes**:
- Removed broken `run_agent_multimodal()` call
- Implemented direct `CustomGemini.generate_content()` calls
- Added proper multimodal Content with image blobs
- Used `response_mime_type='application/json'` for structured output
- All 3 test images successfully processed

**Status**: ✅ Verified working with test suite

---

### BUG-010: Incorrect `@cached_property` on `generate_content()` ✅
**Severity**: Critical (discovered during Phase 4)
**Resolution Date**: 2025-11-24
**Location**: `feedback_agent/custom_llm.py:31`

**Description**:
The `generate_content()` method was decorated with `@cached_property`, which is incorrect because:
1. `@cached_property` is for property getters, not methods with parameters
2. This caused the method to fail when called with arguments
3. Error: "CustomGemini.generate_content() missing 2 required positional arguments: 'model' and 'contents'"

**Root Cause**:
```python
# INCORRECT:
@cached_property
async def generate_content(self, model, contents, config=None):
```

**Solution**:
Removed `@cached_property` decorator to make it a proper async method:
```python
# CORRECT:
async def generate_content(self, model, contents, config=None):
    """Generate content using the Gemini API directly."""
```

**Status**: ✅ Fixed and verified

---

## Bug Tracking Guidelines

**Severity Levels**:
- 🔴 **Critical**: System is broken or data loss possible
- 🟡 **High**: Feature doesn't work or major functionality issue
- 🟠 **Medium**: Inconvenience or suboptimal behavior
- 🟢 **Low**: Minor issue or technical debt

**Status Values**:
- **Known**: Identified but not yet being fixed
- **In Progress**: Currently being worked on
- **Testing**: Fix implemented, needs verification
- **Resolved**: Fixed and verified

---

## Notes

When adding bugs:
1. Assign sequential BUG-XXX number
2. Include file location and line numbers
3. Provide code examples where relevant
4. Link to fix plan phase if applicable
5. Update status as work progresses

---

## Known Limitations ⚠️

### LIMIT-001: Gemini API Free Tier Rate Limits
**Severity**: Medium
**Status**: Known Limitation
**Location**: All agent processing (evaluation runs)
**Date Identified**: 2025-11-24

**Description**:
Gemini API free tier has strict rate limits that prevent running comprehensive evaluation suites:
- gemini-2.5-pro: 2 requests/minute (too restrictive for multi-agent pipeline)
- gemini-2.0-flash-exp: 15 requests/minute (better but still limited)
- Both models: Daily/hourly quotas that can be exhausted during testing

Each exam processing requires 3 API calls (grading, analysis, recommendations), so with 8 test cases:
- Total API calls needed: 24 calls
- Time required at 2 req/min: ~12 minutes (gemini-2.5-pro)
- Time required at 15 req/min: ~1.6 minutes (gemini-2.0-flash-exp)

**Impact**:
- Cannot run full evaluation suite in single session
- Need to wait for quota reset (typically 1 minute for per-minute limits)
- May hit daily quotas after multiple test runs

**Workarounds**:
1. Wait for quota reset (1 minute for per-minute limits, 24 hours for daily limits)
2. Use paid API key with higher rate limits
3. Run tests in smaller batches with delays between batches
4. Use gemini-2.0-flash-exp which has higher rate limits

**Solution**:
For production use:
- Upgrade to paid API tier
- Implement proper rate limiting and retry logic in evaluation runner
- Consider caching evaluation results to avoid re-running tests

**Current Status**:
Evaluation framework is fully functional and integrated with agent. Blocked only by API quota. Framework will generate complete results once quotas reset or paid API key is used.

