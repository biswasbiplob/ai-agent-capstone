import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv("feedback_agent/.env")

import json
import logging
from feedback_agent.agent import feedback_system

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def run_evals(dataset_path: str):
    logger.info(f"Running evaluations from {dataset_path}...")
    
    with open(dataset_path, 'r') as f:
        lines = f.readlines()
        
    results = []
    
    for i, line in enumerate(lines):
        data = json.loads(line)
        input_text = data['input']['text']
        expected = data['expected_output']
        
        logger.info(f"Processing Item {i+1}: {input_text[:50]}...")
        
        # Parse input to extract fields (simple parsing for this eval script)
        # Expected format: "Grade this exam for student <Name>. Subject: <Subject>. Exam: <Content>. Key: <Key>."
        try:
            student_name = input_text.split("student ")[1].split(".")[0]
            subject = input_text.split("Subject: ")[1].split(".")[0]
            exam_content = input_text.split("Exam: ")[1].split(" Key: ")[0]
            answer_key = input_text.split("Key: ")[1].strip(".")
            
            # Register student
            student_id = feedback_system.register_student(student_name)
            
            # Process exam
            result = feedback_system.process_exam(
                student_id=student_id,
                subject=subject,
                exam_content=exam_content,
                answer_key=answer_key
            )
            
            # Compare with expected
            total_score = result['grading'].get('total_score')
            expected_score = expected['grading']['total_score']
            
            if total_score == expected_score:
                logger.info(f"Item {i+1}: PASSED (Score: {total_score}/{expected_score})")
                results.append({"status": "PASSED", "item": i+1})
            else:
                logger.error(f"Item {i+1}: FAILED (Score: {total_score}, Expected: {expected_score})")
                results.append({"status": "FAILED", "item": i+1})
                
            # Sleep to avoid hitting rate limits (Free Tier: 15 RPM)
            import time
            logger.info("Sleeping for 30 seconds to respect rate limits...")
            time.sleep(30)
                
        except Exception as e:
            import traceback
            logger.error(f"Item {i+1}: ERROR - {repr(e)}")
            traceback.print_exc()
            results.append({"status": "ERROR", "item": i+1})
            
    logger.info("Evaluation Complete.")
    logger.info(f"Results: {results}")

if __name__ == "__main__":
    run_evals("evals/eval_dataset.jsonl")
