from pathlib import Path
from dotenv import load_dotenv
from mistralai.client import MistralClient
from mistralai.models.chat_completion import ChatMessage
import os

env_path = Path(__file__).parent.parent / '.env'
load_dotenv(env_path)

class TextService:
    def __init__(self):
        self.client = MistralClient(api_key=os.getenv('MISTRAL_API_KEY'))
        self.model = "mistral-medium"

    def analyze_descriptions(self, descriptions: list) -> str:
        messages = [ChatMessage(
            role="user",
            content=f"Create a comprehensive item description from these image analyses:\n{'\n'.join(descriptions)}"
        )]
        
        response = self.client.chat(
            model=self.model,
            messages=messages
        )
        return response.choices[0].message.content