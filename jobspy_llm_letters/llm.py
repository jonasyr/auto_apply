import os
from typing import Optional
from dotenv import load_dotenv

# Falls du die offizielle OpenAI-Lib nutzt:
from openai import OpenAI

load_dotenv()

def load_text(path: Optional[str]) -> str:
    if not path or not os.path.exists(path):
        return ""
    with open(path, "r", encoding="utf-8") as f:
        return f.read().strip()

def generate_cover_letter(
    cfg_llm: dict,
    prompt_template: str,
    job: dict,
    resume_text: str,
    template_letter: str,
    example_letter: str = ""
) -> str:
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    filled_prompt = (
        prompt_template
            .replace("{{tone}}", cfg_llm.get("tone",""))
            .replace("{{language}}", cfg_llm.get("language","de"))
            .replace("{{target_length}}", str(cfg_llm.get("target_length", 1500)))
            .replace("{{dual_study_context}}", cfg_llm.get("dual_study_context","").strip())
            .replace("{{job_title}}", job.get("job_title",""))
            .replace("{{company}}", job.get("company",""))
            .replace("{{location}}", job.get("location",""))
            .replace("{{source}}", job.get("source",""))
            .replace("{{url}}", job.get("job_url",""))
            .replace("{{job_description}}", job.get("job_description","").strip()[:6000])
            .replace("{{resume_text}}", resume_text.strip()[:6000])
            .replace("{{template_letter}}", template_letter.strip()[:4000])
            .replace("{{example_letter}}", example_letter.strip()[:4000])
    )

    # Wir geben den System-/User-Block aus der Promptdatei weiter,
    # indem wir ihn als einheitlichen "input" in messages legen.
    # Alternativ kannst du System/User sauber splitten – hier pragmatisch.
    resp = client.chat.completions.create(
        model=cfg_llm.get("model", "gpt-4o-mini"),
        temperature=float(cfg_llm.get("temperature", 0.6)),
        max_tokens=int(cfg_llm.get("max_tokens", 900)),
        messages=[
            {"role": "system", "content": "Du bist ein präziser, deutschsprachiger Karrieretexter."},
            {"role": "user", "content": filled_prompt}
        ]
    )
    return resp.choices[0].message.content.strip()
