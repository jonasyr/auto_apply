# JobSpy LLM Letters 🚀

Ein automatisiertes System zum Finden von Jobs und Generieren personalisierter Anschreiben mit KI-Unterstützung.

## ✨ Features

- **Multi-Platform Job Scraping**: Indeed, LinkedIn, Google Jobs, ZipRecruiter, Glassdoor
- **Intelligente Bewertung**: Keyword-basiertes Scoring mit konfigurierbaren Gewichtungen
- **KI-Anschreiben**: Automatische Generierung personalisierter Bewerbungsschreiben
- **Interactive Dashboard**: Webbasierte Übersicht aller Jobs und Anschreiben
- **Flexible Konfiguration**: YAML-basierte Einstellungen für alle Parameter

## 🚀 Quick Start

### 1. Installation

```bash
# Repository klonen
git clone https://github.com/your-username/jobspy-llm-letters.git
cd jobspy-llm-letters

# Virtual Environment erstellen
python -m venv venv
source venv/bin/activate  # Linux/Mac
# oder
venv\Scripts\activate     # Windows

# Dependencies installieren
pip install -r requirements.txt
```

### 2. Konfiguration

```bash
# OpenAI API Key setzen
export OPENAI_API_KEY="sk-your-api-key-here"

# Oder in .env Datei
echo "OPENAI_API_KEY=sk-your-api-key-here" > .env
```

### 3. Konfiguration anpassen

Bearbeite `config.yaml`:

```yaml
search:
  query: "Deine Suchbegriffe"
  location: "Deine Stadt, Deutschland"
  sources: ["indeed", "linkedin", "google"]
  
scoring:
  keywords:
    Python: 4        # Deine wichtigsten Skills
    "Data Science": 3
    
llm:
  dual_study_context: |
    Dein persönlicher Kontext hier...
```

### 4. Ausführen

```bash
python main.py
```

### 5. Dashboard öffnen

```bash
# Dashboard starten (einfacher HTTP Server)
cd out
python -m http.server 8000
# Dann http://localhost:8000/Dashboard.html öffnen
```

## 📁 Projektstruktur

```
jobspy_llm_letters/
├── main.py                 # Hauptskript
├── config.yaml            # Konfiguration
├── llm.py                  # LLM Integration
├── scoring.py              # Job-Bewertung
├── requirements.txt        # Dependencies
├── prompts/
│   └── cover_letter_prompt.txt  # LLM Prompt Template
├── data/
│   ├── resume.md          # Dein Lebenslauf
│   ├── template_letter.md # Anschreiben-Template
│   └── example_letter.md  # Beispiel-Anschreiben
└── out/
    ├── jobs.csv           # Alle gefundenen Jobs
    ├── Dashboard.html     # Interactive Übersicht
    └── *.txt              # Generierte Anschreiben
```

## ⚙️ Konfiguration

### Suchparameter

```yaml
search:
  query: "Werkstudent Informatik"           # Hauptsuchbegriff
  location: "Mainz, Deutschland"            # Standort
  google_search_term: "spezifische Google-Suche"  # Für Google Jobs
  sources: ["indeed", "linkedin", "google"] # Job-Quellen
  results_wanted: 60                        # Ergebnisse pro Quelle
  hours_old: 168                           # Max. Alter in Stunden
  country_indeed: "Germany"                # Land für Indeed/Glassdoor
```

### Bewertungssystem

```yaml
scoring:
  keywords:
    # Hohe Gewichtung für wichtige Skills
    Python: 4
    "Data Analytics": 3
    
    # Mittlere Gewichtung
    SQL: 2
    Docker: 2
    
    # Niedrige Gewichtung
    Git: 1
    
  # Boni und Mali
  bonus_remote: 3      # Extra Punkte für Remote-Jobs
  malus_senior: 4      # Abzug für Senior-Positionen
  min_score: -3        # Mindestpunktzahl
  top_k: 25           # Max. Anzahl zu bearbeiten
```

### LLM-Einstellungen

```yaml
llm:
  model: "gpt-4o-mini"        # Oder gpt-4, gpt-3.5-turbo
  temperature: 0.7            # Kreativität (0-1)
  max_tokens: 1200           # Max. Antwortlänge
  target_length: 1800        # Ziel-Zeichenzahl
  tone: "professionell, präzise"
  
  dual_study_context: |
    Dein persönlicher Kontext für das duale Studium...
```

## 🔧 JobSpy-Parameter

### Site-spezifische Einschränkungen

**Indeed/Glassdoor**: Nur eines dieser Parameter kann verwendet werden:
- `hours_old` ODER
- `job_type` + `is_remote` ODER  
- `easy_apply`

**LinkedIn**: Nur eines dieser Parameter:
- `hours_old` ODER
- `easy_apply`

**Google Jobs**: Benötigt spezifischen `google_search_term`

### Beispiel-Konfigurationen

**Nur aktuelle Jobs (letzten 7 Tage):**
```yaml
search:
  hours_old: 168
  # job_type und easy_apply NICHT verwenden!
```

**Vollzeit + Remote (ohne Zeitfilter):**
```yaml
search:
  job_type: "fulltime"
  remote: true
  # hours_old NICHT verwenden!
```

## 🌐 Unterstützte Länder

### LinkedIn
- Global verfügbar, nutzt nur `location` Parameter

### ZipRecruiter  
- USA und Kanada

### Indeed/Glassdoor
Unterstützte Länder (verwende `country_indeed`):
- Germany*, Austria*, Switzerland*
- USA*, UK*, Canada*, France*
- Viele weitere (siehe JobSpy Dokumentation)

*Glassdoor verfügbar

## 🚨 Troubleshooting

### Problem: Keine Ergebnisse

**Mögliche Ursachen:**
1. **Zu spezifische Suchbegriffe**
   ```yaml
   # Statt:
   query: "Werkstudent Python Machine Learning München"
   # Versuche:
   query: "Werkstudent Informatik"
   ```

2. **Falsche Standortangabe**
   ```yaml
   # Statt:
   location: "Deutschland"
   # Versuche:
   location: "Berlin" oder "München"
   ```

3. **Google Jobs Syntax**
   ```yaml
   # Google benötigt sehr spezifische Syntax:
   google_search_term: "Werkstudent jobs near Berlin since:2025"
   ```

### Problem: Rate Limiting

**Lösung: Proxies verwenden**
```yaml
search:
  proxies: 
    - "user:pass@proxy1.com:8080"
    - "user:pass@proxy2.com:8080"
```

### Problem: LinkedIn blockiert

**LinkedIn ist sehr restriktiv:**
- Nutze Proxies (praktisch Pflicht)
- Reduziere `results_wanted`
- Füge Delays zwischen Requests ein

### Problem: LLM-Fehler

**Häufige Fehler:**
1. **API Key fehlt:**
   ```bash
   export OPENAI_API_KEY="sk-..."
   ```

2. **Rate Limit erreicht:**
   - Warte einige Minuten
   - Nutze kleinere `max_tokens`

3. **Quota überschritten:**
   - Prüfe dein OpenAI-Konto
   - Ggf. Billing einrichten

### Problem: Dashboard lädt Anschreiben nicht

**Das Dashboard kann keine lokalen Dateien laden!**

**Lösung: HTTP Server starten**
```bash
cd out
python -m http.server 8000
# Dann http://localhost:8000/Dashboard.html besuchen
```

## 🎯 Optimierung-Tipps

### 1. Keyword-Optimierung

Analysiere deine Ergebnisse:
```python
from scoring import analyze_keywords_performance

# Nach dem Scraping:
stats = analyze_keywords_performance(jobs_df, keywords)
suggestions = suggest_keyword_improvements(stats)
```

### 2. Suchstrategie

**Indeed (beste Quelle):**
- Nutze `-` zum Ausschließen: `"software engineer" -senior -lead`
- Nutze `""` für exakte Phrasen: `"working student"`
- Kombiniere Skills: `python OR java OR javascript`

**LinkedIn:**
- Einfache Keywords verwenden
- Proxies praktisch Pflicht
- Kleinere `results_wanted` (10-20)

**Google Jobs:**
- Sehr spezifische Syntax nötig
- Teste die Suche erst manuell auf Google
- Kopiere dann die finale Suchanfrage

### 3. Performance

**Parallel Scraping:**
```yaml
search:
  sources: ["indeed"]  # Erstmal nur Indeed testen
  results_wanted: 30   # Kleinere Anzahl für Tests
```

**Dann erweitern:**
```yaml
search:
  sources: ["indeed", "linkedin", "google"]
  results_wanted: 60
```

## 🧪 Testing

```bash
# LLM-Verbindung testen
python -c "from llm import test_llm_connection; print(test_llm_connection())"

# Scoring testen
python scoring.py

# Vollständiger Test mit wenigen Jobs
python main.py  # mit results_wanted: 5 in config.yaml
```

## 📊 Metriken verstehen

### Scoring Breakdown
- **Keyword Score**: Basierend auf gefundenen Keywords
- **Location Bonus**: Für bevorzugte Standorte
- **Remote Bonus**: Für Remote-Möglichkeiten  
- **Seniority Malus**: Abzug für Senior-Positionen
- **Total Score**: Finale Bewertung

### Dashboard Statistiken
- **Gefundene Jobs**: Alle gescrapten Jobs
- **Gefilterte Jobs**: Nach Score-Filter
- **Ø Score**: Durchschnittsbewertung
- **Anschreiben verfügbar**: Erfolgreich generiert

## 🔐 Sicherheit & Datenschutz

- **API Keys**: Niemals in Git committen, nutze `.env`
- **Lokale Verarbeitung**: Alle Daten bleiben lokal
- **Datenschutz**: Keine Job-Daten werden an Dritte gesendet
- **Rate Limiting**: Respektiert API-Limits der Job-Boards

## 🤝 Contributing

1. Fork das Repository
2. Feature Branch erstellen: `git checkout -b feature/amazing-feature`
3. Committe deine Änderungen: `git commit -m 'Add amazing feature'`
4. Push zum Branch: `git push origin feature/amazing-feature`
5. Pull Request öffnen

## 📝 Lizenz

MIT License - siehe [LICENSE](LICENSE) für Details.

## 🙏 Credits

- [JobSpy](https://github.com/cullenwatson/JobSpy) - Job Scraping Library
- [OpenAI](https://openai.com) - GPT API für Anschreiben-Generierung
- [PapaParse](https://www.papaparse.com/) - CSV Parsing im Dashboard

---

**Viel Erfolg bei der Jobsuche! 🎯**