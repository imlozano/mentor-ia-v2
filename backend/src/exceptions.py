"""Excepciones de dominio con mensajes amigables para la API."""

from __future__ import annotations


class AppError(Exception):
    def __init__(self, message: str, status_code: int = 500) -> None:
        self.message = message
        self.status_code = status_code
        super().__init__(message)


class DocumentNotFoundError(AppError):
    def __init__(self) -> None:
        super().__init__("No encontré ese documento en esta sesión.", 404)


class DocumentEmptyError(AppError):
    def __init__(self) -> None:
        super().__init__("El documento existe pero no tiene chunks indexados.", 422)


class QdrantUnavailableError(AppError):
    def __init__(self) -> None:
        super().__init__("Qdrant no respondió; intenta de nuevo.", 503)


class OpenAIRateLimitError(AppError):
    def __init__(self) -> None:
        super().__init__("Límite de uso alcanzado.", 429)


class OpenAIServiceError(AppError):
    def __init__(self) -> None:
        super().__init__("OpenAI no respondió; intenta de nuevo.", 503)
