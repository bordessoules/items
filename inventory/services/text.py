"""
Text service for interacting with Mistral's LLM.
Handles text-to-text queries using Mistral API.
"""

import os
from mistralai import Mistral
from typing import Optional

class TextService:
    """Service class for handling text operations using Mistral's API."""
    
    def __init__(self):
        """Initialize Mistral client with API configuration"""
        try:
            self.client = Mistral(api_key=os.getenv('MISTRAL_API_KEY'))
            self.model = "ministral-8b-latest"
            self.default_prompt = """Analysez ces images qui doivent représenter le même objet sous différents angles.
                            IMPORTANT :

                            Ne décrivez que les informations explicitement visibles dans les descriptions
                            Ne faites aucune supposition sur les marques ou modèles
                            Concentrez-vous sur les textes visibles, les codes et les caractéristiques physiques
                            Si quelque chose n'est pas clair, indiquez "non visible" au lieu de faire des suppositions
                            Listez les textes et nombres exactement comme ils apparaissent, sans interprétation"""
        except KeyError:
            raise EnvironmentError("MISTRAL_API_KEY not found in environment variables")

    def query_text(self, descriptions: str, custom_prompt: str = None) -> Optional[str]:
        prompt = f"{custom_prompt or self.default_prompt}\n\nDescriptions:\n{descriptions}"
        try:
            response = self.client.chat.complete(
                model=self.model,
                messages=[{"role": "user", "content": prompt}]
            )
            return response.choices[0].message.content
        except Exception as e:
            print(f"Error calling Mistral API: {e}")
            return None

def handle_text_query(prompt: str) -> Optional[str]:
    """
    Generic handler for text queries.
    
    Args:
        prompt: Text prompt for analysis
        
    Returns:
        str: AI response text or None if processing fails
    """
    text_service = TextService()
    return text_service.query_text(prompt)
