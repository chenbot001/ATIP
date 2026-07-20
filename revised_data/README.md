# ATIP Revised Data Documentation

This directory contains the processed and enriched dataset for the ATIP (Academic Talent Identification Platform) project. The dataset focuses on computational linguistics and natural language processing papers from ACL (Association for Computational Linguistics) venues, enriched with data from multiple external sources.

## 📊 Dataset Overview

The dataset contains **9 CSV files** with a total size of approximately **350 MB** and covers:
- **38,805 ACL papers** from various venues
- **48,567 unique authors** with detailed profiles
- **161,180 authorship records** linking papers to authors
- **2+ million citation relationships** between papers
- Cross-references to **DBLP** and **Semantic Scholar** databases

## 🗂️ Data Files

### 1. `acl_papers_master.csv` (99.53 MB, 38,805 rows)
**Primary source of ACL paper data** - Contains comprehensive information about papers from ACL Anthology.

**Columns:**
- `paper_id` (string): Unique ACL paper identifier (e.g., "2020.acl-main.1")
- `title` (string): Paper title
- `authors` (string): List of author names as JSON array
- `author_ids` (string): List of author identifiers (mostly empty)
- `author_affils` (string): List of author affiliations (mostly empty)
- `abstract` (string): Paper abstract (mostly empty)
- `venue` (string): Conference/venue name (e.g., "ACL", "EMNLP")
- `year` (int): Publication year
- `url` (url): Link to ACL Anthology page
- `doi` (string): Digital Object Identifier (mostly empty)
- `pdf` (string): PDF reference information
- `pages` (string): Page numbers
- `month` (string): Publication month
- `publisher` (string): Publisher information
- `bibtype` (string): Bibliography type (e.g., "inproceedings", "proceedings")
- `is_deleted` (bool): Whether paper is marked as deleted
- `is_frontmatter` (bool): Whether entry is frontmatter (not a research paper)

**Data Quality Notes:**
- Many fields (doi, abstract, author_affils) are empty and intended to be filled by external sources
- Contains both research papers and conference proceedings frontmatter
- Author information is stored as JSON arrays

### 2. `author_profiles.csv` (2.58 MB, 48,567 rows)
**Comprehensive author profiles** with publication statistics and metrics.

**Columns:**
- `dblp_name` (string): Author name as recorded in DBLP
- `s2_author_id` (bigint): Semantic Scholar author identifier
- `s2_author_name` (string): Author name as recorded in Semantic Scholar
- `paper_count` (int): Total number of papers by this author
- `first_author_count` (int): Number of papers where author is first author
- `last_author_count` (int): Number of papers where author is last author
- `h_index` (float): H-index metric from Semantic Scholar
- `citations` (float): Total citation count from Semantic Scholar
- `affiliation` (string): Author affiliation (mostly empty)
- `career_length` (string): Career length information (mostly empty)

**Data Quality Notes:**
- Contains 48,567 unique authors
- H-index and citation data from Semantic Scholar
- Affiliation and career length fields are mostly empty

### 3. `authorships.csv` (25.0 MB, 161,180 rows)
**Paper-author relationships** with authorship order and matching confidence.

**Columns:**
- `s2_id` (string): Semantic Scholar paper identifier
- `title` (string): Paper title
- `dblp_name` (string): Author name from DBLP
- `s2_name` (string): Author name from Semantic Scholar
- `s2_author_id` (bigint): Semantic Scholar author identifier
- `authorship_order` (int): Author position on paper (1 = first author)
- `match_confidence` (string): Confidence level of author name matching

**Data Quality Notes:**
- Contains 161,180 authorship records
- Links papers to individual authors with position information
- Includes confidence scores for author name matching between DBLP and S2

### 4. `citation_details.csv` (188.4 MB, 2,062,979 rows)
**Citation network data** - Records which papers cite other papers.

**Columns:**
- `cited_paper_id` (string): ID of the paper being cited
- `citing_paper_id` (string): ID of the paper doing the citing
- `year_cited` (float): Year when the citation occurred
- `in_dataset` (bool): Whether the citing paper is in our dataset

**Data Quality Notes:**
- Contains 2+ million citation relationships
- Includes citations from papers outside the dataset
- Temporal information available for citation analysis

### 5. `acl_dblp_paper_mapping.csv` (4.27 MB, 34,024 rows)
**Cross-reference mapping** between ACL and DBLP paper identifiers.

**Columns:**
- `acl_paper_id` (string): ACL paper identifier
- `dblp_key` (string): DBLP paper key
- `title` (string): Paper title
- `year` (int): Publication year
- `venue` (string): Conference/venue name

**Data Quality Notes:**
- Maps 34,024 ACL papers to DBLP entries
- Used for cross-referencing between databases

### 6. `dblp_papers_master.csv` (8.7 MB, 37,418 rows)
**DBLP paper data** - Comprehensive bibliographic information from DBLP.

**Columns:**
- `key` (string): DBLP paper key
- `title` (string): Paper title
- `authors` (string): List of authors as JSON array
- `year` (int): Publication year
- `pages` (string): Page numbers
- `ee` (url): Electronic edition URL
- `venue` (string): Conference/venue name

**Data Quality Notes:**
- Contains 37,418 DBLP paper records
- More complete author information than ACL data
- Includes electronic edition links

### 7. `dblp_paper_authors.csv` (12.56 MB, 37,277 rows)
**DBLP author-paper relationships** with cross-references to Semantic Scholar.

**Columns:**
- `s2_id` (string): Semantic Scholar paper identifier
- `title` (string): Paper title
- `dblp_authors` (string): Author names from DBLP
- `dblp_id` (string): DBLP paper identifier
- `s2_authors` (string): Author names from Semantic Scholar
- `s2_author_ids` (string): Semantic Scholar author identifiers

**Data Quality Notes:**
- Links DBLP papers to Semantic Scholar data
- Shows author name variations between databases
- Contains 37,277 paper-author mappings

### 8. `dblp_paper_ids.csv` (6.65 MB, 37,418 rows)
**Comprehensive paper identifier mapping** across multiple databases.

**Columns:**
- `dblp_id` (string): DBLP paper identifier
- `title` (string): Paper title
- `author_count` (int): Number of authors
- `s2_id` (string): Semantic Scholar paper identifier
- `corpus_id` (float): Semantic Scholar corpus identifier
- `acl_id` (string): ACL paper identifier
- `DOI` (string): Digital Object Identifier

**Data Quality Notes:**
- Maps papers across DBLP, Semantic Scholar, and ACL
- Includes DOI information when available
- Contains 37,418 paper records

### 9. `dblp_missing_papers.csv` (1.54 MB, 11,590 rows)
**Papers in DBLP but missing from other sources** - Gap analysis data.

**Columns:**
- `dblp_id` (string): DBLP paper identifier
- `title` (string): Paper title
- `author_count` (int): Number of authors
- `s2_id` (string): Semantic Scholar identifier (mostly empty)
- `corpus_id` (string): Semantic Scholar corpus ID (mostly empty)
- `acl_id` (string): ACL identifier (mostly empty)
- `DOI` (string): Digital Object Identifier

**Data Quality Notes:**
- Contains 11,590 papers that exist in DBLP but are missing from other sources
- Useful for identifying coverage gaps
- Many fields are empty indicating missing cross-references

## 🔗 Data Relationships

The dataset follows a normalized structure with the following key relationships:

1. **Papers** → **Authors** (via `authorships.csv`)
2. **Papers** → **Citations** (via `citation_details.csv`)
3. **ACL Papers** ↔ **DBLP Papers** (via `acl_dblp_paper_mapping.csv`)
4. **DBLP Papers** ↔ **Semantic Scholar Papers** (via `dblp_paper_ids.csv`)

## 📈 Data Coverage

- **ACL Papers**: 38,805 papers from ACL Anthology
- **DBLP Papers**: 37,418 papers from DBLP
- **Authors**: 48,567 unique authors
- **Authorships**: 161,180 paper-author relationships
- **Citations**: 2,062,979 citation relationships
- **Cross-references**: 34,024 ACL-DBLP mappings

## 🎯 Use Cases

This dataset supports various research and analysis tasks:

1. **Author Analysis**: Track author productivity, collaboration patterns, and career progression
2. **Citation Analysis**: Study citation networks, impact metrics, and knowledge flow
3. **Venue Analysis**: Compare different ACL venues and their characteristics
4. **Temporal Analysis**: Study trends in NLP research over time
5. **Collaboration Networks**: Analyze co-authorship patterns and research communities
6. **Impact Assessment**: Calculate various bibliometric indicators

## ⚠️ Data Quality Notes

1. **Missing Data**: Many fields (affiliations, abstracts, DOIs) are empty and intended to be filled by external enrichment
2. **Name Variations**: Author names may vary between DBLP and Semantic Scholar
3. **Incomplete Citations**: Citation data includes papers outside the core dataset
4. **Frontmatter**: ACL data includes conference proceedings frontmatter (not research papers)
5. **Cross-reference Gaps**: Not all papers are present in all databases

## 🔧 Data Processing Pipeline

The data follows the pipeline described in `DATA_PIPELINE_V2.md`:
1. **Core Data Ingestion**: ACL Anthology as primary source
2. **Author Profiling**: Grouping and profiling unique authors
3. **Authorship Construction**: Linking papers to authors with position information
4. **External Enrichment**: Supplementing with DBLP and Semantic Scholar data

## 📝 TODO Items

According to `TODO.txt`, the following improvements are planned:
- Verify DBLP/S2 name similarity distribution
- Deduplicate author and paper IDs
- Clean citations data

## 🚀 Getting Started

To work with this dataset:

1. **Load the data**: Use pandas to read the CSV files
2. **Start with core files**: Begin with `acl_papers_master.csv` and `author_profiles.csv`
3. **Join data**: Use the mapping files to combine information from different sources
4. **Filter as needed**: Remove frontmatter entries and focus on research papers

Example Python code:
```python
import pandas as pd

# Load core data
papers = pd.read_csv('acl_papers_master.csv')
authors = pd.read_csv('author_profiles.csv')
authorships = pd.read_csv('authorships.csv')

# Filter to research papers only
research_papers = papers[~papers['is_frontmatter']]
```
