import re

def compute_score(text: str, keywords: dict, bonus_remote: int, malus_senior: int) -> int:
    score = 0
    for k, w in keywords.items():
        score += len(re.findall(rf"(?i)\b{re.escape(k)}\b", text)) * w
    if re.search(r"(?i)\b(remote|home[-\s]?office)\b", text):
        score += bonus_remote
    if re.search(r"(?i)\b(senior|lead|leiter)\b", text):
        score -= malus_senior
    return score
