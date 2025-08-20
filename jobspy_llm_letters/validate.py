#!/usr/bin/env python3
"""
Configuration Validation Script
Validates setup and configuration before running main application
"""

import os
import sys
import yaml
import logging
from pathlib import Path
from typing import Dict, List, Tuple, Any
from dotenv import load_dotenv

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ValidationError(Exception):
    """Custom exception for validation errors"""
    pass

class ConfigValidator:
    def __init__(self, config_path: str = "config.yaml"):
        self.config_path = Path(config_path)
        self.config = None
        self.errors = []
        self.warnings = []
        
    def load_config(self) -> bool:
        """Load and parse configuration file"""
        try:
            if not self.config_path.exists():
                self.errors.append(f"Configuration file not found: {self.config_path}")
                return False
                
            with open(self.config_path, 'r', encoding='utf-8') as f:
                self.config = yaml.safe_load(f)
                
            if not self.config:
                self.errors.append("Configuration file is empty or invalid")
                return False
                
            return True
        except yaml.YAMLError as e:
            self.errors.append(f"YAML parsing error: {e}")
            return False
        except Exception as e:
            self.errors.append(f"Error loading config: {e}")
            return False
    
    def validate_search_config(self) -> bool:
        """Validate search configuration"""
        search = self.config.get('search', {})
        valid = True
        
        # Required fields
        required_fields = ['query', 'sources']
        for field in required_fields:
            if not search.get(field):
                self.errors.append(f"Search.{field} is required")
                valid = False
        
        # Validate sources
        sources = search.get('sources', [])
        if not isinstance(sources, list):
            self.errors.append("Search.sources must be a list")
            valid = False
        else:
            valid_sources = {'linkedin', 'indeed', 'zip_recruiter', 'glassdoor', 'google', 'bayt', 'bdjobs'}
            invalid_sources = set(sources) - valid_sources
            if invalid_sources:
                self.errors.append(f"Invalid job sources: {invalid_sources}")
                valid = False
        
        # Validate parameter conflicts
        if 'hours_old' in search:
            conflicting = []
            if search.get('job_type'):
                conflicting.append('job_type')
            if search.get('remote') is not None:
                conflicting.append('remote')
            if search.get('easy_apply') is not None:
                conflicting.append('easy_apply')
            
            if conflicting and any(src in ['indeed', 'glassdoor', 'linkedin'] for src in sources):
                self.warnings.append(f"hours_old conflicts with {conflicting} on Indeed/LinkedIn/Glassdoor")
        
        # Validate numeric fields
        numeric_fields = {
            'results_wanted': (1, 1000),
            'distance': (1, 100),
            'hours_old': (1, 8760),  # Max 1 year
            'offset': (0, 10000),
            'verbose': (0, 2)
        }
        
        for field, (min_val, max_val) in numeric_fields.items():
            if field in search:
                value = search[field]
                if not isinstance(value, int) or value < min_val or value > max_val:
                    self.errors.append(f"Search.{field} must be integer between {min_val} and {max_val}")
                    valid = False
        
        # Google-specific validation
        if 'google' in sources and not search.get('google_search_term'):
            self.warnings.append("Google Jobs requires google_search_term for best results")
        
        # Country validation for Indeed/Glassdoor
        if any(src in ['indeed', 'glassdoor'] for src in sources):
            if not search.get('country_indeed'):
                self.warnings.append("country_indeed recommended for Indeed/Glassdoor")
        
        return valid
    
    def validate_scoring_config(self) -> bool:
        """Validate scoring configuration"""
        scoring = self.config.get('scoring', {})
        valid = True
        
        # Check keywords
        keywords = scoring.get('keywords', {})
        if not keywords:
            self.warnings.append("No keywords defined for scoring")
        else:
            for keyword, weight in keywords.items():
                if not isinstance(weight, (int, float)):
                    self.errors.append(f"Keyword '{keyword}' weight must be numeric")
                    valid = False
                elif abs(weight) > 20:
                    self.warnings.append(f"Very high weight for keyword '{keyword}': {weight}")
        
        # Check bonus/malus values
        numeric_scoring = {
            'bonus_remote': (-10, 10),
            'malus_senior': (0, 20),
            'min_score': (-50, 50),
            'top_k': (1, 1000)
        }
        
        for field, (min_val, max_val) in numeric_scoring.items():
            if field in scoring:
                value = scoring[field]
                if not isinstance(value, (int, float)) or value < min_val or value > max_val:
                    self.errors.append(f"Scoring.{field} must be number between {min_val} and {max_val}")
                    valid = False
        
        return valid
    
    def validate_llm_config(self) -> bool:
        """Validate LLM configuration"""
        llm = self.config.get('llm', {})
        valid = True
        
        # Model validation
        model = llm.get('model', 'gpt-4o-mini')
        valid_models = {
            'gpt-4o-mini', 'gpt-4o', 'gpt-4', 'gpt-4-turbo', 
            'gpt-3.5-turbo', 'gpt-3.5-turbo-16k'
        }
        if model not in valid_models:
            self.warnings.append(f"Unknown model '{model}', may not work")
        
        # Numeric parameters
        numeric_llm = {
            'temperature': (0.0, 2.0),
            'max_tokens': (50, 4000),
            'target_length': (500, 5000)
        }
        
        for field, (min_val, max_val) in numeric_llm.items():
            if field in llm:
                value = llm[field]
                if not isinstance(value, (int, float)) or value < min_val or value > max_val:
                    self.errors.append(f"LLM.{field} must be number between {min_val} and {max_val}")
                    valid = False
        
        # Check dual study context
        if not llm.get('dual_study_context'):
            self.warnings.append("dual_study_context not set - letters will be generic")
        
        return valid
    
    def validate_file_paths(self) -> bool:
        """Validate file paths configuration"""
        files = self.config.get('files', {})
        valid = True
        
        required_files = {
            'resume_path': 'Resume/CV file',
            'template_letter_path': 'Cover letter template'
        }
        
        for field, description in required_files.items():
            path_str = files.get(field)
            if not path_str:
                self.warnings.append(f"{description} path not set: {field}")
                continue
                
            # Resolve path relative to config file
            if not Path(path_str).is_absolute():
                path = self.config_path.parent / path_str
            else:
                path = Path(path_str)
                
            if not path.exists():
                self.warnings.append(f"{description} file not found: {path}")
        
        return valid
    
    def validate_output_config(self) -> bool:
        """Validate output configuration"""
        output = self.config.get('output', {})
        
        out_dir = Path(output.get('out_dir', 'out'))
        try:
            out_dir.mkdir(exist_ok=True)
        except Exception as e:
            self.errors.append(f"Cannot create output directory {out_dir}: {e}")
            return False
        
        return True
    
    def validate_environment(self) -> bool:
        """Validate environment setup"""
        load_dotenv()
        valid = True
        
        # Check API keys
        openai_key = os.getenv('OPENAI_API_KEY')
        if not openai_key:
            self.errors.append("OPENAI_API_KEY not set in environment")
            valid = False
        elif not openai_key.startswith('sk-'):
            self.warnings.append("OPENAI_API_KEY doesn't look like a valid OpenAI key")
        
        # Check dependencies
        required_modules = [
            'jobspy', 'pandas', 'yaml', 'tqdm', 'openai', 'dotenv'
        ]
        
        missing_modules = []
        for module in required_modules:
            try:
                __import__(module.replace('-', '_'))
            except ImportError:
                missing_modules.append(module)
        
        if missing_modules:
            self.errors.append(f"Missing required modules: {missing_modules}")
            valid = False
        
        return valid
    
    def validate_all(self) -> Tuple[bool, List[str], List[str]]:
        """Run all validations"""
        self.errors = []
        self.warnings = []
        
        if not self.load_config():
            return False, self.errors, self.warnings
        
        validation_steps = [
            self.validate_search_config,
            self.validate_scoring_config,
            self.validate_llm_config,
            self.validate_file_paths,
            self.validate_output_config,
            self.validate_environment
        ]
        
        all_valid = True
        for step in validation_steps:
            if not step():
                all_valid = False
        
        return all_valid, self.errors, self.warnings

def test_api_connection() -> Tuple[bool, str]:
    """Test API connections"""
    try:
        from llm import test_llm_connection
        if test_llm_connection():
            return True, "LLM connection successful"
        else:
            return False, "LLM connection failed"
    except Exception as e:
        return False, f"LLM test error: {e}"

def test_jobspy_simple() -> Tuple[bool, str]:
    """Test basic JobSpy functionality"""
    try:
        from jobspy import scrape_jobs
        
        # Try a very simple search
        result = scrape_jobs(
            site_name="indeed",
            search_term="test",
            location="Berlin",
            results_wanted=1,
            verbose=0
        )
        
        if result is not None:
            return True, f"JobSpy test successful (found {len(result)} results)"
        else:
            return False, "JobSpy returned no results"
            
    except Exception as e:
        return False, f"JobSpy test error: {e}"

def main():
    """Main validation function"""
    print("🔍 JobSpy LLM Letters - Configuration Validation")
    print("=" * 50)
    
    # Find config file
    config_candidates = ["config.yaml", "jobspy_llm_letters/config.yaml"]
    config_path = None
    
    for candidate in config_candidates:
        if Path(candidate).exists():
            config_path = candidate
            break
    
    if not config_path:
        print("❌ No config.yaml found. Run setup.py first.")
        return False
    
    # Validate configuration
    validator = ConfigValidator(config_path)
    valid, errors, warnings = validator.validate_all()
    
    # Print results
    if errors:
        print("\n❌ ERRORS (must fix):")
        for error in errors:
            print(f"  • {error}")
    
    if warnings:
        print("\n⚠️  WARNINGS (should review):")
        for warning in warnings:
            print(f"  • {warning}")
    
    if not errors and not warnings:
        print("✅ Configuration validation passed!")
    elif not errors:
        print("✅ Configuration is valid (with warnings)")
    else:
        print("❌ Configuration validation failed")
        return False
    
    # Test connections
    print("\n🧪 Testing connections...")
    
    # Test LLM
    llm_ok, llm_msg = test_api_connection()
    print(f"{'✅' if llm_ok else '❌'} LLM API: {llm_msg}")
    
    # Test JobSpy (optional)
    if '--skip-jobspy' not in sys.argv:
        jobspy_ok, jobspy_msg = test_jobspy_simple()
        print(f"{'✅' if jobspy_ok else '⚠️ '} JobSpy: {jobspy_msg}")
        if not jobspy_ok:
            print("    (This might be due to rate limiting - try again later)")
    
    # Final result
    overall_ok = valid and llm_ok
    print(f"\n{'🎉' if overall_ok else '❌'} Overall status: {'Ready to run!' if overall_ok else 'Needs fixes'}")
    
    if overall_ok:
        print("\nNext steps:")
        print("  python main.py")
    else:
        print("\nPlease fix the issues above and run validation again.")
    
    return overall_ok

if __name__ == "__main__":
    if "--help" in sys.argv:
        print("""
Configuration Validation Script

Usage:
  python validate.py [options]

Options:
  --help           Show this help
  --skip-jobspy    Skip JobSpy connection test

This script validates:
- Configuration file syntax and values
- Required files exist
- Environment variables are set
- API connections work
- Dependencies are installed
""")
    else:
        success = main()
        sys.exit(0 if success else 1)