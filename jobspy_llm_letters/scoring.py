import re
import logging
from typing import Dict, List, Any, Tuple
from dataclasses import dataclass
import math

logger = logging.getLogger(__name__)

@dataclass
class ScoringResult:
    """Detailed scoring result with breakdown"""
    total_score: int
    keyword_score: int
    location_score: int
    remote_bonus: int
    seniority_malus: int
    length_penalty: int
    matched_keywords: List[str]
    warning_flags: List[str]

class JobScorer:
    """Advanced job scoring with detailed analytics"""
    
    def __init__(self):
        # Common negative indicators
        self.negative_keywords = [
            "senior", "lead", "leiter", "head", "director", "manager",
            "5+ jahre", "mehrjährig", "langjährig", "erfahren",
            "vollzeit", "40 stunden", "unbefristet"
        ]
        
        # Positive location indicators
        self.preferred_locations = [
            "mainz", "wiesbaden", "frankfurt", "darmstadt", "mannheim",
            "remote", "homeoffice", "hybrid"
        ]
        
        # Warning flags
        self.warning_patterns = [
            (r"vollzeit", "Vollzeit-Position"),
            (r"unbefristet", "Unbefristete Stelle"),
            (r"berufserfahrung", "Berufserfahrung erforderlich"),
            (r"abgeschlossen", "Abgeschlossenes Studium"),
            (r"minimum.*jahr", "Mindesterfahrung erforderlich")
        ]
    
    def score_job(
        self,
        text: str,
        keywords: Dict[str, int],
        bonus_remote: int = 2,
        malus_senior: int = 3,
        location: str = "",
        job_type: str = ""
    ) -> ScoringResult:
        """
        Comprehensive job scoring with detailed breakdown
        
        Args:
            text: Combined job text (title + company + description + location)
            keywords: Keyword weights dictionary
            bonus_remote: Bonus points for remote jobs
            malus_senior: Penalty for senior positions
            location: Job location
            job_type: Job type (fulltime, parttime, etc.)
        """
        text_lower = text.lower()
        
        # 1. Keyword scoring
        keyword_score, matched_keywords = self._score_keywords(text_lower, keywords)
        
        # 2. Location scoring
        location_score = self._score_location(text_lower, location.lower() if location else "")
        
        # 3. Remote bonus
        remote_bonus = self._calculate_remote_bonus(text_lower, bonus_remote)
        
        # 4. Seniority penalty
        seniority_malus = self._calculate_seniority_malus(text_lower, malus_senior)
        
        # 5. Job type and length considerations
        length_penalty = self._calculate_length_penalty(text_lower, job_type.lower() if job_type else "")
        
        # 6. Warning flags
        warning_flags = self._detect_warning_flags(text_lower)
        
        # Calculate total score
        total_score = (
            keyword_score +
            location_score +
            remote_bonus -
            seniority_malus -
            length_penalty
        )
        
        return ScoringResult(
            total_score=total_score,
            keyword_score=keyword_score,
            location_score=location_score,
            remote_bonus=remote_bonus,
            seniority_malus=seniority_malus,
            length_penalty=length_penalty,
            matched_keywords=matched_keywords,
            warning_flags=warning_flags
        )
    
    def _score_keywords(self, text: str, keywords: Dict[str, int]) -> Tuple[int, List[str]]:
        """Score based on keyword matches"""
        score = 0
        matched = []
        
        for keyword, weight in keywords.items():
            # Create regex pattern for word boundary matching
            pattern = rf"\b{re.escape(keyword.lower())}\b"
            matches = len(re.findall(pattern, text))
            
            if matches > 0:
                matched.append(f"{keyword} (x{matches})")
                # Diminishing returns for multiple occurrences
                score += weight * min(matches, 3) * (0.8 ** max(0, matches - 1))
        
        return int(score), matched
    
    def _score_location(self, text: str, location: str) -> int:
        """Score based on location preferences"""
        score = 0
        
        # Check for preferred locations in text or explicit location
        combined_location = f"{text} {location}"
        
        for pref_loc in self.preferred_locations:
            if pref_loc in combined_location:
                if pref_loc in ["remote", "homeoffice", "hybrid"]:
                    score += 3  # Higher bonus for remote
                else:
                    score += 1  # Moderate bonus for preferred cities
        
        return score
    
    def _calculate_remote_bonus(self, text: str, bonus_remote: int) -> int:
        """Calculate remote work bonus"""
        remote_indicators = [
            "remote", "homeoffice", "home office", "home-office",
            "fernarbeit", "mobiles arbeiten", "hybrid"
        ]
        
        for indicator in remote_indicators:
            if indicator in text:
                return bonus_remote
        
        return 0
    
    def _calculate_seniority_malus(self, text: str, malus_senior: int) -> int:
        """Calculate penalty for senior positions"""
        penalty = 0
        
        for negative in self.negative_keywords:
            if negative in text:
                if negative in ["senior", "lead", "leiter"]:
                    penalty += malus_senior
                elif negative in ["vollzeit", "40 stunden"]:
                    penalty += max(1, malus_senior // 2)  # Smaller penalty for fulltime
                else:
                    penalty += 1
        
        return min(penalty, malus_senior * 2)  # Cap the penalty
    
    def _calculate_length_penalty(self, text: str, job_type: str) -> int:
        """Calculate penalty for inappropriate job length/type"""
        penalty = 0
        
        # Penalty for explicit fulltime requirements when looking for part-time
        if job_type == "fulltime" or "vollzeit" in text:
            if "teilzeit" not in text and "werkstudent" not in text:
                penalty += 2
        
        # Penalty for permanent positions when looking for temporary
        if "unbefristet" in text and "befristet" not in text:
            penalty += 1
        
        return penalty
    
    def _detect_warning_flags(self, text: str) -> List[str]:
        """Detect potential issues with the job posting"""
        flags = []
        
        for pattern, description in self.warning_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                flags.append(description)
        
        return flags

# Backwards compatibility function
def compute_score(
    text: str,
    keywords: Dict[str, int],
    bonus_remote: int = 2,
    malus_senior: int = 3,
    location: str = "",
    job_type: str = ""
) -> int:
    """
    Compute job score - backwards compatible interface
    
    Args:
        text: Combined job text
        keywords: Keyword weights
        bonus_remote: Remote work bonus
        malus_senior: Senior position penalty
        location: Job location (optional)
        job_type: Job type (optional)
    
    Returns:
        Total score as integer
    """
    scorer = JobScorer()
    result = scorer.score_job(text, keywords, bonus_remote, malus_senior, location, job_type)
    return result.total_score

def compute_detailed_score(
    text: str,
    keywords: Dict[str, int],
    bonus_remote: int = 2,
    malus_senior: int = 3,
    location: str = "",
    job_type: str = ""
) -> ScoringResult:
    """
    Compute detailed job score with breakdown
    
    Args:
        text: Combined job text
        keywords: Keyword weights
        bonus_remote: Remote work bonus
        malus_senior: Senior position penalty
        location: Job location (optional)
        job_type: Job type (optional)
    
    Returns:
        Detailed scoring result
    """
    scorer = JobScorer()
    return scorer.score_job(text, keywords, bonus_remote, malus_senior, location, job_type)

def analyze_keywords_performance(jobs_df, keywords: Dict[str, int]) -> Dict[str, Any]:
    """
    Analyze keyword performance across all jobs
    
    Args:
        jobs_df: DataFrame with job data
        keywords: Keyword weights dictionary
    
    Returns:
        Dictionary with keyword analysis
    """
    keyword_stats = {}
    
    for keyword, weight in keywords.items():
        matches = 0
        total_score_contribution = 0
        
        for _, job in jobs_df.iterrows():
            text = " ".join(str(job.get(k, "")) for k in ["title", "company", "description", "location"]).lower()
            pattern = rf"\b{re.escape(keyword.lower())}\b"
            job_matches = len(re.findall(pattern, text))
            
            if job_matches > 0:
                matches += 1
                total_score_contribution += weight * job_matches
        
        keyword_stats[keyword] = {
            "weight": weight,
            "jobs_matched": matches,
            "match_rate": matches / len(jobs_df) if len(jobs_df) > 0 else 0,
            "total_score_contribution": total_score_contribution,
            "efficiency": total_score_contribution / weight if weight > 0 else 0
        }
    
    return keyword_stats

def suggest_keyword_improvements(keyword_stats: Dict[str, Any]) -> List[str]:
    """
    Suggest improvements to keyword configuration
    
    Args:
        keyword_stats: Output from analyze_keywords_performance
    
    Returns:
        List of improvement suggestions
    """
    suggestions = []
    
    # Low efficiency keywords
    low_efficiency = [k for k, stats in keyword_stats.items() 
                     if stats["efficiency"] < 1.0 and stats["weight"] > 1]
    
    if low_efficiency:
        suggestions.append(f"Consider reducing weight for low-efficiency keywords: {', '.join(low_efficiency)}")
    
    # High efficiency but low weight keywords
    high_efficiency = [k for k, stats in keyword_stats.items() 
                      if stats["efficiency"] > 5.0 and stats["weight"] < 3]
    
    if high_efficiency:
        suggestions.append(f"Consider increasing weight for high-efficiency keywords: {', '.join(high_efficiency)}")
    
    # Rarely matched keywords
    rare_keywords = [k for k, stats in keyword_stats.items() 
                    if stats["match_rate"] < 0.1 and stats["weight"] > 1]
    
    if rare_keywords:
        suggestions.append(f"Rarely matched keywords (consider synonyms): {', '.join(rare_keywords)}")
    
    return suggestions

# Testing and validation functions
def validate_scoring_config(keywords: Dict[str, int]) -> List[str]:
    """Validate scoring configuration"""
    issues = []
    
    # Check for reasonable weights
    if max(keywords.values()) > 10:
        issues.append("Very high keyword weights detected (>10)")
    
    if min(keywords.values()) < -5:
        issues.append("Very negative keyword weights detected (<-5)")
    
    # Check for balanced scoring
    total_positive = sum(w for w in keywords.values() if w > 0)
    total_negative = sum(w for w in keywords.values() if w < 0)
    
    if abs(total_negative) > total_positive * 0.5:
        issues.append("Too many negative keywords relative to positive ones")
    
    return issues

if __name__ == "__main__":
    # Test the scoring system
    test_keywords = {
        "Python": 4,
        "Data Analytics": 3,
        "Linux": 3,
        "Werkstudent": 3,
        "SQL": 2,
        "senior": -3,
        "vollzeit": -2
    }
    
    test_text = "Werkstudent Python Data Analytics Linux SQL Entwicklung Teilzeit Remote"
    
    # Test basic scoring
    score = compute_score(test_text, test_keywords, 3, 4)
    print(f"Basic score: {score}")
    
    # Test detailed scoring
    detailed = compute_detailed_score(test_text, test_keywords, 3, 4)
    print(f"Detailed score: {detailed}")
    
    # Test validation
    issues = validate_scoring_config(test_keywords)
    if issues:
        print(f"Configuration issues: {issues}")
    else:
        print("✅ Scoring configuration looks good")