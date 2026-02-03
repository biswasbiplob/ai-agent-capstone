"""
ImageProcessingAgent using direct Gemini API calls with multimodal support.

This agent extracts exam content and answer keys from images using Gemini's
vision capabilities.

Key improvements over the original:
- Uses direct model API for simple stateless image processing
- Properly handles multimodal input (images)
- No dependency on custom run_agent_multimodal function
- Async/await patterns
- Structured JSON output
"""

import json
import logging
import os
from typing import Dict, Any, Optional
from pathlib import Path
from dotenv import load_dotenv

from google.genai import types
from feedback_agent.custom_llm import CustomGemini
from feedback_agent.json_utils import parse_json_payload

logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()


class ImageProcessingAgent:
    """
    Image processing agent using direct Gemini model calls.

    This agent:
    - Accepts image files (path or bytes)
    - Uses Gemini's multimodal capabilities
    - Extracts exam content and answer keys
    - Returns structured JSON output
    """

    INSTRUCTION = """
You are an expert OCR and document analysis AI.
Your task is to extract the content of an exam from an image.

Analyze the image and extract:
1. The subject of the exam (infer if not explicitly stated)
2. All questions and student answers (verbatim text)
3. Any answer key or rubric visible (markings, corrections, etc.)

Output must be a JSON object with the following structure:
{
    "subject": <str> (e.g., "Mathematics", "Physics", "Biology"),
    "exam_content": <str> (Full text of questions and answers),
    "answer_key": <str> (Answer key/rubric, or "Not found" if not visible)
}

Be thorough in extracting all text from the image.
If the subject is not stated, infer it from the content.
If no answer key is visible, set "answer_key" to "Not found".
"""

    def __init__(self, model: Optional[str] = None):
        """
        Initialize the image processing agent.

        Args:
            model: Gemini model to use (must support vision). If None, reads from MODEL_NAME env variable.

        Raises:
            ValueError: If model is None and MODEL_NAME is not set in .env
        """
        # Get model from environment or use provided value
        if model is None:
            model = os.getenv("MODEL_NAME")
            if not model:
                raise ValueError(
                    "MODEL_NAME must be set in .env file. "
                    "Add MODEL_NAME=<model-name> to feedback_agent/.env "
                    "(e.g., MODEL_NAME=gemini-1.5-flash)"
                )

        self.model_name = model
        self.model = CustomGemini(model=model)
        logger.info(f"ImageProcessingAgent initialized with model {model}")

    async def process_image(
        self,
        image_path: Optional[str] = None,
        image_bytes: Optional[bytes] = None,
        mime_type: str = "image/jpeg",
    ) -> Dict[str, Any]:
        """
        Process an exam image and extract content.

        Args:
            image_path: Path to image file
            image_bytes: Raw image bytes
            mime_type: MIME type of the image (default: image/jpeg)

        Returns:
            Dictionary with extracted exam content:
            {
                "subject": str,
                "exam_content": str,
                "answer_key": str
            }
        """
        logger.info("Processing exam image...")

        # Validate input
        if image_path is None and image_bytes is None:
            logger.error("No image provided (need either image_path or image_bytes)")
            return {
                "subject": "Unknown",
                "exam_content": "",
                "answer_key": "Not found",
                "error": "No image provided",
            }

        # Read image if path provided
        if image_path and image_bytes is None:
            try:
                with open(image_path, "rb") as f:
                    image_bytes = f.read()
                logger.info(f"Read image from {image_path}")
            except Exception as e:
                logger.error(f"Error reading image file: {e}")
                return {
                    "subject": "Unknown",
                    "exam_content": "",
                    "answer_key": "Not found",
                    "error": f"Failed to read image: {e}",
                }

        # Detect MIME type from path if provided
        if image_path:
            suffix = Path(image_path).suffix.lower()
            mime_map = {
                ".jpg": "image/jpeg",
                ".jpeg": "image/jpeg",
                ".png": "image/png",
                ".gif": "image/gif",
                ".webp": "image/webp",
            }
            mime_type = mime_map.get(suffix, mime_type)

        # Create multimodal content with instruction and image
        parts = [
            types.Part(text=self.INSTRUCTION),
            types.Part(text="Extract the exam content from this image."),
            types.Part(inline_data=types.Blob(data=image_bytes, mime_type=mime_type)),
        ]

        # Call model directly with multimodal input
        try:
            response_schema = types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "subject": types.Schema(type=types.Type.STRING),
                    "exam_content": types.Schema(type=types.Type.STRING),
                    "answer_key": types.Schema(type=types.Type.STRING),
                },
                required=["subject", "exam_content", "answer_key"],
            )

            response = await self.model.generate_content(
                model=self.model_name,
                contents=[types.Content(role="user", parts=parts)],
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=response_schema,
                ),
            )

            # Extract response text
            response_text = ""
            if response.candidates:
                for candidate in response.candidates:
                    if candidate.content and candidate.content.parts:
                        for part in candidate.content.parts:
                            if part.text:
                                response_text += part.text

            logger.debug(f"Image processing response length: {len(response_text)}")

            # Parse JSON response
            if response_text:
                result = parse_json_payload(response_text, "image_processing")
                if result:
                    logger.info("Successfully extracted exam content from image")
                    return result
                logger.warning("Failed to parse JSON from image processing response")
                return {
                    "subject": "Unknown",
                    "exam_content": response_text,
                    "answer_key": "Not found",
                    "error": "Failed to parse JSON response",
                }
            else:
                logger.warning("Empty response from image processing")
                return {
                    "subject": "Unknown",
                    "exam_content": "",
                    "answer_key": "Not found",
                    "error": "Empty response from agent",
                }

        except json.JSONDecodeError as e:
            logger.error(f"Error parsing image processing JSON: {e}")
            logger.debug(f"Raw response: {response_text[:500]}")
            return {
                "subject": "Unknown",
                "exam_content": response_text if response_text else "",
                "answer_key": "Not found",
                "error": "Failed to parse JSON response",
            }

        except Exception as e:
            logger.error(f"Error processing image: {e}", exc_info=True)
            return {
                "subject": "Unknown",
                "exam_content": "",
                "answer_key": "Not found",
                "error": f"Processing failed: {e}",
            }


# Create global instance for backward compatibility
image_processor = ImageProcessingAgent()
