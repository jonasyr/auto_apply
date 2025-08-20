#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import yaml
import pandas as pd
import logging
from tqdm import tqdm
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from pathlib import Path

from jobspy import scrape_jobs
from scoring import compute_score
from llm import load_text, generate_cover_letter

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('jobspy.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class JobScrapingError(Exception):
    """Custom exception for job scraping errors"""
    pass

class JobSpyApp:
    def __init__(self, config_path: str = "config.yaml"):
        self.config = self._load_config(config_path)
        self.jobs_df = pd.DataFrame()
        self.draft_count = 0
        
    def _load_config(self, config_path: str) -> Dict:
        """Load configuration with fallback paths"""
        script_dir = Path(__file__).parent
        candidates = [
            script_dir / config_path,
            Path(config_path),
            script_dir / "config.yaml"
        ]
        
        for path in candidates:
            if path.exists():
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        config = yaml.safe_load(f)
                        logger.info(f"Loaded config from: {path}")
                        return config
                except yaml.YAMLError as e:
                    logger.error(f"Error parsing YAML config: {e}")
                    raise
        
        raise FileNotFoundError(f"Config file not found. Tried: {[str(p) for p in candidates]}")
    
    def _ensure_output_dir(self) -> Path:
        """Ensure output directory exists"""
        # Resolve output directory relative to the script directory when a
        # relative path is provided in the config. This prevents writing to
        # an unexpected root-level /out/ path when the process CWD differs.
        script_dir = Path(__file__).parent
        cfg_out = Path(self.config["output"]["out_dir"])

        if not cfg_out.is_absolute():
            out_dir = (script_dir / cfg_out).resolve()
        else:
            out_dir = cfg_out.resolve()

        out_dir.mkdir(parents=True, exist_ok=True)
        return out_dir
    
    def _get_site_specific_params(self, site: str, base_params: Dict) -> Dict:
        """Get site-specific parameters based on JobSpy limitations"""
        params = base_params.copy()
        search_config = self.config["search"]
        
        # Site-specific parameter handling
        if site in ["indeed", "glassdoor"]:
            # Indeed/Glassdoor specific parameters
            if search_config.get("country_indeed"):
                params["country_indeed"] = search_config["country_indeed"]
            
            # Indeed limitations: Only one of these can be used
            if search_config.get("hours_old"):
                params["hours_old"] = search_config["hours_old"]
                # Remove conflicting parameters
                params.pop("job_type", None)
                params.pop("is_remote", None)
                params.pop("easy_apply", None)
            elif search_config.get("job_type") or search_config.get("remote") is not None:
                if search_config.get("job_type"):
                    params["job_type"] = search_config["job_type"]
                if search_config.get("remote") is not None:
                    params["is_remote"] = search_config["remote"]
                # Remove conflicting parameters
                params.pop("easy_apply", None)
            elif search_config.get("easy_apply") is not None:
                params["easy_apply"] = search_config["easy_apply"]
        
        elif site == "linkedin":
            # LinkedIn specific parameters
            if search_config.get("linkedin_fetch_description") is not None:
                params["linkedin_fetch_description"] = search_config["linkedin_fetch_description"]
            if search_config.get("linkedin_company_ids"):
                params["linkedin_company_ids"] = search_config["linkedin_company_ids"]
            
            # LinkedIn limitations: Only one of these can be used
            if search_config.get("hours_old"):
                params["hours_old"] = search_config["hours_old"]
                params.pop("easy_apply", None)
            elif search_config.get("easy_apply") is not None:
                params["easy_apply"] = search_config["easy_apply"]
        
        elif site == "google":
            # Google requires specific search term
            if search_config.get("google_search_term"):
                params["google_search_term"] = search_config["google_search_term"]
            else:
                logger.warning("Google requires google_search_term parameter")
        
        # Remove None values
        return {k: v for k, v in params.items() if v is not None}
    
    def scrape_jobs_from_sources(self) -> List[pd.DataFrame]:
        """Scrape jobs from all configured sources"""
        search_config = self.config["search"]
        sources = search_config.get("sources", ["linkedin", "indeed", "google"])
        frames = []
        
        # Base parameters common to all sites
        base_params = {
            "search_term": search_config["query"],
            "location": search_config.get("location"),
            "results_wanted": search_config.get("results_wanted", 60),
            "verbose": search_config.get("verbose", 1),
        }
        
        # Add optional common parameters
        for param in ["distance", "proxies", "user_agent", "description_format", "offset"]:
            if search_config.get(param):
                base_params[param] = search_config[param]
        
        for source in sources:
            try:
                logger.info(f"Scraping jobs from {source}...")
                
                # Get site-specific parameters
                params = self._get_site_specific_params(source, base_params)
                params["site_name"] = source
                
                logger.debug(f"Parameters for {source}: {params}")
                
                # Scrape jobs
                df = scrape_jobs(**params)
                
                if df is None or len(df) == 0:
                    logger.warning(f"No results from {source}")
                    continue
                
                # Add source column
                df["source"] = source
                frames.append(df)
                
                logger.info(f"Successfully scraped {len(df)} jobs from {source}")
                
                # Save raw results for debugging
                out_dir = self._ensure_output_dir()
                raw_path = out_dir / f"raw_{source}.csv"
                df.to_csv(raw_path, index=False, encoding="utf-8")
                logger.debug(f"Saved raw results to {raw_path}")
                
            except Exception as e:
                logger.error(f"Error scraping {source}: {e}", exc_info=True)
                continue
        
        if not frames:
            raise JobScrapingError("No jobs found from any source. Check your configuration and network connection.")
        
        return frames
    
    def process_and_score_jobs(self, frames: List[pd.DataFrame]) -> pd.DataFrame:
        """Combine, deduplicate and score jobs"""
        # Combine all dataframes
        jobs_df = pd.concat(frames, ignore_index=True)
        
        # Remove duplicates based on job_url
        initial_count = len(jobs_df)
        jobs_df = jobs_df.drop_duplicates(subset=["job_url"]).reset_index(drop=True)
        logger.info(f"Removed {initial_count - len(jobs_df)} duplicate jobs")
        
        # Score jobs
        scoring_config = self.config["scoring"]
        keywords = scoring_config["keywords"]
        bonus_remote = scoring_config.get("bonus_remote", 2)
        malus_senior = scoring_config.get("malus_senior", 3)
        
        def score_job(row):
            text = " ".join(str(row.get(k, "")) for k in ["title", "company", "description", "location"])
            return compute_score(text, keywords, bonus_remote, malus_senior)
        
        jobs_df["score"] = jobs_df.apply(score_job, axis=1)
        jobs_df = jobs_df.sort_values("score", ascending=False)
        
        logger.info(f"Scored {len(jobs_df)} jobs")
        return jobs_df
    
    def filter_top_jobs(self, jobs_df: pd.DataFrame) -> pd.DataFrame:
        """Filter jobs based on minimum score and top-k"""
        scoring_config = self.config["scoring"]
        min_score = scoring_config.get("min_score", -999)
        top_k = scoring_config.get("top_k", 25)
        
        filtered_jobs = jobs_df[jobs_df["score"] >= min_score].head(top_k).copy()
        logger.info(f"Filtered to {len(filtered_jobs)} top jobs (min_score: {min_score}, top_k: {top_k})")
        
        return filtered_jobs
    
    def generate_cover_letters(self, jobs_df: pd.DataFrame) -> None:
        """Generate cover letters for filtered jobs"""
        files_config = self.config["files"]
        llm_config = self.config["llm"]
        out_dir = self._ensure_output_dir()
        
        # Load template files
        try:
            prompt_template = load_text("prompts/cover_letter_prompt.txt")
            resume_text = load_text(files_config["resume_path"])
            template_letter = load_text(files_config["template_letter_path"])
            example_letter = load_text(files_config.get("example_letter_path", ""))
        except Exception as e:
            logger.error(f"Error loading template files: {e}")
            raise
        
        if not prompt_template:
            logger.error("Could not load prompt template")
            return
        
        success_count = 0
        for _, row in tqdm(jobs_df.iterrows(), total=len(jobs_df), desc="Generating cover letters"):
            try:
                job_data = {
                    "job_title": row.get("title", ""),
                    "company": row.get("company", ""),
                    "location": row.get("location", ""),
                    "job_description": row.get("description", ""),
                    "source": row.get("source", ""),
                    "job_url": row.get("job_url", ""),
                }
                
                # Generate cover letter
                letter_text = generate_cover_letter(
                    cfg_llm=llm_config,
                    prompt_template=prompt_template,
                    job=job_data,
                    resume_text=resume_text,
                    template_letter=template_letter,
                    example_letter=example_letter
                )
                
                # Create safe filename
                safe_company = self._sanitize_filename(job_data["company"])[:80]
                safe_title = self._sanitize_filename(job_data["job_title"])[:80]
                filename = f"{safe_company} - {safe_title}.txt"
                
                # Create header with metadata
                header = (
                    f"{datetime.now().strftime('%d.%m.%Y')}\n"
                    f"{job_data['company']} – {job_data['location']}\n"
                    f"Score: {row.get('score', 0)} | Quelle: {job_data['source']}\n"
                    f"URL: {job_data['job_url']}\n"
                    f"{'-' * 50}\n\n"
                )
                
                # Save cover letter
                output_path = out_dir / filename
                with open(output_path, "w", encoding="utf-8") as f:
                    f.write(header + letter_text + "\n")
                
                success_count += 1
                
            except Exception as e:
                logger.error(f"Failed to generate letter for {row.get('company', 'Unknown')}: {e}")
                continue
        
        self.draft_count = success_count
        logger.info(f"Successfully generated {success_count} cover letters")
    
    def _sanitize_filename(self, text: str) -> str:
        """Sanitize text for use in filename"""
        if not text:
            return "Unknown"
        return "".join(c if c.isalnum() or c in " .-_()" else "_" for c in str(text))
    
    def save_results(self, jobs_df: pd.DataFrame) -> None:
        """Save jobs data to CSV"""
        if self.config["output"].get("save_jobs_csv", True):
            out_dir = self._ensure_output_dir()
            jobs_path = out_dir / "jobs.csv"
            jobs_df.to_csv(jobs_path, index=False, encoding="utf-8")
            logger.info(f"Saved jobs data to {jobs_path}")
    
    def run(self) -> None:
        """Main execution method"""
        try:
            logger.info("Starting job scraping application...")
            
            # Step 1: Scrape jobs
            frames = self.scrape_jobs_from_sources()
            
            # Step 2: Process and score
            self.jobs_df = self.process_and_score_jobs(frames)
            
            # Step 3: Save all results
            self.save_results(self.jobs_df)
            
            # Step 4: Filter top jobs
            top_jobs = self.filter_top_jobs(self.jobs_df)
            
            # Step 5: Generate cover letters
            if len(top_jobs) > 0:
                self.generate_cover_letters(top_jobs)
            else:
                logger.warning("No jobs passed filtering criteria")
            
            # Step 6: Print summary
            self._print_summary(top_jobs)
            
        except Exception as e:
            logger.error(f"Application failed: {e}", exc_info=True)
            raise
    
    def _print_summary(self, top_jobs: pd.DataFrame) -> None:
        """Print execution summary"""
        # Show the resolved output directory path
        out_dir = str(self._ensure_output_dir())
        print(f"\n{'='*50}")
        print("JOB SCRAPING SUMMARY")
        print(f"{'='*50}")
        print(f"Total jobs found: {len(self.jobs_df)}")
        print(f"Jobs after filtering: {len(top_jobs)}")
        print(f"Cover letters generated: {self.draft_count}")
        print(f"Output directory: {out_dir}")

        if len(top_jobs) > 0:
            print(f"\nTop scoring jobs:")
            for _, job in top_jobs.head(5).iterrows():
                print(f"  • {job.get('company', 'Unknown')} - {job.get('title', 'Unknown')} (Score: {job.get('score', 0)})")

        print(f"\nFiles created:")
        print(f"  • jobs.csv - All job data")
        print(f"  • {self.draft_count} cover letter drafts")
        print(f"  • Dashboard.html - Interactive dashboard")

def main():
    """Main entry point"""
    try:
        app = JobSpyApp()
        app.run()
    except KeyboardInterrupt:
        logger.info("Application interrupted by user")
    except Exception as e:
        logger.error(f"Application failed: {e}")
        return 1
    return 0

if __name__ == "__main__":
    exit(main())