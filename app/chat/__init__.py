# app/chat/__init__.py
"""
Chat module for TAAFT backend
Provides conversational LLM chat features with MongoDB storage
"""
from .routes import router

__all__ = ["router"]
