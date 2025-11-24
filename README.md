# AI Agent Capstone: Student-Teacher Exam Correction System

A sophisticated AI agent system built with Google's Agent Development Kit (ADK) that automates exam grading, identifies student weaknesses, and creates personalized learning plans. This project demonstrates best practices from the Kaggle AI Agents course.

## <� Project Overview

This system provides:
- **Automated Grading**: Evaluates student exams against answer keys
- **Weakness Analysis**: Identifies recurring learning gaps
- **Personalized Recommendations**: Creates targeted study plans
- **Role-Based Access**: Students see their own data, teachers see all students
- **Multimodal Support**: Processes both text and image-based exams

## <� Architecture

Built using Google ADK best practices:
- **Runner Pattern**: Proper session management with DatabaseSessionService
- **State Management**: Agent pipeline with output_key pattern
- **Authentication**: Session-based auth with User and UserRole models
- **Authorization Tools**: Role-based access control following ADK patterns
- **Multimodal Processing**: Direct Gemini API calls for vision capabilities

### Agent Pipeline

```
ExamInput � GradingAgent � AnalysisAgent � RecommendationAgent � Database
              (scores)        (weaknesses)    (learning plan)
```

## =� Prerequisites

- Python 3.13+
- uv (dependency manager)
- Google API Key (Gemini)

## =� Setup

1. **Clone and navigate to project**:
```bash
cd ai_agent_capstone
```

2. **Create virtual environment and install dependencies**:
```bash
uv venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
uv pip install -e .
```

3. **Configure environment variables**:
```bash
# Create .env file in feedback_agent/ directory
cat > feedback_agent/.env << 'EOF'
GOOGLE_GENAI_USE_VERTEXAI=0
GOOGLE_GEMINI_BASE_URL="https://generativelanguage.googleapis.com"
GOOGLE_API_KEY=your_api_key_here

# Model Configuration (REQUIRED)
# Available models: gemini-1.5-flash, gemini-1.5-pro, gemini-2.0-flash-exp, gemini-2.5-pro
# Recommendation: Use gemini-1.5-flash for evaluation runs (15 req/min rate limit)
MODEL_NAME="gemini-1.5-flash"
EOF
```

**Model Selection Guide**:
- `gemini-1.5-flash`: Best for evaluation runs (15 req/min, fast, good quality)
- `gemini-1.5-pro`: Higher quality but restricted (2 req/min)
- `gemini-2.0-flash-exp`: Experimental, similar to 1.5-flash
- `gemini-2.5-pro`: Best quality but very restricted (2 req/min)

4. **Verify installation**:
```bash
python -c "import google.adk; print('ADK installed successfully')"
```

##  Completed Phases

### Phase 1: Core Architecture Refactor 
**Status**: Production-ready
**Key Achievement**: Migrated from custom runner to ADK Runner pattern

**What It Does**:
- Proper session management with DatabaseSessionService
- Agent state flow using output_key pattern
- EventsCompactionConfig for context management
- Async callback functions

**Test It**:
```bash
python tests/test_refactored_agent.py
```

**Expected Output**: Agent pipeline processes exam through grading � analysis � recommendations

---

### Phase 2: Role-Based Access Control 
**Status**: All tests passing (6/6)
**Key Achievement**: Implemented authentication and authorization system

**What It Does**:
- User management with STUDENT, TEACHER, ADMIN roles
- Session-based authentication
- Authorization tools that check permissions:
  - `get_my_performance()` - Students view their own data
  - `get_student_performance()` - Teachers view any student
  - `get_class_statistics()` - Teachers view class-wide stats
  - `list_my_students()` - Teachers list all students

**Test It**:
```bash
python tests/test_authorization.py
```

**Expected Output**:
```
 TEST PASSED: Student can view own data
 TEST PASSED: Student blocked from accessing other student's data
 TEST PASSED: Teacher can view student data
 TEST PASSED: Teacher can list students
 TEST PASSED: Teacher can view class statistics
 TEST PASSED: Student blocked from viewing class statistics
```

---

### Phase 4: Image Processing 
**Status**: All tests passing with 3 sample images
**Key Achievement**: Fixed broken multimodal support

**What It Does**:
- Processes exam images using Gemini vision (gemini-2.5-pro)
- Extracts subject, exam content, and answer keys
- Auto-detects MIME types (PNG, JPEG, GIF, WebP)
- Returns structured JSON output

**Test It**:
```bash
python tests/test_image_processing.py
```

**Expected Output**:
```
TEST 1: Processing Mathematics exam
  Subject: Mathematics
  Exam Content: [Extracted questions and answers]
  Answer Key: [Extracted with corrections]
 Image processed successfully!

TEST 2: Processing World History exam
  Subject: World History
  Exam Content: [Extracted quiz content]
  Answer Key: [Extracted markings]
 Image processed successfully!
```

**Sample Images**: Located in `feedback_agent/input_images/`

---

### Phase 5: Evaluation Framework ✅
**Status**: Complete - Framework operational, performance needs model upgrade
**Key Achievement**: Production-ready evaluation system with comprehensive metrics

**What It Does**:
- Evaluates agent performance across 8 test cases
- Measures grading accuracy (comparing scores to ground truth)
- Assesses analysis quality (weakness identification)
- Evaluates recommendation relevance (learning plan alignment)
- Generates detailed reports with pass/fail status

**Test It**:
```bash
python evals/run_evaluation.py
```

**Current Results**:
- Pass Rate: 25% (2/8 tests)
- Grading Accuracy: 0.550
- Analysis Quality: 0.233 (needs improvement)
- Recommendation Relevance: 0.892

**Note**: Performance limited by gemini-2.0-flash model capabilities. Upgrade to gemini-1.5-pro recommended.

---

### Phase 6: Observability ✅
**Status**: All tests passing (3/3)
**Key Achievement**: Production-ready monitoring with custom metrics plugin

**What It Does**:
- **Custom ExamMetricsPlugin**: Tracks exam processing metrics
  - Processing duration (total and per-agent)
  - Grading scores and distributions
  - Weakness identification counts
  - Success/failure rates
  - Writes metrics to JSONL file
- **ADK LoggingPlugin**: Built-in agent lifecycle logging
  - LLM request/response tracking
  - Token usage monitoring
  - Color-coded console output
- **Structured Logging**: File and console logging with detailed context

**Test It**:
```bash
python tests/test_observability.py
```

**Expected Output**:
```
============================================================
📊 EXAM PROCESSING METRICS SUMMARY
============================================================
Total Exams Processed: 3
Success Rate: 100.0%
Total Processing Time: 14.98s
Average Processing Time: 4.99s

Score Statistics:
  Average Score: 77.8%
  Min Score: 66.7%
  Max Score: 100.0%
============================================================
```

**Usage**:
```python
# Initialize system with metrics enabled
system = FeedbackSystemRefactored(
    enable_metrics=True,
    metrics_file="exam_metrics.jsonl"
)

# Process exams (metrics tracked automatically)
result = await system.process_exam(...)

# Get summary statistics
summary = system.get_metrics_summary()
# Returns: {"total_exams_processed": 3, "avg_processing_time": 4.99, ...}

# Or print human-readable summary
system.print_metrics_summary()
```

**Metrics Output**: See `exam_metrics.jsonl` for detailed per-exam metrics in JSON Lines format.

---

## >� Running Tests

### Run All Tests
```bash
# Run all tests in tests/ folder
python -m pytest tests/ -v
```

### Run Specific Tests
```bash
# Test authorization
python tests/test_authorization.py

# Test image processing
python tests/test_image_processing.py

# Test refactored agent
python tests/test_refactored_agent.py
```

### Integration Test
```bash
python tests/test_integration.py
```

## =� Current Capabilities

###  Working Features
- [x] Automated exam grading with detailed feedback
- [x] Student weakness identification (concept-based analysis)
- [x] Personalized study recommendations
- [x] Role-based access control (students vs teachers)
- [x] Image-based exam processing (multimodal support)
- [x] Session management with database persistence
- [x] Structured JSON outputs
- [x] **Evaluation framework** - Measures grading accuracy, analysis quality, recommendation relevance
- [x] **Observability system** - Custom metrics plugin + LoggingPlugin for monitoring
- [x] **Structured logging** - File and console output with detailed context

### =� In Development
- [ ] Memory service for cross-session tracking (Phase 3 - NEXT)
- [ ] Comprehensive documentation and demo (Phase 7)

### =� Known Limitations
- Evaluation pass rate: 25% (model upgrade needed for better performance)
- Analysis quality: 0.233 (gemini-2.0-flash insufficient for complex concept extraction)

## =� Project Structure

```
ai_agent_capstone/
   feedback_agent/
      agents/
         grading_agent.py          # Grades exams
         analysis_agent.py         # Identifies weaknesses
         recommendation_agent.py   # Creates study plans
         image_processing_agent.py # Processes exam images 
      agent_refactored.py          # Main refactored system 
      auth.py                       # Authentication system 
      authorization.py              # Authorization tools 
      database.py                   # SQLite database interface
      custom_llm.py                 # Custom Gemini wrapper
   tests/
      test_authorization.py         # Auth tests (6/6 passing) 
      test_image_processing.py      # Image tests (3/3 passing) 
      test_refactored_agent.py      # Agent pipeline tests 
   .adr/                             # Architecture Decision Records
   PROGRESS.md                       # Detailed progress tracking
   BUGS.md                           # Bug tracking and resolutions
   EVALUATION_SUMMARY.md             # Initial evaluation report
   README.md                         # This file
```

## =' Configuration

### Database Configuration
- **Development**: `students.db` (SQLite)
- **Session Storage**: `feedback_sessions.db` (DatabaseSessionService)
- **Test Databases**: `test_*.db` (automatically cleaned)

### Model Configuration
- **Default Model**: `gemini-2.5-pro`
- **Vision Model**: `gemini-2.5-pro` (supports multimodal)
- **API**: Google Gemini via google-genai SDK

## =� Documentation

### Architecture Decision Records (ADRs)
- [ADR-001](./adr/001-migrate-to-adk-runner-pattern.md): Migration to ADK Runner pattern
- [ADR-002](./adr/002-agent-state-flow-pattern.md): Agent state flow using output_key

### Progress Tracking
- [PROGRESS.md](./PROGRESS.md): Detailed phase-by-phase progress
- [BUGS.md](./BUGS.md): Known issues and resolutions

## <� Course Alignment

This project demonstrates best practices from the Kaggle AI Agents course:

| Course Day | Concept | Implementation |
|------------|---------|----------------|
| Day 1 | Agent Basics | Sequential agent pipeline |
| Day 2a | Tools | Authorization tools with ToolContext |
| Day 3a | Runner & Sessions | DatabaseSessionService, proper state management |
| Day 5a | State Management | output_key pattern between agents |
| Multimodal | Vision APIs | Image processing with Gemini vision |

## =� Next Steps

**Phase 5: Evaluation Framework (IN PROGRESS)**
- Create evaluation dataset with ground truth
- Implement grading accuracy metrics
- Measure analysis quality
- Benchmark recommendation relevance

## > Contributing

This is a capstone project for educational purposes. For issues or suggestions:
1. Check [BUGS.md](./BUGS.md) for known issues
2. Review [PROGRESS.md](./PROGRESS.md) for current status
3. See ADRs for architectural decisions

## =� License

This project is for educational purposes as part of the Kaggle AI Agents course capstone.

## =O Acknowledgments

- Kaggle AI Agents Course instructors
- Google Agent Development Kit (ADK) team
- Google Gemini API

---

**Last Updated**: 2024-11-24
**Phase**: 5 (Evaluation Framework - Starting)
**Tests Passing**: 9/9 


## Phase 5: Evaluation Framework (Complete - Needs Model Upgrade)

**Framework Status**: ✅ Complete and fully operational
**Performance Status**: ⚠️ Below target (25% pass rate vs 70% target)

### Completed Components
- 8 test cases covering grading accuracy, analysis quality, and recommendations
- Full metrics implementation (GradingAccuracyMetric, AnalysisQualityMetric, RecommendationRelevanceMetric)
- Async evaluation runner with results aggregation and JSON output
- Agent integration with proper data flow
- Identified and partially fixed critical architectural issue

### Key Findings
**Architectural Issue Identified**: AnalysisAgent was extracting question text instead of concepts, causing 0% topic coverage.

**Fix Applied**: Updated agent to receive exam_content and extract underlying concepts. Result: Topic coverage improved to 25% in some tests.

**Current Challenge**: gemini-2.0-flash model lacks reasoning capability for complex concept extraction. Recommendation: Upgrade to gemini-1.5-pro.

### Run Evaluations
```bash
python evals/run_evaluation.py
```

### Results Summary
- **Pass Rate**: 25% (2/8 tests)
- **Grading Accuracy**: 0.550
- **Analysis Quality**: 0.233 (needs improvement)
- **Recommendation Relevance**: 0.892

See EVALUATION_COMPARISON.md for detailed analysis and recommendations.

