
import asyncio
import logging
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv("feedback_agent/.env")

from feedback_agent.agents.grading_agent import GradingAgent
from feedback_agent.utils import run_agent
from feedback_agent.custom_llm import CustomGemini

# Configure logging
logging.basicConfig(level=logging.INFO)

async def main():
    grading_agent = GradingAgent()
    
    # Input data as constructed in process_exam
    exam_content = "1. 2+2=? Answer: 4. 2. 3*3=? Answer: 9."
    answer_key = "1. 4, 2. 9."
    input_data = f"Exam Content: {exam_content}\nAnswer Key: {answer_key}"
    
    print(f"--- Input Data ---\n{input_data}\n------------------")
    
    # Run the agent directly
    print("Running GradingAgent...")
    
    # We need to mock the context/session behavior if run_agent relies on it, 
    # but run_agent handles it.
    # However, run_agent is synchronous wrapper.
    
    # We can use the synchronous run_agent from utils
    response = run_agent(grading_agent.agent, input_data)
    
    print(f"\n--- Agent Response ---\n{response}\n----------------------")

if __name__ == "__main__":
    # run_agent is synchronous, so we don't need asyncio.run for it, 
    # but let's just call it directly.
    # Wait, run_agent in utils.py is synchronous?
    # Let's check utils.py content.
    # It uses asyncio.run inside if needed? 
    # No, looking at previous view_file of utils.py, it seemed to define run_agent.
    # Let's just run it.
    
    grading_agent = GradingAgent()
    
    # Input data as constructed in process_exam
    exam_content = "1. 2+2=? Answer: 4. 2. 3*3=? Answer: 9."
    answer_key = "1. 4, 2. 9."
    input_data = f"Exam Content: {exam_content}\nAnswer Key: {answer_key}"
    
    print(f"--- Input Data ---\n{input_data}\n------------------")
    
    from feedback_agent.utils import run_agent
    response = run_agent(grading_agent.agent, input_data)
    
    print(f"\n--- Agent Response ---\n{response}\n----------------------")
