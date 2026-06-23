"""
Proveedor de IA abstracto — soporta Gemini (free) y Claude.
Configuracion en settings.py: AI_PROVIDER = "gemini" | "claude"
"""
from typing import Optional


class AIProvider:
    """Interfaz abstracta para generacion de texto con IA."""

    def __init__(self, provider: Optional[str] = None):
        from config.settings import settings
        self.provider = (provider or settings.ai_provider).lower()
        self._client = None

    def _get_client(self):
        if self._client:
            return self._client
        if self.provider == "gemini":
            import google.generativeai as genai
            from config.settings import settings
            genai.configure(api_key=settings.gemini_api_key or "")
            self._client = genai.GenerativeModel(settings.gemini_model or "gemini-2.5-flash")
        elif self.provider == "claude":
            import anthropic
            from config.settings import settings
            self._client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        return self._client

    def generar(self, system_prompt: str, user_prompt: str, max_tokens: int = 1500) -> str:
        client = self._get_client()
        if self.provider == "gemini":
            response = client.generate_content(
                f"{system_prompt}\n\n{user_prompt}",
                generation_config={"max_output_tokens": max_tokens},
            )
            return response.text
        elif self.provider == "claude":
            response = client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=max_tokens,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}],
            )
            return response.content[0].text
        return "[AI no configurado]"
