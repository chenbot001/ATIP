# Data Processing Pipeline Documentation 

This document details the step-by-step pipeline for collecting, processing, enriching, and analyzing publication data from DBLP and Semantic Scholar (S2). 🧑‍💻

Project Repo: https://github.com/Chenbot001/ATIP

---

## 1. DBLP Data and Affiliation Extraction

The initial step involves parsing the raw DBLP XML data dump to create a foundational dataset of publications.

### Description
This process extracts core paper metadata from the DBLP source. It's important to note that the XML dump **does not contain author affiliation information**; this data must be sourced separately via API or other means later in the pipeline.

### Prerequisite
-   `external\dblp.xml`: latest DBLP data dump, download from `https://dblp.org/xml/`.

### Scripts
-   `scripts\dblp\dblp_parse.py`

### Output
-   **File**: `revised_data\dblp_papers_master.csv`
-   **Schema**: `key`, `title`, `authors`, `year`, `pages`, `ee`, `venue`
-   **Size**: 37,418 rows

---

## 2. Golden Label Verification (ACL Anthology Test)

To ensure data integrity, the extracted DBLP data is cross-referenced against the ACL Anthology as a "golden" dataset. ✅

### Description
This step collects and cleans data from the ACL Anthology to compare it against our DBLP dataset, allowing us to quantify the coverage and identify any discrepancies early on. The analysis revealed 3,394 DBLP papers that were not found in the ACL mapping.

### Scripts
-   `scripts\acl_anthology\get_ACL_papers.py`
-   `scripts\acl_anthology\clean_acl_papers.py`

### Output
-   **File**: `revised_data\acl_dblp_paper_mapping.csv`
-   **Size**: 34,024 rows

---

## 3. Semantic Scholar Paper Matching

This stage enriches the DBLP data by matching each paper to its corresponding entry in the Semantic Scholar (S2) database.

### 3.1 Data Collection
A multi-pass approach is used to find S2 entries, as the S2 API relies on identifiers like ACL ID or DOI rather than the DBLP key.
1.  **ID Creation**: First, S2-compatible IDs (ACL ID, DOI) are extracted from the `ee` URL field in the DBLP data.
2.  **Batch Query by ID**: The S2 API is queried in batches using the extracted IDs to retrieve S2 paper IDs and Corpus IDs.
3.  **Title Search**: Any remaining unmatched papers are searched for using their titles as a fallback.

#### Scripts
-   `scripts\dblp\create_paper_ids.py`
-   `scripts\s2api\S2_batch_query_id.py`
-   `scripts\s2api\S2_search_titles.py`

#### Output
-   **File**: `revised_data\dblp_paper_ids.csv`
-   **Schema**: `dblp_id`, `title`, `author_count`, `s2_id`, `corpus_id`, `acl_id`, `DOI`
-   **Size**: 37,277 rows

### 3.2 Data Verification
After matching, titles are compared to ensure accuracy. Titles with low similarity scores are logged for manual inspection.

#### Script
-   `scripts\s2api\S2_verify_titles.py`

---

## 4. Author List Extraction and Validation

With papers matched, this step extracts author lists from S2 and validates them against the DBLP records.

### Description
The S2 API is queried for the full author list of each paper. The number of authors returned by S2 is then compared to the count from DBLP to flag any mismatches for manual review.

### Scripts
-   `scripts\s2api\S2_batch_query_authorships.py`
-   `scripts\analysis\analyze_author_count.py`

### Output
-   **File**: `revised_data\dblp_paper_authors.csv`
-   **Schema**: `s2_id`, `title`, `dblp_authors`, `dblp_id`, `s2_authors`, `s2_author_ids`

---

## 5. Author Disambiguation, Matching, and Enrichment

This crucial stage disambiguates authors by matching DBLP author names to unique S2 Author IDs and enriches their profiles with metrics. 📈

### 5.1 Data Collection & Profile Creation
Author lists are transformed into a table of one-to-one paper-author relationships (`authorships.csv`), which is then used to create a table of unique author profiles (`author_profiles.csv`).

#### Scripts
-   `scripts\data\create_authorships.py`
-   `scripts\data\create_author_profiles.py`

#### Outputs
-   **Authorships File**: `revised_data\authorships.csv`
    -   **Schema**: `s2_id`, `title`, `dblp_name`, `s2_name`, `s2_author_id`, `authorship_order`, `match_confidence`
-   **Profiles File**: `revised_data\author_profiles.csv`
    -   **Schema**: `dblp_name`, `s2_author_id`, `s2_author_name`, `paper_count`, `first_author_count`, `last_author_count`, `affiliation`, `career_length`, `h_index`, `citations`

### 5.2 Analysis
The similarity between matched DBLP and S2 names is analyzed to verify the matching algorithm's accuracy. Low-similarity matches are logged for manual inspection.

#### Script
-   `scripts\analysis\analyze_name_similarity.py`

### 5.3 Profile Enrichment
Author profiles and paper data are enriched with citation metrics from the S2 API.

#### Scripts
-   `scripts\s2api\S2_batch_query_author_metrics.py`: Fills in author h-index and citation counts.
-   `scripts\s2api\S2_batch_query_citations.py`: Creates a detailed table of citation relationships.

#### Outputs
-   The `revised_data\author_profiles.csv` table is updated with new metrics.
-   **Citation Details File**: `revised_data\citation_details.csv`
    -   **Schema**: `cited_paper_id`, `citing_paper_id`, `year_cited`, `in_dataset`

---

## 6. Affiliation Data Integration

This step integrates author affiliation data from an external mapping provided by CSRankings.

### Prerequisite
-   `external\csrankings.csv`: A file mapping CSRankings author names (which correspond to DBLP names) to their affiliations.

### Script
-   `scripts\data\map_csr_affil.py`

### Output
-   The `affiliation` column in `revised_data\author_profiles.csv` is populated.

---

## 7. Final Metric Calculation

The final step involves running various scripts to calculate custom author-level metrics based on the fully processed and enriched dataset. 🏆

### Scripts
-   All scripts located in the `scripts\metric_calulation\` directory.

### Output
-   Multiple output tables, one for each ranking metric calculated.
-   **Template Schema**: `author_id` (S2 ID), `author_name` (DBLP name), metric scores.

---

## Final Database Schema

The key tables generated by this pipeline are:

-   `dblp_papers_master.csv`: Core paper metadata from DBLP.
    -   **Schema**: `key`, `title`, `authors`, `year`, `pages`, `ee`, `venue`
-   `dblp_paper_ids.csv`: Paper data structured for S2 API requests.
    -   **Schema**: `dblp_id`, `title`, `author_count`, `s2_id`, `corpus_id`, `acl_id`, `DOI`
-   `authorships.csv`: One-to-one relationship between a paper and an author.
    -   **Schema**: `s2_id`, `title`, `dblp_name`, `s2_name`, `s2_author_id`, `authorship_order`, `match_confidence`
-   `author_profiles.csv`: Aggregated data and metrics for each unique author.
    -   **Schema**: `dblp_name`, `s2_author_id`, `s2_author_name`, `paper_count`, `first_author_count`, `last_author_count`, `affiliation`, `career_length`, `h_index`, `citations`
-   `citation_details.csv`: Detailed paper-to-paper citation relationships.
    -   **Schema**: `cited_paper_id`, `citing_paper_id`, `year_cited`, `in_dataset`

---

## Important Notes

-   **Data Duplication**: The `author_profiles.csv` table may contain duplicates, where the same author appears under multiple DBLP name variations.
-   **S2 API Limits**: Be mindful of the Semantic Scholar API rate limits:
    -   1 request per second.
    -   Batch requests are limited to 500 paper IDs or 1000 author IDs per request.
    -   Citation queries return a maximum of 9999 records per request.