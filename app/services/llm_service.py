"""
LLM service integration for OpenAI and Google Gemini
Handles all interactions with language models with timeout and error handling
"""

import asyncio
import time
import logging
from typing import Tuple, Optional
from abc import ABC, abstractmethod

try:
    import openai
    from openai import AsyncOpenAI
except ImportError:
    AsyncOpenAI = None

try:
    import google.generativeai as genai
except ImportError:
    genai = None

from app.core.config import settings

logger = logging.getLogger(__name__)


class LLMProvider(ABC):
    """Abstract base class for LLM providers"""
    
    @abstractmethod
    async def query(self, prompt: str, system_prompt: Optional[str] = None) -> Tuple[str, float]:
        """Execute query against LLM"""
        pass
    
    @abstractmethod
    async def validate_connection(self) -> bool:
        """Validate connection to LLM"""
        pass


class OpenAIProvider(LLMProvider):
    """OpenAI GPT integration"""
    
    def __init__(self):
        if not settings.OPENAI_API_KEY:
            raise ValueError("OPENAI_API_KEY not set in environment")
        
        self.client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        self.model = settings.OPENAI_MODEL
        self.temperature = settings.LLM_TEMPERATURE
    
    async def query(self, prompt: str, system_prompt: Optional[str] = None) -> Tuple[str, float]:
        """
        Query OpenAI API with timeout handling
        Returns: (response_text, execution_time_ms)
        """
        start_time = time.time()
        
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        
        try:
            response = await asyncio.wait_for(
                self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    temperature=self.temperature,
                    max_tokens=1000,
                    timeout=settings.LLM_TIMEOUT
                ),
                timeout=settings.LLM_TIMEOUT
            )
            
            execution_time = (time.time() - start_time) * 1000  # Convert to ms
            return response.choices[0].message.content, execution_time
            
        except asyncio.TimeoutError:
            execution_time = (time.time() - start_time) * 1000
            logger.error(f"OpenAI timeout after {execution_time}ms")
            raise TimeoutError(f"OpenAI request exceeded {settings.LLM_TIMEOUT}s timeout")
        except Exception as e:
            logger.error(f"OpenAI error: {str(e)}")
            raise
    
    async def validate_connection(self) -> bool:
        """Validate OpenAI connection"""
        try:
            response = await asyncio.wait_for(
                self.client.chat.completions.create(
                    model=self.model,
                    messages=[{"role": "user", "content": "ping"}],
                    max_tokens=10,
                    timeout=5.0
                ),
                timeout=5.0
            )
            return True
        except Exception as e:
            logger.error(f"OpenAI connection validation failed: {e}")
            return False


class GeminiProvider(LLMProvider):
    """Google Gemini integration"""
    
    def __init__(self):
        if not settings.GEMINI_API_KEY:
            raise ValueError("GEMINI_API_KEY not set in environment")
        
        genai.configure(api_key=settings.GEMINI_API_KEY)
        self.model = genai.GenerativeModel(settings.GEMINI_MODEL)
        self.temperature = settings.LLM_TEMPERATURE
    
    async def query(self, prompt: str, system_prompt: Optional[str] = None) -> Tuple[str, float]:
        """
        Query Gemini API with timeout handling
        Returns: (response_text, execution_time_ms)
        """
        start_time = time.time()
        
        full_prompt = prompt
        if system_prompt:
            full_prompt = f"{system_prompt}\n\n{prompt}"
        
        try:
            # Run blocking call in executor to avoid blocking event loop
            loop = asyncio.get_event_loop()
            response = await asyncio.wait_for(
                loop.run_in_executor(
                    None,
                    lambda: self.model.generate_content(
                        full_prompt,
                        generation_config=genai.types.GenerationConfig(
                            temperature=self.temperature,
                            max_output_tokens=1000,
                        )
                    )
                ),
                timeout=settings.LLM_TIMEOUT
            )
            
            execution_time = (time.time() - start_time) * 1000
            return response.text, execution_time
            
        except asyncio.TimeoutError:
            execution_time = (time.time() - start_time) * 1000
            logger.error(f"Gemini timeout after {execution_time}ms")
            raise TimeoutError(f"Gemini request exceeded {settings.LLM_TIMEOUT}s timeout")
        except Exception as e:
            logger.error(f"Gemini error: {str(e)}")
            raise
    
    async def validate_connection(self) -> bool:
        """Validate Gemini connection"""
        try:
            loop = asyncio.get_event_loop()
            await asyncio.wait_for(
                loop.run_in_executor(
                    None,
                    lambda: self.model.generate_content("ping")
                ),
                timeout=5.0
            )
            return True
        except Exception as e:
            logger.error(f"Gemini connection validation failed: {e}")
            return False


class LLMService:
    """Unified service for LLM operations"""
    
    def __init__(self):
        self.provider: Optional[LLMProvider] = None
        self._initialize_provider()
    
    def _initialize_provider(self):
        """Initialize the configured LLM provider"""
        try:
            if settings.LLM_PROVIDER.lower() == "openai":
                if AsyncOpenAI is None:
                    raise ImportError("OpenAI package not installed")
                self.provider = OpenAIProvider()
                logger.info("Initialized OpenAI provider")
            elif settings.LLM_PROVIDER.lower() == "gemini":
                if genai is None:
                    raise ImportError("Google Generative AI package not installed")
                self.provider = GeminiProvider()
                logger.info("Initialized Gemini provider")
            else:
                raise ValueError(f"Unknown LLM provider: {settings.LLM_PROVIDER}")
        except Exception as e:
            logger.error(f"Failed to initialize LLM provider: {e}")
            raise
    
    async def query(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        timeout: Optional[float] = None
    ) -> Tuple[str, float]:
        """
        Execute query with the configured provider
        Returns: (response_text, execution_time_ms)
        """
        if not self.provider:
            raise RuntimeError("LLM provider not initialized")
        
        return await self.provider.query(prompt, system_prompt)
    
    async def validate_connection(self) -> bool:
        """Validate LLM provider connection"""
        if not self.provider:
            return False
        return await self.provider.validate_connection()
    
    def get_provider_name(self) -> str:
        """Get name of active provider"""
        return settings.LLM_PROVIDER


# Global LLM service instance
_llm_service: Optional[LLMService] = None


async def get_llm_service() -> LLMService:
    """Get or create LLM service singleton"""
    global _llm_service
    if _llm_service is None:
        _llm_service = LLMService()
    return _llm_service
