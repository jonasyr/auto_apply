import os
import logging
from typing import Optional, Dict, Any
from pathlib import Path
from dotenv import load_dotenv

# Support for multiple LLM providers
try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    logging.warning("OpenAI library not installed. Install with: pip install openai")

load_dotenv()
logger = logging.getLogger(__name__)

class LLMError(Exception):
    """Custom exception for LLM-related errors"""
    pass

class CoverLetterGenerator:
    def __init__(self, api_key: Optional[str] = None):
        if not OPENAI_AVAILABLE:
            raise LLMError("OpenAI library not available. Install with: pip install openai")
        
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise LLMError("OpenAI API key not found. Set OPENAI_API_KEY environment variable.")
        
        self.client = OpenAI(api_key=self.api_key)
        
    def generate(
        self,
        cfg_llm: Dict[str, Any],
        prompt_template: str,
        job: Dict[str, str],
        resume_text: str,
        template_letter: str,
        example_letter: str = ""
    ) -> str:
        """Generate a cover letter using LLM"""
        try:
            # Prepare context data
            context = self._prepare_context(cfg_llm, job, resume_text, template_letter, example_letter)
            
            # Fill prompt template
            filled_prompt = self._fill_prompt_template(prompt_template, context)
            
            # Validate inputs
            self._validate_inputs(filled_prompt, cfg_llm)
            
            # Generate response
            response = self._call_llm(filled_prompt, cfg_llm)
            
            # Post-process response
            return self._post_process_response(response, cfg_llm)
            
        except Exception as e:
            logger.error(f"Error generating cover letter for {job.get('company', 'Unknown')}: {e}")
            raise LLMError(f"Cover letter generation failed: {e}")
    
    def _prepare_context(
        self,
        cfg_llm: Dict[str, Any],
        job: Dict[str, str],
        resume_text: str,
        template_letter: str,
        example_letter: str
    ) -> Dict[str, str]:
        """Prepare context dictionary for prompt template"""
        # Truncate long texts to avoid token limits
        max_description_length = 4000
        max_resume_length = 3000
        max_template_length = 2000
        max_example_length = 2000
        
        return {
            "tone": cfg_llm.get("tone", "professionell und respektvoll"),
            "language": cfg_llm.get("language", "de"),
            "target_length": str(cfg_llm.get("target_length", 1500)),
            "dual_study_context": cfg_llm.get("dual_study_context", "").strip(),
            "job_title": job.get("job_title", "").strip(),
            "company": job.get("company", "").strip(),
            "location": job.get("location", "").strip(),
            "source": job.get("source", "").strip(),
            "url": job.get("job_url", "").strip(),
            "job_description": self._truncate_text(job.get("job_description", ""), max_description_length),
            "resume_text": self._truncate_text(resume_text, max_resume_length),
            "template_letter": self._truncate_text(template_letter, max_template_length),
            "example_letter": self._truncate_text(example_letter, max_example_length)
        }
    
    def _truncate_text(self, text: str, max_length: int) -> str:
        """Truncate text to maximum length with intelligent cutoff"""
        if not text or len(text) <= max_length:
            return text
        
        # Try to cut at sentence boundary
        truncated = text[:max_length]
        last_sentence = truncated.rfind('.')
        last_newline = truncated.rfind('\n')
        
        # Cut at the latest sentence or paragraph boundary
        cutoff = max(last_sentence, last_newline)
        if cutoff > max_length * 0.8:  # If we can keep at least 80% of content
            return text[:cutoff + 1].strip()
        else:
            return text[:max_length].strip() + "..."
    
    def _fill_prompt_template(self, template: str, context: Dict[str, str]) -> str:
        """Fill prompt template with context values"""
        filled = template
        for key, value in context.items():
            placeholder = "{{" + key + "}}"
            filled = filled.replace(placeholder, str(value))
        
        # Check for unfilled placeholders
        import re
        unfilled = re.findall(r'\{\{[^}]+\}\}', filled)
        if unfilled:
            logger.warning(f"Unfilled placeholders in prompt: {unfilled}")
        
        return filled
    
    def _validate_inputs(self, prompt: str, cfg_llm: Dict[str, Any]) -> None:
        """Validate inputs before sending to LLM"""
        if not prompt.strip():
            raise LLMError("Empty prompt")
        
        if len(prompt) > 50000:  # Rough token limit check
            logger.warning(f"Prompt is very long ({len(prompt)} chars), may hit token limits")
        
        model = cfg_llm.get("model", "gpt-4o-mini")
        if not model:
            raise LLMError("No model specified")
    
    def _call_llm(self, prompt: str, cfg_llm: Dict[str, Any]) -> str:
        """Make API call to LLM"""
        model = cfg_llm.get("model", "gpt-4o-mini")
        temperature = float(cfg_llm.get("temperature", 0.7))
        max_tokens = int(cfg_llm.get("max_tokens", 1200))
        
        # Validate parameters
        temperature = max(0.0, min(2.0, temperature))
        max_tokens = max(100, min(4000, max_tokens))
        
        try:
            response = self.client.chat.completions.create(
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
                messages=[
                    {
                        "role": "system",
                        "content": "Du bist ein erfahrener Karriereberater und Texter, spezialisiert auf präzise, wirkungsvolle Bewerbungsschreiben. Du schreibst authentisch, überzeugend und ohne Floskeln."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ]
            )
            
            return response.choices[0].message.content.strip()
            
        except Exception as e:
            if "rate_limit" in str(e).lower():
                raise LLMError("Rate limit exceeded. Please wait and try again.")
            elif "quota" in str(e).lower():
                raise LLMError("API quota exceeded. Check your OpenAI account.")
            elif "authentication" in str(e).lower():
                raise LLMError("Authentication failed. Check your API key.")
            else:
                raise LLMError(f"API call failed: {e}")
    
    def _post_process_response(self, response: str, cfg_llm: Dict[str, Any]) -> str:
        """Post-process the LLM response"""
        if not response:
            raise LLMError("Empty response from LLM")
        
        # Remove any markdown formatting if present
        response = response.replace("```", "").strip()
        
        # Remove common unwanted prefixes/suffixes
        unwanted_prefixes = [
            "Hier ist ",
            "Hier ist das ",
            "Das ist ",
            "Sehr gerne:",
        ]
        
        for prefix in unwanted_prefixes:
            if response.startswith(prefix):
                response = response[len(prefix):].strip()
        
        # Ensure proper formatting
        if not response.endswith('.'):
            # Only add period if it doesn't end with punctuation
            if not response[-1] in '!?':
                response += '.'
        
        return response

def load_text(path: Optional[str]) -> str:
    """Load text file with improved error handling"""
    if not path:
        return ""

    # Convert to Path object for better handling
    if not isinstance(path, Path):
        path = Path(path)
    
    # If path is relative, resolve it relative to this file's directory
    if not path.is_absolute():
        base_dir = Path(__file__).parent
        path = base_dir / path

    if not path.exists():
        logger.warning(f"File not found: {path}")
        return ""

    try:
        with open(path, "r", encoding="utf-8") as f:
            content = f.read().strip()
            logger.debug(f"Loaded {len(content)} characters from {path}")
            return content
    except Exception as e:
        logger.error(f"Error loading file {path}: {e}")
        return ""

# Backwards compatibility function
def generate_cover_letter(
    cfg_llm: Dict[str, Any],
    prompt_template: str,
    job: Dict[str, str],
    resume_text: str,
    template_letter: str,
    example_letter: str = ""
) -> str:
    """Generate cover letter - backwards compatible interface"""
    try:
        generator = CoverLetterGenerator()
        return generator.generate(
            cfg_llm=cfg_llm,
            prompt_template=prompt_template,
            job=job,
            resume_text=resume_text,
            template_letter=template_letter,
            example_letter=example_letter
        )
    except Exception as e:
        logger.error(f"Cover letter generation failed: {e}")
        # Return a fallback template-based letter
        return _generate_fallback_letter(job, cfg_llm)

def _generate_fallback_letter(job: Dict[str, str], cfg_llm: Dict[str, Any]) -> str:
    """Generate a simple fallback cover letter when LLM fails"""
    company = job.get("company", "Ihr Unternehmen")
    title = job.get("job_title", "die ausgeschriebene Position")
    
    fallback = f"""Betreff: Bewerbung als {title}

Sehr geehrte Damen und Herren,

hiermit bewerbe ich mich um die Position als {title} bei {company}.

Als dualer Informatikstudent im 5. Semester bringe ich praktische Erfahrung in der IT-Branche mit und suche einen neuen Praxispartner ab Oktober 2025.

Gerne stelle ich Ihnen meine Qualifikationen in einem persönlichen Gespräch vor.

Mit freundlichen Grüßen
Jonas Weirauch

---
HINWEIS: Dies ist ein Fallback-Anschreiben. Das LLM-System war nicht verfügbar.
"""
    
    logger.warning(f"Generated fallback letter for {company}")
    return fallback

# Test function for development
def test_llm_connection() -> bool:
    """Test if LLM connection works"""
    try:
        generator = CoverLetterGenerator()
        test_job = {
            "job_title": "Test Position",
            "company": "Test Company",
            "job_description": "Test description",
            "location": "Test Location",
            "job_url": "https://example.com",
            "source": "test"
        }
        
        test_config = {
            "model": "gpt-4o-mini",
            "temperature": 0.5,
            "max_tokens": 100,
            "tone": "professionell",
            "language": "de"
        }
        
        response = generator._call_llm("Schreibe 'Test erfolgreich' auf Deutsch.", test_config)
        
        return bool(response and "test" in response.lower())
        
    except Exception as e:
        logger.error(f"LLM connection test failed: {e}")
        return False

if __name__ == "__main__":
    # Test the connection
    if test_llm_connection():
        print("✅ LLM connection successful")
    else:
        print("❌ LLM connection failed")