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
            df = scrape_jobs(
                site_name=src,
                search_term=search["query"],
                location=search.get("location"),
                results_wanted=search.get("results_wanted", 60),
                hours_old=search.get("hours_old", 336),
                is_remote=search.get("remote"),
                country=search.get("country", "DE")
            )
            df["source"] = src
            frames.append(df)
        except Exception as e:
            print(f"[WARN] {src}: {e}")

    if not frames:
        print("Keine Ergebnisse gefunden.")
        return

    jobs = (
        pd.concat(frames, ignore_index=True)
          .drop_duplicates(subset=["job_url"])
          .reset_index(drop=True)
    )

    # --- 2) Scoring/Filter ---
    kw = cfg["scoring"]["keywords"]
    bonus_remote = cfg["scoring"].get("bonus_remote", 2)
    malus_senior = cfg["scoring"].get("malus_senior", 3)
    jobs["score"] = jobs.apply(
        lambda r: compute_score(
            " ".join(str(r.get(k,"")) for k in ["job_title","company","job_description","location"]),
            kw, bonus_remote, malus_senior
        ), axis=1
    )
    jobs = jobs.sort_values("score", ascending=False)
    if cfg["output"].get("save_jobs_csv", True):
        jobs.to_csv(os.path.join(out_dir, "jobs.csv"), index=False, encoding="utf-8")

    # Top-K auswählen (optional min_score)
    min_score = cfg["scoring"].get("min_score", -999)
    jobs_top = jobs[jobs["score"] >= min_score].head(cfg["scoring"].get("top_k", 25)).copy()

    # --- 3) LLM-Generierung ---
    prompt_template = load_text("prompts/cover_letter_prompt.txt")
    resume_text = load_text(cfg["files"]["resume_path"])
    template_letter = load_text(cfg["files"]["template_letter_path"])
    example_letter = load_text(cfg["files"].get("example_letter_path","")) if cfg["files"].get("example_letter_path") else ""

    llm_cfg = cfg["llm"]

    drafted = 0
    for _, row in tqdm(jobs_top.iterrows(), total=len(jobs_top), desc="Drafting"):
        job = {
            "job_title": row.get("job_title",""),
            "company": row.get("company",""),
            "location": row.get("location",""),
            "job_description": row.get("job_description",""),
            "source": row.get("source",""),
            "job_url": row.get("job_url",""),
        }
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

    print(f"Fertig: {drafted} Anschreiben-Drafts in '{out_dir}'")

if __name__ == "__main__":
    main()
