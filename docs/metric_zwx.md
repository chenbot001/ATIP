很好，我们使用如下公式计算 Early Career Velocity (ECV)：

ECV = 前3年总引用数 / min(career_length, 3)

⸻

✅ 方法描述（标准化版本，可用于文档或论文）

Metric Name: Early Career Velocity (ECV)

Definition:
Early Career Velocity (ECV) quantifies the pace of a researcher’s academic impact during the initial stage of their career. It is defined as the total number of citations received by the researcher’s publications within the first three years of their academic career, divided by the effective early career duration.

Formula:
\text{ECV}{i} = \frac{\sum{\substack{p \in P_i \\ y_p \leq y_{start,i} + 2}} C_p}{\min(\text{career\_length}_i, 3)}

Where:
	•	i is the index of the researcher
	•	P_i is the set of all papers authored by researcher i
	•	y_{start,i} = Y_{now} - \text{career\_length}_i + 1 is the estimated start year of researcher i
	•	y_p is the publication year of paper p
	•	C_p is the citation count of paper p
	•	Y_{now} is the current year (e.g., 2025)

Data Required:
	•	career_length from author profile table
	•	Paper publication years and citation counts
	•	Authorship mappings between authors and papers

Interpretation:
Higher ECV indicates that the researcher had a fast start in their academic career in terms of research impact.

⸻


⸻



⸻

📘 Industry Collaboration Score (ICS) 方法描述（标准文档版）

Metric Name: Industry Collaboration Score (ICS)

Definition:
Industry Collaboration Score (ICS) quantifies the extent to which a researcher collaborates with industry-affiliated coauthors. It is defined as the proportion of a researcher’s total collaborations that are with coauthors from industry.

Formula:
\[
\text{ICS}i = \frac{\sum{j \in \mathcal{I}i} \text{num\collaborations}{ij}}{\sum{j \in \mathcal{C}_i} \text{num\collaborations}{ij}}
\]

Where:
	•	i is the target researcher
	•	\mathcal{C}_i is the set of all coauthors of researcher i
	•	\mathcal{I}_i \subset \mathcal{C}_i is the subset of coauthors affiliated with industry (based on most recent affiliation)
	•	\( \text{num\collaborations}{ij} \) is the number of collaborations between i and j

Industry affiliation identification:
A coauthor j is considered industry-affiliated if their latest recorded affiliation in author_history.csv contains one or more predefined industry keywords (e.g., “Google”, “Microsoft”, “Amazon”, “Meta”, “Alibaba”, “Tencent”, etc.).

Data Required:
	•	coauthors_by_author.csv: Contains coauthor relationships and number of collaborations
	•	author_history.csv: Contains historical affiliation data per author
	•	megatable_authors.csv: Contains core author information

Interpretation:
A higher ICS indicates stronger collaboration with industry researchers.


⸻



好的！以下是基于你确认采用的 方法 A（引用Z分数 + 奖项加成） 的完整内容：

⸻

📘 Breakthrough Paper Score (BPS) 方法说明（标准文档版）

Metric Name: Breakthrough Paper Score (BPS)

Definition:
Breakthrough Paper Score (BPS) quantifies whether a researcher has published any paper that significantly exceeds typical impact for its publication year, reflecting extraordinary influence or recognition. It is calculated based on the most “breakthrough-like” paper authored by a researcher, considering citation count relative to peers in the same year, and boosted by paper awards.

⸻

Formula:

Step 1: Calculate PaperScore for each paper

\text{PaperScore}_p = \text{ZScore}_p + \alpha \cdot \text{AwardBoost}_p
Where:
	•	\text{ZScore}p = \frac{C_p - \mu{y_p}}{\sigma_{y_p}}
C_p: citations of paper p
\mu_{y_p}, \sigma_{y_p}: mean and std of citations for papers published in year y_p
	•	\text{AwardBoost}_p is a categorical award score:
	•	Best Overall Paper: +3
	•	Outstanding Paper: +2
	•	Area Chair / Resource Paper / Other Thematic Awards: +1
	•	No award: 0

Step 2: Author-level Breakthrough Paper Score

\text{BPS}i = \max{p \in P_i} \text{PaperScore}_p

Step 3: Normalize

Normalize all BPS values linearly into a 0–100 range:
\text{NormalizedBPS}_i = 100 \cdot \frac{BPS_i - \min(BPS)}{\max(BPS) - \min(BPS)}

⸻

Data Required:
	•	megatable_papers.csv: includes paper_id, year, citation_count, awards
	•	paper_awards.csv: includes paper_id, award, category
	•	authorships.csv: maps author_id to paper_id
	•	megatable_authors.csv: includes author_id, first_name, last_name

⸻

Interpretation:
	•	High BPS: Author has published at least one unusually influential or highly recognized paper
	•	Low BPS: No such standout publication in available dataset

⸻
