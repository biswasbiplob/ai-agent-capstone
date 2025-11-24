# ADR-004: Configurable Model Name via Environment Variable

**Status**: Accepted  
**Date**: 2025-11-24  
**Context**: Phase 5 - Evaluation Framework

## Context and Problem Statement

During evaluation framework testing, we encountered severe API rate limiting issues:
- gemini-2.5-pro: Only 2 requests/minute (hardcoded in all agents)
- Each exam requires 3 API calls (grading, analysis, recommendations)
- 8 test cases = 24 API calls = 12+ minutes with 2 req/min
- Different models have different rate limits and quality tradeoffs
- Need flexibility to switch models without code changes

## Decision

Make model name configurable via environment variable:
1. Add `MODEL_NAME` to `feedback_agent/.env`
2. All agents read from environment on initialization
3. Raise explicit error if MODEL_NAME not set (no defaults)
4. Document available models and their rate limits

## Implementation

### Changes Made

1. **Environment File** (`feedback_agent/.env`):
```bash
MODEL_NAME="gemini-1.5-flash"
```

2. **All Agent Files** (grading, analysis, recommendation, image processing):
```python
import os
from dotenv import load_dotenv

load_dotenv()

def __init__(self, model: str = None):
    if model is None:
        model = os.getenv('MODEL_NAME')
        if not model:
            raise ValueError(
                "MODEL_NAME must be set in .env file. "
                "Add MODEL_NAME=<model-name> to feedback_agent/.env"
            )
```

3. **Documentation Updated**:
   - README.md: Added model selection guide
   - .env: Added detailed comments about model options

## Available Models

| Model | Rate Limit | Quality | Best For |
|-------|-----------|---------|----------|
| gemini-1.5-flash | 15 req/min | Good | Evaluation runs, development |
| gemini-1.5-pro | 2 req/min | Better | Production, quality critical |
| gemini-2.0-flash-exp | 15 req/min | Good | Experimental features |
| gemini-2.5-pro | 2 req/min | Best | Highest quality needs |

## Consequences

### Positive
- Easy model switching for rate limit management
- No code changes required to try different models
- Explicit error if configuration missing
- Clear documentation of tradeoffs
- Evaluation runs 6x faster with gemini-1.5-flash

### Negative
- Requires environment variable setup
- One more configuration step for new users
- Error if .env file missing or misconfigured

### Neutral
- All agents use same model (consistent behavior)
- Can still override per-agent if needed via constructor

## References

- Gemini API Rate Limits: https://ai.google.dev/gemini-api/docs/rate-limits
- Phase 5 Evaluation Framework (PROGRESS.md)
- BUGS.md: LIMIT-001 (API Rate Limiting)
