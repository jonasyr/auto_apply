#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import yaml
import pandas as pd
from tqdm import tqdm
from datetime import datetime

from jobspy import scrape_jobs
from scoring import compute_score
from llm import load_text, generate_cover_letter

def ensure_dir(path: str):
    os.makedirs(path, exist_ok=True)

def main():
    # Try to find config.yaml relative to this script first, then fall back to CWD.
    script_dir = os.path.dirname(__file__)
    candidates = [
        os.path.join(script_dir, "config.yaml"),
        "config.yaml",
    ]
    cfg = None
    for p in candidates:
        if os.path.exists(p):
            with open(p, "r", encoding="utf-8") as f:
                cfg = yaml.safe_load(f)
            break

    if cfg is None:
        print("[ERROR] 'config.yaml' not found. Tried the following paths:")
        for p in candidates:
            print(f"  - {os.path.abspath(p)}")
        print("Place 'config.yaml' in the project folder or run this script from the 'jobspy_llm_letters' directory.")
        return

    out_dir = cfg["output"]["out_dir"]
    ensure_dir(out_dir)

    # --- 1) Scrape ---
    search = cfg["search"]
    sources = search.get("sources", ["linkedin", "indeed", "google"])
    frames = []

    for src in sources:
        try:
            print(f"[INFO] Scraping {src}...")
            
            # Base parameters that all sites use
            kwargs = {
                "site_name": src,
                "search_term": search["query"],
                "location": search.get("location"),
                "results_wanted": search.get("results_wanted", 60),
                "verbose": search.get("verbose", 2),
            }
            
            # Add optional parameters if they exist in config
            if search.get("hours_old"):
                kwargs["hours_old"] = search.get("hours_old")
                
            if search.get("remote") is not None:
                kwargs["is_remote"] = search.get("remote")
                
            if search.get("job_type"):
                kwargs["job_type"] = search.get("job_type")
                
            if search.get("distance"):
                kwargs["distance"] = search.get("distance")
                
            if search.get("easy_apply") is not None:
                kwargs["easy_apply"] = search.get("easy_apply")
                
            if search.get("proxies"):
                kwargs["proxies"] = search.get("proxies")
                
            if search.get("user_agent"):
                kwargs["user_agent"] = search.get("user_agent")
                
            if search.get("description_format"):
                kwargs["description_format"] = search.get("description_format")
                
            if search.get("offset"):
                kwargs["offset"] = search.get("offset")
            
            # Site-specific parameters
            if src in ["indeed", "glassdoor"] and search.get("country_indeed"):
                kwargs["country_indeed"] = search.get("country_indeed")
                
            if src == "google" and search.get("google_search_term"):
                kwargs["google_search_term"] = search.get("google_search_term")
                
            if src == "linkedin":
                if search.get("linkedin_fetch_description") is not None:
                    kwargs["linkedin_fetch_description"] = search.get("linkedin_fetch_description")
                if search.get("linkedin_company_ids"):
                    kwargs["linkedin_company_ids"] = search.get("linkedin_company_ids")
            
            print(f"[DEBUG] {src} kwargs: {kwargs}")
            
            df = scrape_jobs(**kwargs)

            # Normalize None -> empty and check length
            n = 0
            if df is None:
                print(f"[INFO] {src}: returned None")
            else:
                try:
                    n = len(df)
                except Exception:
                    n = 0
            print(f"[INFO] {src}: {n} results")

            # Save raw results for debugging if any rows
            if df is not None and n > 0:
                df["source"] = src
                frames.append(df)
                raw_path = os.path.join(out_dir, f"raw_{src}.csv")
                try:
                    df.to_csv(raw_path, index=False, encoding="utf-8")
                    print(f"[DEBUG] saved raw results to {raw_path}")
                except Exception as e:
                    print(f"[WARN] could not save raw results for {src}: {e}")
        except Exception as e:
            print(f"[ERROR] {src}: {e}")
            import traceback
            print(f"[DEBUG] Full traceback: {traceback.format_exc()}")

    if not frames:
        print("Keine Ergebnisse gefunden.")
        print("\n[DEBUG] Troubleshooting tips:")
        print("1. Try a more specific location (e.g., 'Berlin' instead of 'Deutschland')")
        print("2. Try simpler search terms (e.g., 'Python' instead of 'Werkstudent Informatik')")
        print("3. Check if your search terms exist on the job sites manually")
        print("4. For Google Jobs, the google_search_term might need adjustment")
        print("5. Consider using proxies if you're being rate limited")
        return

    jobs = (
        pd.concat(frames, ignore_index=True)
          .drop_duplicates(subset=["job_url"])
          .reset_index(drop=True)
    )

    print(f"[INFO] Total unique jobs found: {len(jobs)}")

    # --- 2) Scoring/Filter ---
    kw = cfg["scoring"]["keywords"]
    bonus_remote = cfg["scoring"].get("bonus_remote", 2)
    malus_senior = cfg["scoring"].get("malus_senior", 3)
    jobs["score"] = jobs.apply(
        lambda r: compute_score(
            " ".join(str(r.get(k,"")) for k in ["title","company","description","location"]),
            kw, bonus_remote, malus_senior
        ), axis=1
    )
    jobs = jobs.sort_values("score", ascending=False)
    if cfg["output"].get("save_jobs_csv", True):
        jobs.to_csv(os.path.join(out_dir, "jobs.csv"), index=False, encoding="utf-8")

    # Top-K auswählen (optional min_score)
    min_score = cfg["scoring"].get("min_score", -999)
    jobs_top = jobs[jobs["score"] >= min_score].head(cfg["scoring"].get("top_k", 25)).copy()

    print(f"[INFO] Jobs after filtering: {len(jobs_top)}")

    # --- 3) LLM-Generierung ---
    prompt_template = load_text("prompts/cover_letter_prompt.txt")
    resume_text = load_text(cfg["files"]["resume_path"])
    template_letter = load_text(cfg["files"]["template_letter_path"])
    example_letter = load_text(cfg["files"].get("example_letter_path","")) if cfg["files"].get("example_letter_path") else ""

    llm_cfg = cfg["llm"]

    drafted = 0
    for _, row in tqdm(jobs_top.iterrows(), total=len(jobs_top), desc="Drafting"):
        job = {
            "job_title": row.get("title",""),
            "company": row.get("company",""),
            "location": row.get("location",""),
            "job_description": row.get("description",""),
            "source": row.get("source",""),
            "job_url": row.get("job_url",""),
        }
        
        try:
            text = generate_cover_letter(
                cfg_llm=llm_cfg,
                prompt_template=prompt_template,
                job=job,
                resume_text=resume_text,
                template_letter=template_letter,
                example_letter=example_letter
            )

            safe_company = "".join(c if c.isalnum() or c in " .-_()" else "_" for c in job["company"])[:80]
            safe_title   = "".join(c if c.isalnum() or c in " .-_()" else "_" for c in job["job_title"])[:80]
            fname = f"{safe_company} - {safe_title}.txt".replace("/", "_").strip()
            header = (
                f"{datetime.now().strftime('%d.%m.%Y')}\n"
                f"{job['company']} – {job['location']}\n"
                f"Quelle: {job['source']} | URL: {job['job_url']}\n\n"
            )
            with open(os.path.join(out_dir, fname), "w", encoding="utf-8") as f:
                f.write(header + text + "\n")
            drafted += 1
        except Exception as e:
            print(f"[WARN] Failed to generate letter for {job['company']}: {e}")

    print(f"Fertig: {drafted} Anschreiben-Drafts in '{out_dir}'")

if __name__ == "__main__":
    main()