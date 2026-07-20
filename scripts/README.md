# AI Researcher Data Pipeline

This document outlines the comprehensive data pipeline used to collect, validate, and assemble AI researcher profiles, along with detailed descriptions of all analysis and processing scripts.

---

## 📊 Script Directory Overview

### **Analysis Scripts** (`scripts/analysis/`)
- **`analyze_author_count.py`**: Analyzes ACL-DBLP author mapping to compare author list lengths and report mismatches (update required to analyze DBLP-S2 mapping)
- **`analyze_author_ids.py`**: Comprehensive analysis of authors and author_ids to find unique ACL and DBLP authors with detailed statistics
- **`analyze_data_structure.py`**: Analyzes column structure of CSV files to understand data types and ranges without loading entire files

### **Classifier Scripts** (`scripts/classifier/`)
- **`assign_theme_to_paper.py`**: Uses pre-trained TF-IDF classifier to assign research themes/tracks to papers
- **`train_PEng_classifier.py`**: Trains a prompt engineering classifier using Qwen API for paper track classification
- **`train_SciBERT_classifier.py`**: Fine-tunes SciBERT model for ACL paper track classification with weighted loss handling
- **`train_TFIDF_classifier.py`**: Trains TF-IDF vectorization with Logistic Regression for paper classification

### **Data Processing Scripts** (`scripts/data/`)
- **`create_author_profiles.py`**: Creates author profiles with ACL names, IDs, DBLP names, and affiliations from csrankings
- **`create_authorships.py`**: Creates authorships table using enhanced name matching between DBLP and Semantic Scholar authors

### **DBLP Scripts** (`scripts/dblp/`)
- **`dblp_api.py`**: Handles DBLP API queries with auto-save, resume capabilities, and venue filtering
- **`dblp_parse.py`**: Parses DBLP XML data dump to extract comprehensive paper details for specific venues
- **`create_paper_ids.py`**: Creates comprehensive paper_ids.csv by extracting IDs from DBLP ee URLs

### **Drission Web Scraping Scripts** (`scripts/drission/`)
- **`scrape_affil_google.py`**: Scrapes author affiliations from Google Scholar with CAPTCHA handling and auto-restart
- **`scrape_affil_openreview.py`**: Scrapes author history and affiliations from OpenReview with checkpointing and resume capabilities

### **Metric Calculation Scripts** (`scripts/metric_calculation/`)
- **`author_contribution.py`**: Calculates FAR, FAI, LAR, LAI metrics using vectorized operations
- **`author_contribution_interactive.py`**: Interactive GUI for author contribution metrics with real-time parameter adjustment
- **`bpr.py`**: Calculates Breakthrough Paper Ratio (BPR) and Low-Impact Paper Ratio (LIPR) with confidence-weighted smoothing
- **`bpr_interactive.py`**: Interactive GUI for BPR/LIPR calculation with percentile parameter adjustment
- **`calculate_research_quality_index.py`**: Comprehensive research quality index calculation with timing decorators
- **`citation_accel.py`**: Calculates citation acceleration metrics using vectorized operations
- **`citation_accel_interactive.py`**: Interactive GUI for citation acceleration analysis
- **`network_growth_catalyst.py`**: Calculates Network Growth Catalyst (NGC) score for community-building ability
- **`rising_star.py`**: Identifies rising stars using TACI, citation acceleration, and author ratio metrics
- **`rising_star_interactive.py`**: Interactive GUI for rising star identification with parameter adjustment
- **`rising_star_magnet.py`**: Calculates Rising Star Magnet (RSM) scores with smoothing
- **`taci.py`**: Calculates Time-Aware Citation Impact (TACI) scores using vectorized operations
- **`taci_interactive.py`**: Interactive GUI for TACI calculation and ranking

### **ZWX Metric Scripts** (`scripts/metric_zwx/`)
- **`calculate_breakthrough_paper_score.py`**: Calculates breakthrough paper scores with award boosts
- **`calculate_early_career_velocity.py`**: Calculates early career velocity metrics
- **`calculate_industry_collaboration_score.py`**: Calculates industry collaboration scores
- **`process_top100_authors.py`**: Processes top 100 authors by h-index

### **Semantic Scholar API Scripts** (`scripts/s2api/`)
- **`S2_batch_query_id.py`**: Batch queries Semantic Scholar API by paper IDs with retry logic
- **`S2_batch_query_papers.py`**: Fetches relational data from Semantic Scholar API
- **`S2_fill_missing.py`**: Fills missing values in paper data using Semantic Scholar API
- **`S2_search_titles.py`**: Searches Semantic Scholar by paper titles
- **`S2_test_query.py`**: Test script for Semantic Scholar API functionality


---

## 🔄 Data Collection Pipeline

### **Phase 1: Paper Data Collection**

The first phase focuses on gathering and validating paper metadata from multiple sources.

* **Primary Data Source**: The pipeline begins by ingesting paper data from the DBLP API and XML dumps.
* **Secondary Data Source**: This data is then matched against records from Semantic Scholar.
* **Validation**: For any conflicts or missing information that cannot be resolved via an exact or partial match, the system uses an LLM to process the paper's PDF as a ground truth source.

**Data Collected:**
- Paper titles, abstracts, venues, years
- Author names and affiliations
- DOI identifiers and external links
- Publication metadata (pages, volumes, etc.)

### **Phase 2: Citation Validation**

Running in parallel, this phase validates the citation counts for the collected papers.

* **Primary Data Source**: Citation counts are primarily sourced from Semantic Scholar.
* **Validation Logic**: A conditional logic is applied to the citation data:
    * If a paper's citation count is **greater than or equal to 2**, the Semantic Scholar count is automatically accepted.
    * If a paper's citation count is **less than 2**, it is flagged for manual review to ensure accuracy.

**Data Collected:**
- Citation counts per paper
- Citation timing data (when papers were cited)
- Citation contexts and relationships
- Citation velocity and acceleration metrics

### **Phase 3: Researcher Profile Assembly**

In the final phase, the validated data is used to construct comprehensive researcher profiles.

* **Inputs**: The system uses the validated paper data and validated citation counts.
* **Outputs**: Each assembled profile contains the researcher's publication list, H-Index, total citations, and research topics, which contribute to an overall impact assessment.

**Data Collected:**
- Author profiles with unique identifiers
- Publication histories and authorship positions
- Affiliation information from multiple sources
- Research topic classifications
- Career progression data

### **Phase 4: Advanced Metrics Calculation**

The final phase calculates sophisticated researcher impact metrics.

**Metrics Calculated:**
- **Author Contribution Metrics**: FAR (First Author Ratio), FAI (First Author Impact), LAR (Last Author Ratio), LAI (Last Author Impact)
- **Breakthrough Paper Ratio (BPR)**: Identifies researchers with high-impact publications
- **Citation Acceleration**: Measures recent momentum in citation growth
- **Network Growth Catalyst (NGC)**: Quantifies community-building ability
- **Rising Star Identification**: Identifies emerging researchers with accelerating impact
- **Time-Aware Citation Impact (TACI)**: Accounts for citation timing in impact assessment
- **Research Quality Index (RQI)**: Comprehensive quality assessment

---

## 📁 Data Source Hierarchy

The pipeline prioritizes data sources as follows:

* **For Paper Metadata**:
    1.  DBLP (Primary)
    2.  Semantic Scholar (Secondary)
    3.  PDF via LLM (Ground Truth for Conflicts)
* **For Citation Counts**:
    1.  Semantic Scholar (Primary)
    2.  Manual Review (For low-count validation)
* **For Author Affiliations**:
    1.  CSRankings (Primary)
    2.  Google Scholar (Secondary)
    3.  OpenReview (Tertiary)
* **For Research Topics**:
    1.  Pre-trained classifiers (SciBERT, TF-IDF)
    2.  LLM-based classification
    3.  Manual annotation

---

## 🗄️ Database Schema

The system uses a normalized data model with four main tables:

### **Core Tables:**
- **`Papers`**: Stores paper metadata with `paper_uuid` as primary key
- **`Authors`**: Stores author profiles with `author_uuid` as primary key  
- **`Authorship`**: Links papers and authors with composite primary key
- **`ExternalIdentifiers`**: Stores third-party IDs for papers and authors

### **Derived Tables:**
- **`Author_Contribution`**: Author contribution metrics (FAR, FAI, LAR, LAI)
- **`Breakthrough_Papers`**: BPR and LIPR scores with smoothing
- **`Citation_Acceleration`**: Citation velocity and acceleration metrics
- **`Network_Growth`**: NGC scores for community building
- **`Rising_Stars`**: Rising star and visionary identification
- **`Research_Quality`**: Comprehensive quality indices

---

## 🚀 Usage Instructions

1. **Data Collection**: Run DBLP and Semantic Scholar scripts to gather initial data
2. **Data Validation**: Use analysis scripts to validate data quality and coverage
3. **Profile Creation**: Execute data processing scripts to create author profiles
4. **Metric Calculation**: Run metric calculation scripts to generate impact scores
5. **Interactive Analysis**: Use interactive scripts for parameter exploration and result visualization

---

## 📊 Output Files

The pipeline generates comprehensive datasets including:
- Author profiles with affiliations and career data
- Paper metadata with citation information
- Authorship relationships with position data
- Citation networks and timing data
- Researcher impact metrics and rankings
- Research topic classifications
- Interactive analysis tools and visualizations