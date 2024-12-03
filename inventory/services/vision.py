"""
Vision service for interacting with Mistral's Vision AI.
Handles image processing and API communication for both single and multiple image analysis.
"""

import base64
import os
from mistralai import Mistral
from typing import List, Tuple, Optional
from django.core.files import File

class VisionService:
    """
    Service class for handling vision AI operations using Mistral's API.
    Supports both single image and multiple image analysis.
    """
    
    def __init__(self):
        """Initialize Mistral client with API configuration"""
        try:
            self.client = Mistral(api_key=os.getenv('MISTRAL_API_KEY'))
            #self.client = Mistral(api_key='dure')
            print(os.getenv('MISTRAL_API_KEY'))
            self.model = "pixtral-12b-2409"
        except KeyError:
            raise EnvironmentError("MISTRAL_API_KEY not found in environment variables")

    def encode_image(self, image_path: str) -> Optional[str]:
        """
        Convert an image file to base64 encoding.
        
        Args:
            image_path: Path to the image file
            
        Returns:
            str: Base64 encoded image string or None if encoding fails
        """
        try:
            with open(image_path, "rb") as image_file:
                return base64.b64encode(image_file.read()).decode('utf-8')
        except FileNotFoundError:
            print(f"Error: Image file not found at {image_path}")
            return None
        except Exception as e:
            print(f"Error encoding image: {e}")
            return None

    def analyze_images(self, image_paths: List[str], prompt: str) -> Optional[Tuple[str, List[str]]]:
        """
        Analyze one or multiple images using Mistral Vision API.
        
        Args:
            image_paths: List of paths to image files
            prompt: Text prompt for the vision model
            
        Returns:
            tuple: (AI response text, list of processed image paths) or None if processing fails
        """
        # Prepare image data for API
        images_data = []
        for path in image_paths[:3]:
            base64_image = self.encode_image(path)
            if base64_image:
                images_data.append({
                    "type": "image_url",
                    "image_url": f"data:image/jpeg;base64,{base64_image}"
                })

        if not images_data:
            print("No valid images to process")
            return None

        try:
            # Construct API request
            messages = [{
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    *images_data
                ]
            }]

            # Call Mistral API
            response = self.client.chat.complete(
                model=self.model,
                messages=messages
            )

            return response.choices[0].message.content, image_paths

        except Exception as e:
            print(f"Error calling Mistral API: {e}")
            return None

def handle_vision_query(instance, model_name: str, prompt: str) -> Optional[Tuple[str, List[str]]]:
    """
    Generic handler for vision queries from both Item and Attachment models.
    
    Args:
        instance: Django model instance (Item or Attachment)
        model_name: Name of the vision model to use
        prompt: Text prompt for analysis
        
    Returns:
        tuple: (AI response text, list of processed image paths) or None if processing fails
    """
    # Determine image paths based on instance type  
    from django.apps import apps # Get the Item model through Django's apps to avoid circular import
    Item = apps.get_model('inventory', 'Item')
    if isinstance(instance, Item):
        image_paths = [
            att.file.path 
            for att in instance.attachments.filter(content_type__startswith='image/')
            if att.has_valid_file
        ]
    else:  # Attachment instance
        image_paths = [instance.file.path] if (
            instance.is_image and 
            instance.has_valid_file and 
            isinstance(instance.file, File)
        ) else []

    if not image_paths:
        print("No valid images found for analysis")
        return None

    # Process images using vision service
    vision_service = VisionService()
    return vision_service.analyze_images(image_paths, prompt)