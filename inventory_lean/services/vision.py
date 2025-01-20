from pathlib import Path
from dotenv import load_dotenv
from mistralai.client import MistralClient
from mistralai.models.chat_completion import ChatMessage
import os
from PIL import Image


env_path = Path(__file__).parent.parent / '.env'
load_dotenv(env_path)


class VisionService:
    def __init__(self):
        self.client = MistralClient(api_key=os.getenv('MISTRAL_API_KEY'))
        self.model = "pixtral-12b-2409"

    def analyze_image(self, image_path: str) -> str:
        if not Path(image_path).exists():
            return ""
        
        messages = [ChatMessage(
            role="user",
            content="List all visible text, codes, and details in this image.",
            files=[image_path]
        )]
        
        response = self.client.chat(
            model=self.model,
            messages=messages
        )
        return response.choices[0].message.content
