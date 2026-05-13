"""
LLM Service
Business logic for Language Model interactions
"""

import time
import requests
from typing import Optional
from config import Config


class LLMService:
    """
    Handle communication with LLM providers (Ollama, Gemini)
    Provides text generation and conversational capabilities
    """
    
    def __init__(self, config: Config):
        self.config = config
    
    def generate(self, prompt: str, model_key: str = 'llama3') -> str:
        """
        Generate text using configured LLM provider
        
        Args:
            prompt: Input prompt text
            model_key: Model identifier from MODEL_MAP
            
        Returns:
            Generated text response (cleaned of markdown code blocks)
        """
        if self.config.LLM_PROVIDER == 'ollama':
            response = self._call_ollama(prompt, model_key)
        else:
            response = self._call_gemini(prompt)
        
        # Clean up markdown code blocks if present
        return self._clean_response(response)
    
    def _clean_response(self, response: str) -> str:
        """
        Remove markdown code blocks and convert markdown to HTML
        
        Args:
            response: Raw LLM response
            
        Returns:
            Cleaned response ready for HTML rendering
        """
        import re
        
        # Remove markdown code blocks: ```html ... ``` or ``` ... ```
        cleaned = re.sub(r'```(?:html)?\s*\n?(.*?)\n?```', r'\1', response, flags=re.DOTALL)
        
        # Remove any remaining backticks at start/end
        cleaned = cleaned.strip('`').strip()
        
        # Convert markdown formatting to HTML
        # Bold: **text** or __text__ -> <b>text</b>
        cleaned = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', cleaned)
        cleaned = re.sub(r'__(.+?)__', r'<b>\1</b>', cleaned)
        
        # Italic: *text* or _text_ -> <i>text</i> (but not within already bolded text)
        cleaned = re.sub(r'(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)', r'<i>\1</i>', cleaned)
        cleaned = re.sub(r'(?<!_)_(?!_)(.+?)(?<!_)_(?!_)', r'<i>\1</i>', cleaned)
        
        # Convert markdown lists to HTML lists
        # Detect unordered list blocks (lines starting with * or -)
        def convert_unordered_list(text):
            lines = text.split('\n')
            in_list = False
            result = []
            
            for line in lines:
                stripped = line.lstrip()
                # Check if line starts with * or - (markdown bullet)
                if re.match(r'^[\*\-]\s+', stripped):
                    if not in_list:
                        result.append('<ul>')
                        in_list = True
                    # Remove the bullet marker and wrap in <li>
                    item_text = re.sub(r'^[\*\-]\s+', '', stripped)
                    result.append(f'<li>{item_text}</li>')
                else:
                    if in_list:
                        result.append('</ul>')
                        in_list = False
                    result.append(line)
            
            # Close list if still open
            if in_list:
                result.append('</ul>')
            
            return '\n'.join(result)
        
        cleaned = convert_unordered_list(cleaned)
        
        # Remove excessive blank lines (more than 2 newlines becomes 1)
        cleaned = re.sub(r'\n\n+', '\n', cleaned)
        
        # Convert remaining newlines to spaces to join text naturally
        # But keep structure around lists
        cleaned = re.sub(r'(?<!</li>)(?<!</ul>)(?<!</ol>)\n(?!<ul>)(?!<ol>)(?!<li>)', ' ', cleaned)
        
        # Add <br> between major sections (after lists, before new content)
        cleaned = re.sub(r'(</ul>|</ol>)\s*(?=\w)', r'\1<br>', cleaned)
        
        # Clean up spaces around HTML tags only (not between words)
        cleaned = re.sub(r'\s*(</?(?:ul|ol|li|br)[^>]*>)\s*', r'\1', cleaned)
        
        return cleaned.strip()
    
    def generate_raw(self, prompt: str, model_key: str = 'gemma3') -> str:
        """Generate text without any post-processing (no HTML conversion).
        Use for classification/structured output calls where the response
        must not be modified."""
        if self.config.LLM_PROVIDER == 'ollama':
            return self._call_ollama(prompt, model_key)
        return self._call_gemini(prompt)

    def chat_with_tools(
        self,
        messages: list,
        tools: list,
        model_key: str = 'gemma3',
    ) -> dict:
        """
        Send a multi-turn messages array to Ollama with optional tool schemas.

        Returns a dict:
          {
            "content": str,           # text content (may be empty if only tool calls)
            "tool_calls": [...],      # list of tool call dicts (may be empty)
          }
        """
        model = self.config.MODEL_MAP.get(model_key, 'gemma3:latest')
        payload: dict = {
            "model": model,
            "messages": messages,
            "stream": False,
        }
        if tools:
            payload["tools"] = tools

        try:
            start = time.time()
            response = requests.post(
                self.config.OLLAMA_URL,
                json=payload,
                timeout=self.config.LLM_TIMEOUT,
            )
            elapsed = time.time() - start
            print(f"[Ollama] chat_with_tools model='{model}' time={elapsed:.2f}s")
            if not response.ok:
                print(f"[ERROR] chat_with_tools HTTP {response.status_code}: {response.text[:500]}")
                response.raise_for_status()
            msg = response.json().get("message", {})
            return {
                "content": msg.get("content") or "",
                "tool_calls": msg.get("tool_calls") or [],
            }
        except requests.HTTPError:
            raise
        except Exception as e:
            print(f"[ERROR] chat_with_tools failed: {e}")
            return {"content": f"Sorry, I encountered an error: {e}", "tool_calls": []}

    def _call_ollama(self, prompt: str, model_key: str = 'llama3') -> str:
        """Call Ollama API"""
        model = self.config.MODEL_MAP.get(model_key, 'llama3:latest')
        
        try:
            start_time = time.time()
            response = requests.post(
                self.config.OLLAMA_URL,
                json={
                    'model': model,
                    'messages': [{'role': 'user', 'content': prompt}],
                    'stream': False
                },
                timeout=self.config.LLM_TIMEOUT
            )
            elapsed = time.time() - start_time
            print(f"[Ollama] Model '{model}' response time: {elapsed:.2f}s")
            
            response.raise_for_status()
            return response.json()['message']['content']
        except Exception as e:
            return f"Sorry, {model} (Ollama) could not process your request. ({e})"
    
    def _call_gemini(self, prompt: str) -> str:
        """Call Gemini API"""
        if not self.config.GEMINI_API_KEY:
            return "Gemini API key not set. Please set GEMINI_API_KEY in your environment."
        
        try:
            response = requests.post(
                self.config.GEMINI_URL,
                headers={'Content-Type': 'application/json'},
                params={'key': self.config.GEMINI_API_KEY},
                json={
                    'contents': [{'role': 'user', 'parts': [{'text': prompt}]}]
                },
                timeout=self.config.GEMINI_TIMEOUT
            )
            response.raise_for_status()
            reply = response.json()['candidates'][0]['content']['parts'][0]['text']
            
            # Filter out code/tool responses
            if reply.strip().startswith('```') or 'tool_code' in reply or 'get_stock_info' in reply:
                return "I don't know. Please ask about information shown above or request a different stock."
            
            return reply
        except Exception as e:
            return f"Sorry, Gemini could not process your request. ({e})"
    
    def humanize_response(self, response_html: str, model_key: str = 'llama3') -> str:
        """
        Make response more conversational using LLM
        
        Args:
            response_html: Technical analysis HTML
            model_key: Model to use
            
        Returns:
            Humanized response maintaining HTML formatting
        """
        prompt = (
            "You are a helpful stock market assistant. Only use the information provided below, "
            "which comes from yfinance and internal agents. If you do not know the answer from the "
            "provided information, reply: 'I don't know.' Do not use any outside knowledge or make up answers. "
            "Rewrite the following stock analysis recommendations to sound more human, conversational, "
            "and friendly, but keep ALL the HTML tags and formatting EXACTLY as in the input. "
            "Do NOT remove, escape, or alter any HTML tags.\n\n"
            f"{response_html}"
        )
        
        result = self.generate(prompt, model_key)
        return result if result and not result.startswith("Sorry") else response_html
