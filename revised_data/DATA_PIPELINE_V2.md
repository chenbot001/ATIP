### 📝 A Note on Primary Keys and Identifiers

All unique identifiers in this pipeline are stored as human-readable, prefixed strings. Each ID consists of a short prefix indicating its type (e.g., `publ_`, `auth_`) followed by an underscore and a UUIDv7. This approach ensures that IDs are immediately identifiable in logs, APIs, and during manual inspection, which prevents errors and simplifies debugging. Consequently, all ID columns in the database are stored as text.

---

### ## 🏛️ Database Schema Overview

To keep the core data tables clean and to flexibly handle a variety of external identifiers, this pipeline uses a **normalized data model**. The schema consists of four main tables.

#### Core Tables:

* The **`Papers`** table stores the primary, trusted information for each paper. Its primary key is `paper_uuid`. Other columns include `title`, `year`, `venue`, `abstract`, etc. It also includes an `author_count` column to store the total number of authors for that paper, which helps in easily identifying the last author.

* The **`Authors`** table stores profiles for each unique author. Its primary key is `author_uuid`. It also contains the author's `full_name`, `affiliation` etc.

* The **`Authorship`** table is a join table that links papers and authors together. Its primary key is a **composite key** made up of the `paper_uuid` and `author_uuid` columns together. This structurally enforces that an author can only be linked to a paper once. The table also contains an `author_position` column to record the order of authors on a paper.

#### Identifier Table:

* The **`ExternalIdentifiers`** table stores all third-party IDs for both papers and authors. Its primary key is `identifier_id`. It contains foreign keys, `paper_uuid` and `author_uuid`, to link back to the correct entity. The table has an `id_source` column to name the external source (e.g., 'semantic_scholar', 'doi') and an `id_value` column for the ID itself. A unique constraint ensures a single paper or author cannot have two different IDs from the same source. For performance, an index is placed on the `id_source` and `id_value` columns together.

---

### **Stage 1: Core Data Ingestion**

This stage focuses on ingesting the core paper data from the primary source.

1.  **Parse Primary Source:** Ingest all paper data from the ACL Anthology.
2.  **Filter by Venue:** Keep only papers from the target venues.
3.  **Populate `Papers` Table:** Save the clean, verified data into the `Papers` table, generating a new `publ_` prefixed ID for each entry. The `author_count` field is left `NULL` at this stage.

---

### **Stage 2: Author Profiling & Grouping**

This stage creates profiles for each unique author name.

1.  **Initial Author Ingestion:** Create a list of all author names from the papers in Stage 1.
2.  **Group by Exact Name:** Treat all authors with the identical full name as a single entity.
3.  **Populate `Authors` Table:** Save each unique author into the `Authors` table, generating a new `auth_` prefixed ID.

---

### **Stage 3: Constructing the Authorship Table**

This stage builds the crucial link between papers and authors and populates the total author count.

1.  **Populate Authorship Links:** For each paper, the pipeline iterates through its list of authors. For each author, it creates a new row in the `Authorship` table, storing the `paper_uuid`, the corresponding `author_uuid`, and the author's sequential position as an integer (1, 2, 3, etc.) in the `author_position` column.
2.  **Update Paper's Author Count:** After all author links for a single paper have been inserted, the pipeline calculates the total number of authors. It then updates that paper's row in the `Papers` table, setting the `author_count` field to this total.

---

### ✨ **Stage 4: Data Enrichment from External Sources**

This stage intelligently enriches the dataset by fetching data from external APIs and processing source documents. This is governed by a strict hierarchy of data sources.

#### Data Sources and Hierarchy

The pipeline prioritizes data sources in tiers. Data from a lower-tier source can only be used to fill in information that is missing from all higher-tier sources.

* **Tier 1: Source of Truth - ACL Anthology**
    Your core dataset from the ACL Anthology is the "gold standard" and is never altered by the enrichment process.

* **Tier 2: Curated Bibliographic Data - DBLP**
    The **DBLP Computer Science Bibliography** is the most trusted secondary source for verifying or filling in missing author names, official publication titles, and venue details.

* **Tier 3: Derived Content Data - LLM-Extracted PDF Analysis**
    This source consists of data extracted directly from each paper's PDF. Its primary strength is capturing information **unavailable in any structured API**, such as **author affiliations**.

* **Tier 4: Rich Aggregated Data - Semantic Scholar (S2)**
    **Semantic Scholar** is the primary workhorse for gathering **citation counts**, **TL;DR summaries**, and links to PDFs.

* **Tier 5: Specialized Sources - OpenReview, arxiv, etc.**
    This tier includes platforms used for advanced, targeted enrichment steps.

#### Enrichment Process

1.  **Query and Select Best Candidate:** For each paper, the pipeline queries external APIs and processes documents according to the hierarchy. For API sources, if multiple results are returned, it programmatically scores each "candidate" to select the most trustworthy match.

2.  **Implement a Conditional Update Policy:** The pipeline uses data to enrich the database field-by-field, strictly following the source hierarchy.
    * **Example of Hierarchy in Action:** You would trust the author name provided by DBLP (Tier 2) over any other source. However, you would use the LLM-Extracted PDF data (Tier 4) to fill in that author's institutional affiliation, as that information is typically absent from bibliographic APIs.
    * **Enriching Core Data:** `NULL` fields in the `Papers` table are filled in sequentially according to the source hierarchy.
    * **Storing External IDs:** All external identifiers from any source are managed through the `ExternalIdentifiers` table. The pipeline will not insert a new ID if an ID from that same source already exists.