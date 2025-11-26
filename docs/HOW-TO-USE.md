# AI Agent Capstone: Automated Exam Correction System

An AI-powered system that automatically grades exams, identifies learning gaps, and creates personalized study plans. Built with Google's Agent Development Kit (ADK).

## What It Does

```
Student submits exam → AI grades it → Identifies weaknesses → Creates personalized study plan
```

**Key Features**:
- ✅ Automated grading with detailed feedback
- ✅ Identifies recurring learning gaps across multiple exams
- ✅ Creates personalized study recommendations
- ✅ Role-based access (students see their data, teachers see all students)
- ✅ Processes both text and image-based exams
- ✅ Tracks learning progress over time

## Quick Start

### Prerequisites
- Python 3.13+
- [uv](https://github.com/astral-sh/uv) (Python package manager)
- Google API Key ([Get one here](https://aistudio.google.com/apikey))

### Installation

1. **Clone and setup**:
```bash
cd ai_agent_capstone
uv sync
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

2. **Configure API Key**:
```bash
# Create .env file in feedback_agent/ directory
cat > feedback_agent/.env << 'EOF'
GOOGLE_GENAI_USE_VERTEXAI=0
GOOGLE_GEMINI_BASE_URL="https://generativelanguage.googleapis.com"
GOOGLE_API_KEY=your_api_key_here
MODEL_NAME="gemini-1.5-flash"
EOF
```

**Important**: Replace `your_api_key_here` with your actual Google API key.

3. **Verify installation**:
```bash
python -c "import google.adk; print('✅ ADK installed successfully')"
```

### First Run

Try the interactive demo:
```bash
python demo.py
```

Or use the conversational interface:
```bash
cd feedback_agent
adk web
```

Then open `http://localhost:8000` in your browser.

**Demo Options** - Select from 5 demos:
1. Basic Exam Processing - See how grading works
2. Role-Based Access Control - Student vs Teacher permissions
3. Image Processing - Upload exam photos
4. Metrics Tracking - Monitor system performance
5. Complete Workflow - End-to-end demo

## Usage Examples

### Basic Exam Processing

```python
import asyncio
from feedback_agent.agent import FeedbackSystem

async def grade_exam():
    # Initialize system
    system = FeedbackSystem()

    # Register student
    student_id = system.register_student("John Doe")

    # Process exam
    result = await system.process_exam(
        student_id=student_id,
        exam_content="1. What is 5 + 3? Answer: 8",
        answer_key="1. 8",
        subject="Mathematics",
        user_id="teacher_001"
    )

    # View results
    print(f"Score: {result['total_score']}/{result['max_score']}")
    print(f"Weaknesses: {result['weaknesses']}")
    print(f"Recommendations: {result['recommendations']}")

asyncio.run(grade_exam())
```

### Track Student Progress

```python
# Get recurring weaknesses across multiple exams
weaknesses = system.get_student_recurring_weaknesses(student_id)

# Calculate learning velocity
velocity = system.get_student_learning_velocity(student_id)
print(f"Improvement rate: {velocity['improvement_rate']:.2f}% per exam")

# Get personalized recommendations
recommendations = system.get_student_review_recommendations(student_id)
```

### Process Image-Based Exams

```python
from feedback_agent.agents.image_processing_agent import ImageProcessingAgentRefactored

agent = ImageProcessingAgentRefactored()
result = await agent.process_image(image_path="path/to/exam.png")

# Extract data from image
print(f"Subject: {result['subject']}")
print(f"Questions: {result['exam_content']}")
print(f"Answers: {result['answer_key']}")
```

## Testing

Run all tests to verify everything works:
```bash
# Run all tests
python -m pytest tests/ -v

# Or test specific components
python tests/test_refactored_agent.py    # Basic agent pipeline
python tests/test_authorization.py       # Role-based access
python tests/test_image_processing.py    # Image processing
python tests/test_memory.py              # Cross-session tracking
python tests/test_observability.py       # Metrics tracking
```

## Configuration

### Model Selection

Choose the right model for your use case in `feedback_agent/.env`:

| Model | Rate Limit | Best For |
|-------|-----------|----------|
| `gemini-1.5-flash` | 15 req/min | **Recommended** - Fast, good quality |
| `gemini-1.5-pro` | 2 req/min | Higher quality, slower |
| `gemini-2.0-flash-exp` | 15 req/min | Experimental features |
| `gemini-2.5-pro` | 2 req/min | Best quality, very restricted |

**For batch operations** (evaluations, multiple exams), use `gemini-1.5-flash`.

### Enable Metrics Tracking

```python
system = FeedbackSystem(
    enable_metrics=True,
    metrics_file="exam_metrics.jsonl"
)

# View metrics
system.print_metrics_summary()
```

## Project Structure

```
ai_agent_capstone/
├── feedback_agent/
│   ├── agents/                 # Agent implementations
│   │   ├── grading_agent.py
│   │   ├── analysis_agent.py
│   │   ├── recommendation_agent.py
│   │   └── image_processing_agent.py
│   ├── agent.py                # Main system (FeedbackSystem, pipeline, root_agent)
│   ├── conversational_agent.py # ADK Web UI conversational agent
│   ├── conversational_tools.py # 8 tools for conversational interface
│   ├── auth.py                 # Authentication
│   ├── authorization.py        # Access control
│   ├── database.py             # Data persistence
│   ├── memory.py               # Cross-session tracking
│   ├── plugins.py              # Metrics & logging
│   └── custom_llm.py           # Custom Gemini wrapper
├── tests/                      # Test suites
├── evals/                      # Evaluation framework
├── docs/                       # Documentation
│   ├── ARCHITECTURE.md
│   ├── CAPSTONE_REPORT.md
│   └── HOW-TO-USE.md
├── .adr/                       # Architecture Decision Records
├── demo.py                     # Interactive demo
└── README.md                   # Project overview
```

## Features Deep Dive

### 1. Automated Grading
- Compares student answers against answer keys
- Provides detailed feedback on mistakes
- Supports partial credit

### 2. Weakness Analysis
- Identifies specific topics where student struggles
- Tracks severity (low, medium, high)
- Detects recurring patterns across exams

### 3. Personalized Recommendations
- Creates targeted study plans
- Prioritizes based on weakness severity and frequency
- Includes time estimates for each learning objective

### 4. Cross-Session Memory
- Tracks student progress over time
- Calculates learning velocity and improvement rates
- Identifies subjects mastered vs struggling

### 5. Role-Based Access Control
- **Students**: View only their own data
- **Teachers**: View all students, class statistics
- **Admins**: Full system access

### 6. Multimodal Support
- Processes text-based exams
- Extracts content from images (PNG, JPEG, GIF, WebP)
- Auto-detects exam structure

### 7. Observability
- Custom metrics plugin for exam processing
- Token usage tracking
- Performance monitoring
- Structured logging

### 8. Conversational Interface (ADK Web UI)
- Natural language interaction via `adk web`
- Role-based authentication (teacher/student)
- 8 tools for complete exam processing workflow
- Image upload support (drag & drop or URLs)

## Using the Conversational Interface

The conversational interface provides a user-friendly way to interact with LearnPath Agent through natural language.

### Starting the Interface

```bash
cd feedback_agent
adk web
```

Open `http://localhost:8000` in your browser.

### Authentication Flow

At the start of each conversation, identify yourself:

```
User: Hi, I'm Ms. Johnson, a teacher
Agent: Welcome, Ms. Johnson! As a teacher, you can:
       - Grade exams from images or text
       - View any student's results
       - See class-wide analytics
       What would you like to do?
```

### Teacher Capabilities

| Action | How to Request |
|--------|----------------|
| Grade image exam | Upload image + "Grade this for [student name]" |
| Grade text exam | Provide questions, answers, and answer key |
| View student results | "Show me [student name]'s results" |
| Class analytics | "Show me class statistics" |
| List students | "List all students" |

### Student Capabilities

| Action | How to Request |
|--------|----------------|
| View own results | "Show me my results" |
| Get recommendations | "What should I study?" |

### Uploading Exam Images

You can upload exam images in several ways:

1. **Drag & Drop**: Drag an image directly into the chat
2. **Paste URL**: Provide a public URL to an image
3. **File Path**: When running locally, provide a local file path

**Example:**
```
User: [uploads exam.png] Grade this math exam for Alice
Agent: I've processed the exam. Alice scored 8/10 (80%).
       Areas for improvement:
       - Quadratic Equations (medium)
       - Factorization (low)
```

## Documentation

- **[ARCHITECTURE.md](./docs/ARCHITECTURE.md)** - System design and architecture
- **[CAPSTONE_REPORT.md](./docs/CAPSTONE_REPORT.md)** - Project report
- **[.adr/](./.adr/)** - Architecture Decision Records

## How It Works

The system uses a hybrid multi-agent pipeline:

```
Input → GradingAgent → LoopAgent(Analysis + Validation) → ParallelAgent(3 Recommenders) → SynthesisAgent → Output
```

**Pipeline Stages:**
1. **GradingAgent**: Compares answers against answer key, calculates scores
2. **LoopAgent (Quality Assurance)**:
   - **AnalysisAgent**: Identifies conceptual weaknesses (not question text)
   - **ValidationAgent**: Ensures analysis quality, retries if needed (up to 5x)
3. **ParallelAgent (Recommendations)**: Runs 3 agents simultaneously:
   - **Study Materials Agent**: Curates learning resources
   - **Practice Problems Agent**: Generates targeted exercises
   - **Learning Strategy Agent**: Develops study techniques
4. **SynthesisAgent**: Combines parallel outputs into unified learning plan
5. **MemoryService**: Tracks patterns across multiple exams

Built using Google ADK best practices:
- Runner pattern for session management
- State flow with output_key pattern
- LoopAgent for quality assurance with validation
- ParallelAgent for efficient recommendation generation
- Custom plugins for observability

## Evaluation Results

Run the evaluation suite:
```bash
python evals/run_evaluation.py
```

**Current Performance**:
- Grading Accuracy: 55%
- Analysis Quality: 23% (needs improvement with better models)
- Recommendation Relevance: 89%

See [EVALUATION_SUMMARY.md](./docs/EVALUATION_SUMMARY.md) for detailed results.

## Troubleshooting

### Rate Limit Errors (429)
**Problem**: `RESOURCE_EXHAUSTED` errors

**Solution**: Switch to `gemini-1.5-flash` in `.env` file
```bash
MODEL_NAME="gemini-1.5-flash"
```

### Import Errors
**Problem**: `ModuleNotFoundError: No module named 'feedback_agent'`

**Solution**: Activate virtual environment and reinstall
```bash
source .venv/bin/activate
uv sync
```

### API Key Issues
**Problem**: `PERMISSION_DENIED` or `INVALID_ARGUMENT`

**Solution**:
1. Get API key from https://aistudio.google.com/apikey
2. Update `feedback_agent/.env` with correct key
3. Ensure no extra quotes or spaces

## Contributing

This is a capstone project for educational purposes. For detailed technical information:
1. See [ARCHITECTURE.md](./docs/ARCHITECTURE.md) for system design
2. Review [.adr/](./.adr/) for architectural decisions
3. Check [CAPSTONE_REPORT.md](./docs/CAPSTONE_REPORT.md) for project overview

## Course Alignment

Demonstrates best practices from Kaggle AI Agents course:

| Concept | Implementation |
|---------|----------------|
| Agent Basics | Hybrid pipeline: Sequential + Loop + Parallel agents |
| Tools | 8 conversational tools with ToolContext |
| Runner & Sessions | SessionService for state management |
| State Management | output_key pattern for agent communication |
| LoopAgent | Quality assurance with ValidationAgent (up to 5 retries) |
| ParallelAgent | 3 specialized recommendation agents running concurrently |
| Multimodal | Gemini vision for image processing (ADK Web UI upload) |
| Observability | Custom ExamMetricsPlugin + structured logging |

## License

Educational project for Kaggle AI Agents course capstone.

## Acknowledgments

- Kaggle AI Agents Course instructors
- Google Agent Development Kit (ADK) team
- Google Gemini API

