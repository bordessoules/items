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
            # This prompt is for general description analysis
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
        """General text analysis method"""
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

    def generate_listing(self, item_descriptions: str) -> Optional[dict]:
        """Specific method for generating marketplace listings"""
        # This prompt is specifically for marketplace listing generation
        listing_prompt = """En vous basant sur ces descriptions d'objet, générez une annonce pour le site Leboncoin au format JSON avec les champs suivants:
        - subject: titre accrocheur de l'annonce (texte)
        - category: catégorie principale (texte)
        - subcategory: sous-catégorie (texte)
        - brand: marque si visible (texte)
        - type: type de produit (texte)
        - usage: utilisation prévue (texte)
        - condition: état de l'objet (texte)
        - description: description détaillée et attractive (texte)
        - price: prix suggéré en euros (nombre entier)
        
        Important:
        - Gardez un ton professionnel et commercial
        - Mettez en avant les points forts du produit
        - Respectez strictement le format JSON demandé
        - Utilisez uniquement les informations visibles dans les descriptions
        
        Répondez uniquement avec le JSON formaté."""

        try:
            response = self.client.chat.complete(
                model=self.model,
                messages=[
                    {"role": "user", "content": f"{listing_prompt}\n\nDescriptions de l'objet:\n{item_descriptions}"}
                ]
            )
            return response.choices[0].message.content
        except Exception as e:
            print(f"Error generating listing: {e}")
            return None

def handle_text_query(prompt: str) -> Optional[str]:
    """Generic handler for text analysis queries"""
    text_service = TextService()
    return text_service.query_text(prompt)

def handle_listing_generation(descriptions: str) -> Optional[dict]:
    """Generic handler for generating listings"""
    text_service = TextService()
    return text_service.generate_listing(descriptions)
