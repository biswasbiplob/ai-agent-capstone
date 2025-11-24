from google.adk.agents.llm_agent import Agent
from google.genai import types
from typing import Dict, Any
import json
import logging

# Configure logging
logger = logging.getLogger(__name__)

class ImageProcessingAgent:
    def __init__(self, model: str = 'gemini-2.5-pro'):
        self.agent = Agent(
            model=model,
            name='image_processing_agent',
            description='An agent that extracts text and answer keys from exam images.',
            instruction='''
            You are an expert OCR and document analysis AI.
            Your task is to extract the content of an exam from an image.
            
            Input will be:
            1. An image of an exam.
            
            Output must be a JSON object with the following structure:
            {
                "subject": <str> (e.g., "Math", "Biology"),
                "exam_content": <str> (The full text of the questions and student answers, verbatim),
                "answer_key": <str> (The answer key or rubric inferred from markings, or "Not found" if not present)
            }
            
            If the subject is not explicitly stated, infer it from the content.
            If the answer key is not visible (e.g., no checkmarks or corrections), set "answer_key" to "Not found".
            ''',
        )
        self.agent.generate_content_config = types.GenerateContentConfig(response_mime_type='application/json')

    def process_image(self, image_path: str = None, image_bytes: bytes = None) -> Dict[str, Any]:
        logger.info("ImageProcessingAgent.process_image called.")
        
        prompt = "Please extract the exam content and answer key from this image."
        
        # Construct the content part with the image
        # Note: The actual image handling depends on how ADK/Gemini accepts images.
        # Assuming we can pass the image as a part in the prompt or context.
        # For adk web, the image might be in the session history or passed differently.
        # However, since we are refactoring to a sub-agent flow, we need to ensure this agent gets the image.
        
        # If running via adk web, the user input (with image) might have already been processed by the root agent
        # and passed down. But here we want a dedicated agent.
        
        # In the context of `run_agent` utility, we need to support multimodal input.
        # The current `run_agent` takes a string prompt. We might need to update it or use a different method.
        
        # For now, let's assume the `root_agent` passes the image description or we rely on the session context 
        # if the image was uploaded in the same session. 
        # BUT, to be robust, this agent should ideally receive the image data.
        
        # Given the constraints and the previous "adk web" context, the image is likely in the session.
        # If we are chaining agents, we might need to pass the image explicitly.
        
        # Let's stick to the instruction-based extraction for now, assuming the image is available in the context 
        # or passed as a part.
        
        # If we are using `run_agent` from utils, it creates a NEW session. This means the image from the 
        # root agent's session won't be there unless we pass it.
        # This is a critical architectural detail.
        
        # For the purpose of this refactor, let's assume we will pass the image content if available.
        # Since `run_agent` in `utils.py` takes a string prompt, we might need to enhance it to take parts.
        
        from feedback_agent.utils import run_agent_multimodal
        
        # We need to implement run_agent_multimodal in utils.py
        response_text = run_agent_multimodal(self.agent, prompt, image_path=image_path, image_bytes=image_bytes)
        
        logger.debug(f"ImageProcessingAgent raw response: {response_text[:200]}...")
        
        try:
            start = response_text.find('{')
            end = response_text.rfind('}') + 1
            if start != -1 and end != -1:
                json_str = response_text[start:end]
                return json.loads(json_str)
            else:
                raise ValueError("No JSON found in response")
        except Exception as e:
            logger.error(f"Error parsing image processing response: {e}")
            return {
                "subject": "Unknown",
                "exam_content": "",
                "answer_key": "Not found"
            }
