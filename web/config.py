"""
Application Configuration
Centralized configuration management for the Flask application
"""

import os
from typing import Dict
from dotenv import load_dotenv

# Load environment variables from config/.env file (doesn't override existing env vars)
load_dotenv(os.path.join(os.path.dirname(__file__), '..', 'config', '.env'), override=False)


class Config:
    """Application configuration with environment variable support"""
    
    # Flask settings
    SECRET_KEY = os.getenv('FLASK_SECRET_KEY', 'replace-with-random-secret-key-in-production')
    DEBUG = os.getenv('FLASK_DEBUG', 'False').lower() == 'true'
    
    # LLM Provider settings
    LLM_PROVIDER = os.getenv('LLM_PROVIDER', 'gemini').lower()
    GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
    OLLAMA_URL = os.getenv('OLLAMA_URL', 'http://localhost:11434/api/chat')
    GEMINI_URL = 'https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent'
    
    # Model mappings
    MODEL_MAP: Dict[str, str] = {
        'llama3': 'llama3:8b',
        'qwen3': 'qwen3:4b',
        'gemma3': 'gemma3:4b',
    }
    
    # Timeouts
    LLM_TIMEOUT = int(os.getenv('LLM_TIMEOUT', '60'))
    GEMINI_TIMEOUT = int(os.getenv('GEMINI_TIMEOUT', '15'))
    
    # Cache settings
    ENABLE_CACHE = os.getenv('ENABLE_CACHE', 'True').lower() == 'true'
    CACHE_TTL = int(os.getenv('CACHE_TTL', '300'))  # 5 minutes
    
    @classmethod
    def validate(cls) -> bool:
        """Validate configuration"""
        if cls.LLM_PROVIDER == 'gemini' and not cls.GEMINI_API_KEY:
            print("Warning: GEMINI_API_KEY not set but LLM_PROVIDER is 'gemini'")
            return False
        return True
