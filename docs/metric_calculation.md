# Metric Documentation V3: 

## Time-weighted Author Citation Impact (TACI)

### 1. Core Idea 🎯
The **TACI** score is a composite metric designed to quantify a researcher's influence more accurately than raw citation counts. It moves beyond simple totals to reward **recent**, **high-velocity** research while fairly attributing credit based on **author contribution**. 

The final score is **normalized and scaled to a 0-100 range** to provide a stable, interpretable measure of an author's average publication impact, addressing issues of scale and publication volume bias.

---

### 2. Stepwise Algorithm ⚙️
The calculation is performed in four sequential steps.

#### **Step 1: Calculate Time-Weighted Paper Impact (`PaperImpact`)**
First, calculate a raw, time-aware impact score for each paper, representing the paper's total influence. This step remains unchanged.

**Formula:**
$$
\text{PaperImpact}(p) = \sum_{c \in C_p} \exp(-\lambda(T_{\text{current}} - T_{c})) \cdot \exp(-\mu(T_{c} - T_{p}))
$$

**Variable Elaboration:**
* `p`: An individual paper.
* $C_p$: The set of all citations received by paper `p`.
* $T_{\text{current}}$: The current year, set to `2025`.
* $T_c$: The year a specific citation `c` was made.
* $T_p$: The publication year of paper `p`.
* $\lambda$ (lambda): The **recency decay constant** (e.g., `0.1`). It discounts the value of older citations.
* $\mu$ (mu): The **velocity decay constant** (e.g., `0.2`). It rewards citations that occur shortly after publication.

---

#### **Step 2: Determine Author's Share of Credit (`AuthorShare`)**
Next, determine the proportional credit for each author on a paper based on their contribution order. This step remains unchanged.

**Formula:**
$$
\text{AuthorShare}(A, p) = \frac{W_{\text{pos}}(A, p)}{\sum_{B \in \text{AuthorsOf}(p)} W_{\text{pos}}(B, p)}
$$

**Variable Elaboration:**
* `A`: The specific author for whom we are calculating the score.
* `p`: The paper being analyzed.
* `AuthorsOf(p)`: The set of all authors for paper `p`.
* $W_{\text{pos}}(A, p)$: A numeric weight assigned to author `A` for paper `p` based on their position.
    * **First Author:** 1.0
    * **Last Author:** 0.8
    * **Middle Author:** 0.5

---

#### **Step 3: Calculate Average Impact per Paper (`TACI_avg`)**
Instead of a simple sum, we first calculate the author's average impact. This counters the bias towards authors with a high volume of publications and measures their typical impact density.

**Formula:**
$$
\text{TACI}_{\text{avg}}(A) = \frac{\sum_{p \in P_A} \text{AuthorShare}(A, p) \cdot \text{PaperImpact}(p)}{\text{Count of all papers by author } A}
$$

**Variable Elaboration:**
* `A`: The author whose score is being calculated.
* $P_A$: The set of all papers published by author `A`.

---

#### **Step 4: Normalize and Scale for Final TACI Score**
Finally, the average impact score is transformed and scaled to a 0-100 range. This involves a logarithmic transformation to handle the skewed distribution of impact scores, followed by Min-Max scaling to produce a final, interpretable score.

**Formula:**
$$
\text{TACI}(A) = \left( \frac{\ln(1 + \text{TACI}_{\text{avg}}(A))}{\ln(1 + \text{TACI}_{\text{avg}}^{\text{max}})} \right) \cdot 100
$$

**Variable Elaboration:**
* $\text{TACI}_{\text{avg}}(A)$: The author's average impact score from Step 3.
* $\ln(1+x)$: The natural log plus one function, used to compress the scale and handle scores of 0.
* $\text{TACI}_{\text{avg}}^{\text{max}}$: The maximum `TACI_avg` score observed across all authors in the dataset. This value is used to scale the final score to a relative 0-100 range.

---

### 3. Data Used 💾
| File | Columns Used | Purpose |
| :--- | :--- | :--- |
| `authorships.csv` | `author_id`, `paper_id`, `is_first_author`, `is_last_author` | Links authors to papers and determines author position. |
| `citation_details.csv` | `target_paper_id`, `year_cited` | Provides the timing for every citation event. |
| `megatable_papers.csv`| `paper_id`, `year` | Provides the publication year for each paper. |

---

### 4. Justification & Goal Alignment ✅
This methodology directly supports the ATIP project's goal to reliably identify high-potential researchers by moving beyond flat citation counts.

* **Addresses "Information Overload"**: By weighting citations by recency and velocity, the metric automatically surfaces researchers making a current impact.
* **Fixes Flawed Traditional Metrics**: The score accounts for authorship order and the context of *when* citations occurred. The new normalization process also corrects for publication volume bias.
* **Creates an Interpretable, Standardized Score**: The final 0-100 score is highly interpretable and standardized, making it easy to integrate into a composite "TalentScore" and compare researchers fairly. The normalization steps were specifically designed to handle the extreme scale and skewed distribution of raw citation data.

---

### 5. Complementary Metrics ➕
To create a more holistic "TalentScore", this metric should be used alongside other signals. The composite score proposed in the project overview could include:

* **Influence/Network Centrality**: A score based on the author's position within the co-authorship graph, such as their "influence distance" to key opinion leaders.
* **Momentum**: A score measuring the rate of change (first derivative) of the `TACI` score over the last 1-2 years, indicating a researcher's rising trajectory.
* **Independence**: A metric that measures an author's ability to publish high-impact work without their primary mentors or advisors, signaling research maturity.
---

## Citation Acceleration (CA)

### 1. Core Idea 🎯
The **Citation Acceleration (CA)** score measures a researcher's **momentum**. It identifies second-derivative trends by calculating the rate of change in their annual citation velocity. The methodology uses linear regression for a robust signal and applies Bayesian smoothing to ensure fairness for researchers at all career stages, especially new entrants with limited citation history.

---

### 2. Stepwise Algorithm ⚙️
The calculation is a three-step process to derive a stable momentum score.

#### **Step 1: Construct Annual Citation Velocity Profile (`V(y)`)**
For the target author, create a time series of their total citations per year.

1.  Identify all of the author's `paper_id`s from `authorships.csv`.
2.  From `citation_details.csv`, gather all citations for those papers.
3.  Group the citations by `year_cited` and sum them to get `V(y)`, the total citations received in year `y`.

---

#### **Step 2: Calculate Raw Acceleration (`m`) via Linear Regression**
Fit a line to the author's recent citation velocity to find the acceleration trend.

1.  Select the last `N` years of the velocity profile (e.g., `N=5`).
2.  **Edge Case Rule**: If the author has citation data for fewer than two years, their raw acceleration `m` is defined as **0**.
3.  Otherwise, perform a linear regression `V(t) = m \cdot t + b` on the `N` data points. The resulting slope, `m`, is the raw acceleration.

---

#### **Step 3: Apply Smoothing for Final Score**
Adjust the raw acceleration `m` using a smoothing formula to produce a fair, stable score.

**Formula:**
$$
\text{CA} = \frac{(N \cdot m) + (k \cdot m_{\text{prior}})}{N + k}
$$

**Variable Elaboration:**
* `N`: The number of years used for the regression (e.g., `5`).
* `m`: The author's raw acceleration (slope) from Step 2.
* `k`: A smoothing factor, representing the "weight" of the prior (e.g., `5`). It ensures that scores from sparse data are pulled towards the baseline.
* $m_{\text{prior}}$: The **neutral baseline**, representing the average acceleration of all researchers in the dataset. This makes the score relative to the typical momentum of the field. For now, this is the average for your NLP-focused dataset; in the future, it should be field-specific.

---

### 3. Data Used 💾
| File | Columns Used | Purpose |
| :--- | :--- | :--- |
| `authorships.csv` | `author_id`, `paper_id` | To link an author to all of their papers. |
| `citation_details.csv`| `target_paper_id`, `year_cited` | To build the annual citation velocity profile. |

---

### 4. Justification & Goal Alignment ✅
This metric is specifically designed to address the challenge of fairly capturing a researcher's recent momentum while accounting for new researchers.

* **Identifies Momentum**: The use of a slope over recent years directly measures acceleration, providing a clear signal of whether a researcher's impact is growing, shrinking, or holding steady.
* **Handles Sparse Data Gracefully**: The smoothing formula ensures that new researchers (for whom `N` is small) are not unfairly penalized or given volatile scores. Their score defaults to the neutral, field-wide baseline, representing a fair "wait-and-see" assessment until more data is available.
* **Provides Fair, Cross-Field Comparison**: By using a **field-specific baseline** (`m_prior`), the metric evaluates a researcher's momentum *relative to their own field's typical growth rate*. This is crucial because different fields have different dynamics; a "hot" field like NLP may have a higher baseline acceleration than a more mature field. This ensures the CA score is a context-aware and fair measure, especially when the platform expands to cover multiple research areas.
* **Robust**: Using linear regression over several years makes the metric resilient to a single "off" year, providing a more stable trendline than simple year-over-year comparisons.

---

### 5. Complementary Metrics ➕
This metric captures momentum and should be used alongside others to build a complete picture.

* **Network Centrality**: Measures an author's influence within the co-authorship graph, fulfilling the "People Graph" dimension of the ATIP project.
* **Award Recognition**: A count or weighted score of prestigious awards from `megatable_papers.csv`, which serves as a powerful external validation of a researcher's contributions.

---

## Research Quality: PQI & RQI

### 1. Core Idea 🎯
This framework measures research quality at two levels: the **Paper Quality Index (PQI)** for individual publications and the **Research Quality Index (RQI)** for authors. It gauges quality by blending signals from venue prestige, dynamic citation impact, and awards into a single, transparent score. The weighting of these signals is deliberately ordered to align with the platform's data-driven philosophy.

---

### 2. Stepwise Algorithm ⚙️
The process first scores each paper (PQI) and then aggregates these scores to the author level (RQI).

#### **Step 1: Calculate Paper Quality Index (PQI)**
The quality score for a single paper is a weighted sum of normalized scores from three components.

**Formula:**
$$
\text{PQI} = w_c \cdot S_c + w_a \cdot S_a + w_v \cdot S_v
$$

**Variable Elaboration:**
* $w_c, w_a, w_v$: The weights for Citation, Award, and Venue scores, respectively (must sum to 1). The recommended order of importance is $w_c > w_a > w_v$.
* $S_c, S_a, S_v$: The normalized scores (0-1 scale) for each component.
    * **$S_c$ (Citation Score)**: The time-weighted citation formula, normalized across all papers.
    * **$S_a$ (Award Score)**: A binary or weighted score based on the `awards` field in `megatable_papers.csv`.
    * **$S_v$ (Venue Score)**: A score based on venue tier. This should be as granular as the data allows.

**Refined Proposal for Venue Score ($S_v$):**
The `Venue Score` should be based on a `(Venue, Track)` combination to reflect that different tracks within the same conference carry different prestige. For example:
* **Tier S (1.0)**: Long Papers (Main Proceedings)
* **Tier A (0.8)**: Short Papers (Main Proceedings)
* **Tier B (0.5)**: Demo Papers
* **Tier C (0.4)**: Findings

**Implementation Note:** This refined `Venue Score` is dependent on the `track` column in `megatable_papers.csv`. As this column is currently empty, the immediate implementation will be limited to distinguishing between "Proceedings" and "Findings" based on the `venue` string. Populating the `track` data is a key priority for improving this metric.

---

#### **Step 2: Calculate Research Quality Index (RQI)**
An author's RQI is their average publication quality, weighted by their contribution to each paper.

**Formula:**
$$
\text{RQI} = \frac{\sum_{p \in P_A} \text{AuthorShare}(A, p) \cdot \text{PQI}(p)}{\sum_{p \in P_A} \text{AuthorShare}(A, p)}
$$

**Variable Elaboration:**
* `RQI`: The final quality score for author `A`.
* `PQI(p)`: The score for an individual paper `p` from Step 1.
* `AuthorShare(A, p)`: The contribution-weighted share (first/last author bonus) for author `A` on paper `p`.

---

### 3. Data Used 💾
| File | Columns Used | Purpose |
| :--- | :--- | :--- |
| `megatable_papers.csv` | `paper_id`, `venue`, `year`, `awards`, `track` | To get venue, track, timing, and award info. |
| `citation_details.csv`| `target_paper_id`, `year_cited` | To calculate the dynamic citation score. |
| `authorships.csv` | `author_id`, `paper_id`, `is_first_author`, `is_last_author`| To link papers and determine author share. |

---

### 4. Justification & Goal Alignment ✅
This methodology provides a nuanced quality score and a clear rationale for weighting the input signals.

* **Proposed Weighting Order (Citation > Award > Venue)**: The ordering is based on your platform's philosophy and current dataset.
    * **Citation Score (Primary Signal)**: This aligns perfectly with the goal of creating what "ai thinks of you", as it's a dynamic, purely data-driven signal of a paper's true influence over time.
    * **Award Score (Secondary Signal)**: This acts as a rare but powerful "gold standard" validation from human experts, confirming exceptional quality.
    * **Venue Score (Tertiary Signal)**: This is weighted lowest because your dataset currently consists of only top-tier NLP venues, making this factor less useful for differentiating between papers. It is a more static, pre-publication signal.

* **Framework Flexibility**: The weighted sum approach is transparent and allows for future tuning, such as learning the weights automatically from data as proposed in your project overview.

---

## Author Contribution

### 1. Core Idea 🎯
This suite of metrics quantifies an author's contribution style and impact by analyzing their role as a first or last author.

1.  **First Author Ratio (FAR)**: Measures the *frequency* with which an author takes the lead, first-author position.
2.  **First Author Impact (FAI)**: Measures the *impact* (via citations) that comes from their first-authored work, signaling their ability to drive impactful research.
3.  **Last Author Ratio (LAR)**: Measures the *frequency* with which an author takes the senior, last-author position.
4.  **Last Author Impact (LAI)**: Measures the *impact* that comes from their last-authored work, signaling their influence as a mentor or supervisor.

---

### 2. Stepwise Algorithm ⚙️

#### **First Author Metrics**
* **First Author Ratio (FAR)**:
    $$
    \text{FAR} = \frac{\text{Count of first-authored papers}}{\text{Total count of all papers}}
    $$
* **First Author Impact (FAI)**:
    $$
    \text{FAI} = \sum \text{Citations from first-authored papers}
    $$

#### **Last Author Metrics**
* **Last Author Ratio (LAR)**:
    $$
    \text{LAR} = \frac{\text{Count of last-authored papers}}{\text{Total count of all papers}}
    $$
* **Last Author Impact (LAI)**:
    $$
    \text{LAI} = \sum \text{Citations from last-authored papers}
    $$

---

### 3. Data Used 💾
| File | Columns Used | Purpose |
| :--- | :--- | :--- |
| `authorships.csv` | `author_id`, `paper_id`, `is_first_author`, `is_last_author` | To identify papers and flag first/last author status. |
| `megatable_papers.csv`| `paper_id`, `citation_count` | To get the total citation count for each paper. |

---

### 4. Justification & Goal Alignment ✅
Documenting all four metrics provides a comprehensive view of a researcher's career stage and contribution style.

* **FAR & FAI** measure an author's role as a **direct leader**. A high FAI is a powerful signal for identifying talent that can personally drive high-impact research. This is crucial for hiring committees seeking hands-on contributors.
* **LAR & LAI** measure an author's role as a **supervisor and mentor**. High LAR and LAI scores are characteristic of senior researchers and principal investigators. A high LAI, in particular, indicates that the author is successful at leading research groups that produce influential work.

---

## High/Low Impact: BPR & LIPR

### 1. Core Idea 🎯
The **Breakthrough Paper Ratio (BPR)** and **Low-Impact Paper Ratio (LIPR)** are a pair of metrics that analyze an author's publication record to determine the proportion of their work that is either very high-impact or demonstrably low-impact. By using year-normalized percentile rankings, they provide a fair assessment of an author's tendency to produce standout papers versus "watery papers", a core challenge your platform aims to address.

The final ratios are adjusted using **confidence-weighted smoothing** to provide a stable and fair assessment, especially for researchers with few publications.

---

### 2. Stepwise Algorithm ⚙️

The calculation is a three-step process.

#### **Step 1: Establish Annual Percentile Thresholds**
For each year available in the dataset, calculate the citation count thresholds for the 95th and 40th percentiles based on all papers published in that year.

* `T_95(y)` = 95th percentile citation count for year `y`.
* `T_40(y)` = 40th percentile citation count for year `y`.

#### **Step 2: Calculate Raw Author Ratios**
For a given author, classify each of their papers and then calculate the raw BPR and LIPR.

* **Breakthrough Paper Ratio (BPR)**: The proportion of an author's papers that are in the top 5% by citation count for their year.
    $$
    \text{BPR}_{\text{raw}} = \frac{\text{Count of papers with citations} > T_{95}(\text{year})}{\text{Total count of all papers}}
    $$

* **Low-Impact Publication Ratio (LIPR)**: The proportion of an author's papers that are in the bottom 40% by citation count for their year.
    $$
    \text{LIPR}_{\text{raw}} = \frac{\text{Count of papers with citations} < T_{40}(\text{year})}{\text{Total count of all papers}}
    $$

#### **Step 3: Apply Smoothing for Final Scores**
To account for statistical variance in authors with few papers, the raw ratios are adjusted using a smoothing formula. This ensures that a high ratio from a single paper is not given undue weight.

**Formulas:**
$$
\text{BPR}_{\text{smoothed}} = \frac{(N \cdot \text{BPR}_{\text{raw}}) + (k \cdot \text{BPR}_{\text{prior}})}{N + k}
$$
$$
\text{LIPR}_{\text{smoothed}} = \frac{(N \cdot \text{LIPR}_{\text{raw}}) + (k \cdot \text{LIPR}_{\text{prior}})}{N + k}
$$

**Variable Elaboration:**
* `N`: The author's **total paper count**.
* `k`: A **smoothing factor** or "confidence threshold" (e.g., `5`), representing the number of papers needed before the system "trusts" the raw ratio.
* $\text{BPR}_{\text{prior}}$ & $\text{LIPR}_{\text{prior}}$: The **neutral baseline**, which is the average BPR or LIPR across all authors in the dataset.

---

### 3. Data Used 💾
| File | Columns Used | Purpose |
| :--- | :--- | :--- |
| `megatable_papers.csv` | `paper_id`, `year`, `citation_count` | To establish annual percentile thresholds and get paper citations. |
| `authorships.csv` | `author_id`, `paper_id` | To link papers to the target author. |

---

### 4. Justification & Goal Alignment ✅
This pair of metrics provides a powerful, data-driven signal to address core challenges outlined in your project overview.

* **Addresses "Watery Papers"**: These metrics directly tackle the "surge of low-quality publications" by quantifying both ends of the impact spectrum, helping stakeholders differentiate genuine impact from mere publication volume.
* **Fairness Through Normalization**: By using year-normalized percentile rankings, the metrics ensure a fair comparison, evaluating papers against their direct contemporaries rather than against publications from different eras with different citation dynamics.
* **Handles Sparse Data Gracefully**: The final smoothing step ensures that new researchers are not unfairly penalized by a high LIPR (or rewarded by a high BPR) based on only one or two publications. Their scores are pulled towards a neutral average until they have a more substantial publication record.
* **Clarity and Interpretability**: The metrics are deliberately kept as simple ratios and are not weighted by co-author share. This provides a clear signal about an author's entire publication record.

---

## Network Growth Catalyst (NGC)

### 1. Core Idea 🎯
The **Network Growth Catalyst (NGC)** score is a second-order metric designed to measure an author's community-building ability. It moves beyond direct influence to quantify how effectively an author serves as a **broker or connector** who fosters new, independent collaborations among their co-authors. A high NGC score suggests the author's lab or project acts as a hub for creating future research partnerships.

---

### 2. Stepwise Algorithm ⚙️
The algorithm defines a "catalyzed" collaboration and then calculates a robust, smoothed score.

#### **Step 1: Define a "Catalyzed Collaboration"**
A collaboration between two researchers, **Author X** and **Author Y**, is considered "catalyzed" by a target, **Author A**, if it meets two strict conditions:
1.  **Independence**: The collaboration between X and Y must **not** include Author A on the author list.
2.  **Timing**: The collaboration must occur *after* both X and Y have already co-authored a paper with Author A.

#### **Step 2: Calculate Raw NGC Ratio (`NGC_raw`)**
1.  **Identify Community**: For target Author A, find all unique co-authors and their "first contact year".
2.  **Count Pairs**: Determine the total number of possible co-author pairs ($N_{\text{pairs}}$).
3.  **Count Catalyzed Collaborations**: For each pair, count the number of independent collaborations that occurred after their "introduction year."
4.  **Calculate Raw Ratio**:
    $$
    \text{NGC}_{\text{raw}} = \frac{\text{Total Catalyzed Collaborations}}{N_{\text{pairs}}}
    $$

#### **Step 3: Apply Smoothing for Final Score**
To account for the statistical instability of ratios from small networks, the raw score is adjusted using a confidence-weighted smoothing formula.

**Formula:**
$$
\text{NGC}_{\text{smoothed}} = \frac{(N_{\text{pairs}} \cdot \text{NGC}_{\text{raw}}) + (k \cdot \text{NGC}_{\text{prior}})}{N_{\text{pairs}} + k}
$$

**Variable Elaboration:**
* $N_{\text{pairs}}$: The **total number of co-author pairs**, which acts as the confidence weight.
* $k$: A **smoothing factor** (e.g., `20`), representing the number of pairs needed before the system "trusts" the raw ratio.
* $\text{NGC}_{\text{prior}}$: The **neutral baseline**, which is the average `NGC_raw` across all authors.

---

### 3. Data Used 💾
| File | Columns Used | Purpose |
| :--- | :--- | :--- |
| `authorships.csv` | `author_id`, `paper_id`, `author_name` | To build the co-author network and check author lists. |
| `megatable_papers.csv`| `paper_id`, `year` | To determine the timing of collaborations. |

---

### 4. Justification & Goal Alignment ✅
This metric provides a unique and powerful signal about a researcher's role within the scientific community.

* **Measures Structural Impact**: It moves beyond direct, first-order metrics to measure an author's second-order influence on the structure and growth of their research network.
* **Identifies True Leaders**: It helps identify key opinion leaders who act as force multipliers by building a stronger, more interconnected community.
* **Handles Sparse Data Gracefully**: The final smoothing step ensures the score is statistically robust, preventing authors with small networks from receiving misleadingly perfect scores based on a single successful connection.

---

### 5. Complementary Metrics ➕
NGC is most insightful when combined with other metrics that describe an author's role.

* **Last Author Impact (LAI)**: A high NGC score combined with a high LAI strongly suggests the author is a successful and influential supervisor whose lab is a nexus for new talent.
* **Research Quality Index (RQI)**: Can be used to analyze if the *new* collaborations being fostered are also high-quality, or if the author is simply connecting a large number of low-impact researchers.

---

## Talent Identification: Rising Stars & Visionaries

This suite of metrics identifies two distinct but equally valuable researcher archetypes: the **Rising Star**, who demonstrates immediate and accelerating impact, and the **Visionary**, whose older work shows foresight by becoming influential long after publication.

---
### 1. The Rising Star Metric

A "Rising Star" is a classification assigned to early-career researchers who show exceptional performance, combining both high momentum and high-quality current impact.

#### **Stepwise Algorithm**

1.  **Define the Cohort**: First, filter for authors who match an **"early-career profile."** This avoids relying on a potentially misleading `career_length` and instead uses a behavioral signature based on publication patterns within the dataset. An author must meet **ALL** of the following criteria:
    * **Low Publication Count**: Fewer than 10 papers.
    * **Low Last Author Ratio (LAR)**: Less than 25% of their papers as last author.
    * **High First Author Ratio (FAR)**: More than 50% of their papers as first author.

2.  **Calculate a `RisingStarScore`**: For each author in this filtered cohort, calculate a weighted score based on their momentum and current impact.
    $$
    \text{RisingStarScore} = (0.6 \cdot \text{CA}_{\text{norm}}) + (0.4 \cdot \text{TACI}_{\text{norm}})
    $$
    * **`CA_norm`**: The author's **Citation Acceleration (CA)** score, normalized to a 0-1 scale *within the early-career cohort*.
    * **`TACI_norm`**: The author's **Time-weighted Author Citation Impact (TACI)** score, normalized to a 0-1 scale within the cohort. This TACI score must be calculated using specific parameters to capture "current buzz":
        * **High Lambda (`λ`)**: e.g., >= 0.6.
        * **High Mu (`μ`)**: e.g., >= 0.6.

3.  **Classify**: Researchers in the cohort who rank in the **top 5%** by `RisingStarScore` are flagged as "Rising Stars".

---
### 2. The Visionary Metric

A "Visionary" is a researcher whose older work was ahead of its time and is now gaining significant traction. This metric is specifically designed to identify these "sleeping beauty" papers and credit their authors.

#### **Stepwise Algorithm**

1.  **Calculate `VisionaryPaperImpact (VPI)`**: For each paper, calculate its "visionary impact" score. This formula actively rewards recent citations to older papers.
    $$\text{VPI}(p) = \sum_{c \in C_p} \underbrace{\left( e^{-\lambda(T_{\text{current}} - T_{c})} \right)}_{\text{Recency Factor}} \cdot \underbrace{\left( 1 - e^{-\mu_{\text{visionary}}(T_{c} - T_{p})} \right)}_{\text{Foresight Factor}}$$
    * **Recency Factor**: The first term finds citations that are happening **now**. A high `λ` is used.
    * **Foresight Factor**: The second term actively rewards a **long time gap** between publication (`T_p`) and citation (`T_c`).

2.  **Calculate Author-Level `VisionaryScore`**: An author's final score is the average `VPI` across all their publications, weighted by their contribution share.
    $$
    \text{VisionaryScore} = \frac{\sum_{p \in P_A} \text{AuthorShare}(A, p) \cdot \text{VPI}(p)}{\sum_{p \in P_A} \text{AuthorShare}(A, p)}
    $$

---
### 3. Data Used 💾
| File | Columns Used | Purpose |
| :--- | :--- | :--- |
| `authorships.csv` | `author_id`, `is_first_author`, `is_last_author` | To calculate FAR and LAR for the Rising Star cohort filter. |
| (Data for TACI & CA) | (As previously documented) | To calculate the components of the `RisingStarScore`. |
| (Data for VPI) | (As previously documented) | To calculate the `VisionaryScore`. |

---
### 4. Justification & Goal Alignment ✅
This pair of metrics allows the platform to tell a more nuanced story about talent.

* **Robust Cohort Identification**: The new multi-factor filter for Rising Stars creates a much more reliable cohort by using a behavioral signature (publication patterns) rather than relying on a single, potentially flawed data point (`career_length`).
* **Identifies Different Success Patterns**: The framework acknowledges that impact can be immediate (Rising Star) or delayed (Visionary), providing a richer analysis than a single impact score.
* **Data-Driven Personas**: These metrics provide a clear, quantifiable methodology for the "Researcher Personas" feature, grounding them in transparent analysis.

---

## Talent Identification: Rising Star Magnet

### 1. Core Idea 🎯
The **Rising Star Magnet (RSM)** metric is a second-order metric that measures a researcher's (typically senior) ability to identify, attract, and collaborate with talented researchers **early** in their careers. It moves beyond an author's individual success to quantify their influence as a talent scout and mentor. To ensure fairness and statistical robustness, the final score is adjusted using **confidence-weighted smoothing**, which prevents bias from authors with very small collaboration networks.

---

### 2. Stepwise Algorithm ⚙️
The calculation uses the "Rising Star" classification as a prerequisite, attributes points, and then applies a smoothing formula for a robust final score.

#### **Step 1: Prerequisite - Generate "Rising Star" List**
First, run the "Rising Star" analysis to generate a definitive list of all authors who are currently classified as Rising Stars.

#### **Step 2: Attribute "Magnet Points"**
This process is best performed by starting with the Rising Stars and working backward.
1.  For each "Rising Star" on the list, find all of their unique co-authors.
2.  For each co-author, determine the year of their first collaboration with the Rising Star.
3.  If this first collaboration occurred within the **first 3 years** of the Rising Star's career, award **one "magnet point"** to that co-author.

#### **Step 3: Calculate Raw RSM Ratio (`RSM_raw`)**
First, a raw "talent-spotting efficiency" ratio is calculated by normalizing the points by the size of the author's network. This ratio, however, is statistically unstable for authors with few collaborators.
$$
\text{RSM}_{\text{raw}} = \frac{\text{Total "magnet points"}}{\text{Total number of unique co-authors}}
$$

#### **Step 4: Apply Smoothing for Final Score**
To correct for statistical instability, the raw ratio is adjusted using a smoothing formula. This prevents authors with a single lucky collaboration from achieving a perfect but misleading score by pulling the metric for low-confidence authors towards a neutral average.

**Formula:**
$$
\text{RSM}_{\text{smoothed}} = \frac{(N \cdot \text{RSM}_{\text{raw}}) + (k \cdot \text{RSM}_{\text{prior}})}{N + k}
$$

**Variable Elaboration:**
* `$N$`: The author's **total number of unique co-authors**, which acts as the confidence weight.
* `$\text{RSM}_{\text{raw}}$`: The author's raw efficiency ratio from Step 3.
* `$k$`: A **smoothing factor** or "confidence threshold" (e.g., `10`), representing the number of collaborators needed before the system "trusts" the raw ratio.
* `$\text{RSM}_{\text{prior}}$`: The **neutral baseline**, which is the average `$\text{RSM}_{\text{raw}}$` across all authors in the dataset.

---

### 3. Data Used 💾
| File | Columns Used | Purpose |
| :--- | :--- | :--- |
| `authorships.csv` | `author_id`, `paper_id` | To find all co-authors for a given author. |
| `megatable_papers.csv`| `paper_id`, `year` | To determine the timing of collaborations. |
| (Data for Rising Star)| (As previously documented) | Required to generate the prerequisite list of Rising Stars. |

---

### 4. Justification & Goal Alignment ✅
This metric provides deep insight into the ecosystem of talent development within a research field.

* **Identifies Key Mentors**: It provides a data-driven method to identify influential professors and lab leaders who are exceptionally good at spotting and nurturing emerging talent.
* **Second-Order Influence**: Like the NGC metric, it measures a researcher's second-order impact, aligning perfectly with the "people-centred networks" dimension of your project.
* **Forward-Looking Signal**: A lab or institution with a high number of "Rising Star Magnets" is likely to be a hub of future innovation.
* **Handles Sparse Data Gracefully**: The final smoothing step ensures the score is statistically robust. It prevents authors with very few collaborators from receiving misleadingly high scores based on a single successful collaboration, pulling their score towards a neutral average until they have a more substantial collaboration history. This makes the metric fair for researchers at all career stages.

---

### 5. Complementary Metrics ➕
This metric is most powerful when viewed alongside metrics that describe a senior researcher's own work.

* **Last Author Impact (LAI)**: A high RSM score combined with a high LAI is a definitive sign of a top-tier Principal Investigator who not only supervises impactful work but also attracts the best new talent to their group.
* **Network Growth Catalyst (NGC)**: A researcher with high scores in both RSM and NGC is a true community builder—they not only attract new talent but are also skilled at connecting that talent to form a stronger, more collaborative research ecosystem.