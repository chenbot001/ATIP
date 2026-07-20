#!/usr/bin/env python3
import subprocess
import sys
import importlib

def install_missing_packages():
    required_packages = [
        "pandas>=2.0",
        "requests",
        "backoff",
        "tqdm", 
        "python-dotenv",
        "openai>=1.0.0"
    ]
    
    for package in required_packages:
        package_name = package.split(">=")[0].split("==")[0]
        try:
            importlib.import_module(package_name.replace("-", "_"))
        except ImportError:
            print(f"Installing {package}...")
            subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", package])

install_missing_packages()

import os
import json
import gzip
import base64
import logging
import time
import threading
import sys
import re
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlparse
import pandas as pd
import requests
import backoff
from tqdm import tqdm
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

INPUT_CSV = "data/database/linkedIn_profiles_test150_serpapi.csv"  
OUTPUT_CSV = "LinkedIn/authors_LinkedIn_verified_150.csv"

BRIGHTDATA_TOKEN = os.getenv("BRIGHTDATA_TOKEN")
BRIGHTDATA_DATASET_ID = os.getenv("BRIGHTDATA_DATASET_ID")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

if not BRIGHTDATA_TOKEN:
    print("Error: BRIGHTDATA_TOKEN environment variable is required")
    sys.exit(1)

if not OPENAI_API_KEY:
    print("Error: OPENAI_API_KEY environment variable is required")
    sys.exit(1)

# 初始化OpenAI客户端
client = OpenAI(api_key=OPENAI_API_KEY)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class ProgressTracker:
    def __init__(self):
        self.lock = threading.Lock()
        self.success_count = 0
        self.error_count = 0
        self.skipped_count = 0
        
    def increment_success(self):
        with self.lock:
            self.success_count += 1
            
    def increment_error(self):
        with self.lock:
            self.error_count += 1
            
    def increment_skipped(self):
        with self.lock:
            self.skipped_count += 1

progress_tracker = ProgressTracker()

@backoff.on_exception(backoff.expo,
                      (requests.HTTPError, requests.Timeout),
                      max_tries=5, jitter=None)
def fetch_linkedin_profiles_batch(urls: list) -> list:
    """调用 Bright Data LinkedIn Dataset API 批量获取 JSON"""
    trigger_url = "https://api.brightdata.com/datasets/v3/trigger"
    headers = {
        "Authorization": f"Bearer {BRIGHTDATA_TOKEN}",
        "Content-Type": "application/json",
    }
    params = {
        "dataset_id": BRIGHTDATA_DATASET_ID,
        "include_errors": "true",
    }
    data = [{"url": url} for url in urls]
    
    # 1. 触发数据集
    logger.info(f"触发Bright Data API，处理 {len(urls)} 个URL")
    r = requests.post(trigger_url, headers=headers, params=params, json=data, timeout=60)
    r.raise_for_status()
    
    response_data = r.json()
    snapshot_id = response_data.get('snapshot_id')
    
    if not snapshot_id:
        logger.error(f"未获取到snapshot_id: {response_data}")
        return []
    
    logger.info(f"获得快照ID: {snapshot_id}")
    
    # 2. 等待快照完成
    snapshot_url = f"https://api.brightdata.com/datasets/v3/snapshot/{snapshot_id}"
    max_wait = 300  # 最多等待5分钟
    wait_time = 0
    
    while wait_time < max_wait:
        time.sleep(10)
        wait_time += 10
        
        try:
            snapshot_response = requests.get(snapshot_url, headers={"Authorization": f"Bearer {BRIGHTDATA_TOKEN}"}, timeout=60)
            
            if snapshot_response.status_code == 202:
                logger.info(f"快照处理中... ({wait_time}s)")
                continue
            elif snapshot_response.status_code == 200:
                # 数据已准备好，解析JSONL
                text_data = snapshot_response.text
                lines = text_data.strip().split('\n')
                json_objects = []
                
                for line in lines:
                    if line.strip():
                        try:
                            json_objects.append(json.loads(line))
                        except json.JSONDecodeError as e:
                            logger.warning(f"JSON解析错误: {e}, 行: {line[:100]}")
                
                logger.info(f"成功解析 {len(json_objects)} 个LinkedIn档案")
                return json_objects
            else:
                logger.error(f"快照状态检查失败: {snapshot_response.status_code} - {snapshot_response.text}")
                break
                
        except Exception as e:
            logger.error(f"快照状态检查错误: {e}")
            break
    
    logger.error(f"快照等待超时 ({max_wait}s)")
    return []

@backoff.on_exception(backoff.expo,
                      (requests.HTTPError, requests.Timeout),
                      max_tries=5, jitter=None)
def fetch_linkedin_profile(url: str) -> dict:
    """调用 Bright Data LinkedIn Dataset API 获取单个 JSON"""
    profiles = fetch_linkedin_profiles_batch([url])
    return profiles[0] if profiles else {}

def verify_profile_openai(author_name, affiliation, profile):
    """更智能的LinkedIn档案验证，充分利用所有JSON信息"""
    
    # 输入验证
    if not isinstance(profile, dict):
        logger.warning(f"Profile不是字典类型: {type(profile)}")
        return {"match": False, "confidence": 0.0, "reason": "invalid_profile_data_type"}
    
    if not author_name or not affiliation:
        logger.warning("缺少必要的作者姓名或机构信息")
        return {"match": False, "confidence": 0.0, "reason": "missing_author_or_affiliation"}
    
    # 提取所有可能的信息源
    current_company = profile.get("current_company", {})
    if isinstance(current_company, dict):
        current_company_name = current_company.get("name") or ""
        current_position_title = current_company.get("title") or ""
    else:
        current_company_name = ""
        current_position_title = ""
    
    # 安全处理experience和education
    experience = profile.get("experience") or []
    if not isinstance(experience, list):
        experience = []
    
    education = profile.get("education") or []
    if not isinstance(education, list):
        education = []
    
    # 构建完整的档案信息，不遗漏任何细节
    comprehensive_profile = {
        "basic_info": {
            "name": profile.get("name"),
            "headline": profile.get("headline"),
            "location": profile.get("location") or profile.get("city"),
            "summary": profile.get("summary", "")
        },
        "current_position": {
            "title": current_position_title,
            "company": current_company_name
        },
        "all_work_experience": [],
        "all_education": [],
        "additional_fields": {
            "educations_details": profile.get("educations_details", ""),
            "position": profile.get("position", ""),
            "about": profile.get("about", ""),
            "description": profile.get("description", "")
        }
    }
    
    # 收集所有工作经历
    for exp in experience:
        if isinstance(exp, dict):
            work_entry = {
                "title": exp.get("title") or "",
                "company": exp.get("company") or "",
                "start_date": exp.get("start_date", ""),
                "end_date": exp.get("end_date", ""),
                "duration": exp.get("duration", ""),
                "description": exp.get("description", "")
            }
            comprehensive_profile["all_work_experience"].append(work_entry)
    
    # 收集所有教育经历
    for edu in education:
        if isinstance(edu, dict):
            edu_entry = {
                "degree": edu.get("degree") or "",
                "field": edu.get("field") or "",
                "school": edu.get("school") or edu.get("title") or "",
                "start_year": edu.get("start_year", ""),
                "end_year": edu.get("end_year", ""),
                "description": edu.get("description", "")
            }
            comprehensive_profile["all_education"].append(edu_entry)

    # 扩展的大学映射表
    university_mappings = {
        # 新加坡高校
        "sutd": "singapore university of technology and design",
        "nus": "national university of singapore", 
        "ntu": "nanyang technological university",
        "smu": "singapore management university",
        "sit": "singapore institute of technology",
        "suss": "singapore university of social sciences",
        
        # 美国高校
        "mit": "massachusetts institute of technology",
        "stanford": "stanford university",
        "cmu": "carnegie mellon university",
        "ucb": "university of california berkeley",
        "ucla": "university of california los angeles",
        "usc": "university of southern california",
        "gatech": "georgia institute of technology",
        "caltech": "california institute of technology",
        "cornell": "cornell university",
        "princeton": "princeton university",
        "harvard": "harvard university",
        "yale": "yale university",
        "columbia": "columbia university",
        "upenn": "university of pennsylvania",
        "brown": "brown university",
        "dartmouth": "dartmouth college",
        "duke": "duke university",
        "uiuc": "university of illinois urbana-champaign",
        "umich": "university of michigan",
        "uw": "university of washington",
        "utexas": "university of texas at austin",
        "ucsb": "university of california santa barbara",
        "ucsd": "university of california san diego",
        "uci": "university of california irvine",
        "ucsc": "university of california santa cruz",
        
        # 中国高校
        "tsinghua": "tsinghua university",
        "peking": "peking university",
        "pku": "peking university",
        "thu": "tsinghua university",
        
        # 香港高校
        "hku": "university of hong kong",
        "cuhk": "chinese university of hong kong",
        "hkust": "hong kong university of science and technology",
        
        # 欧洲高校
        "eth": "eth zurich",
        "epfl": "école polytechnique fédérale de lausanne",
        "tu delft": "delft university of technology",
        "tu munich": "technical university of munich",
        "rwth": "rwth aachen university",
        "ku leuven": "ku leuven",
        "tu berlin": "technical university of berlin",
        "tu vienna": "vienna university of technology",
        
        # 澳大利亚高校
        "uow": "university of wollongong",
        "wollongong": "university of wollongong",
        "unsw": "university of new south wales",
        "usyd": "university of sydney",
        "umelb": "university of melbourne",
        "anu": "australian national university",
        "uq": "university of queensland",
        "monash": "monash university",
        "uwa": "university of western australia",
        "adelaide": "university of adelaide",
        "uts": "university of technology sydney",
        "rmit": "rmit university",
        "deakin": "deakin university",
        "griffith": "griffith university",
        "qut": "queensland university of technology",
        "curtin": "curtin university",
        
        # 亚洲其他高校
        "kaist": "korea advanced institute of science and technology",
        "snu": "seoul national university",
        "tokyo": "university of tokyo",
        "kyoto": "kyoto university",
        "iit": "indian institute of technology",
        "iisc": "indian institute of science"
    }

    # 更加智能和全面的验证提示
    prompt = f"""
You are an expert academic profile validator with deep knowledge of global universities and academic career patterns. Your task is to determine if a LinkedIn profile matches an expected academic researcher profile.

**CRITICAL INSTRUCTION: Use ALL available information from the LinkedIn profile. Academic researchers often have complex career paths with multiple affiliations.**

Expected Profile:
- Author Name: "{author_name}"
- Expected Affiliation: "{affiliation}"

Complete LinkedIn Profile Data:
```json
{json.dumps(comprehensive_profile, ensure_ascii=False, indent=2)}
```

University Name Mapping Reference:
{json.dumps(university_mappings, ensure_ascii=False, indent=2)}

**ENHANCED VALIDATION CRITERIA:**

1. **NAME MATCHING (Flexible):**
   - Consider name variations, cultural differences, nicknames
   - Accept partial matches if core components align
   - Account for different name orders (first/last, family/given)

2. **AFFILIATION MATCHING (Comprehensive):**
   - Check EVERY source: current position, ALL work history, ALL education history, additional fields
   - Use university mappings to match abbreviations with full names
   - Consider ANY historical connection as valid (current OR past positions)
   - Academic careers involve multiple institutions - ANY connection counts
   - Look for semantic equivalence and partial matches
   - Department/school affiliations within universities are valid matches

3. **ACADEMIC CONTEXT UNDERSTANDING:**
   - Researchers frequently move between institutions
   - PhD/education affiliations are as important as employment
   - Visiting positions, collaborations, and joint appointments are common
   - Multiple simultaneous affiliations are normal in academia
   - Historical connections often remain relevant for publications

4. **EVIDENCE PRIORITIZATION:**
   - ANY mention of the expected institution is significant
   - Education history is equally important as work history
   - Consider research collaborations and academic networks
   - Look for institution mentions in descriptions, summaries, etc.

5. **CONFIDENCE SCORING:**
   - 0.9-1.0: Strong name match + clear institutional connection (current OR historical)
   - 0.7-0.9: Good name match + reasonable institutional evidence
   - 0.5-0.7: Partial matches with supporting evidence
   - 0.3-0.5: Weak connections or ambiguous data
   - 0.0-0.3: Clear mismatches or insufficient information

**EXAMPLES OF POSITIVE MATCHES:**
- Expected: "Nanyang Technological University" → Found: "NTU" or "Research Scientist at NTU" (even if currently elsewhere)
- Expected: "University of Michigan" → Found: "PhD from UMich" or "Ann Arbor" location
- Expected: "SUTD" → Found: "Singapore University of Technology and Design" in ANY context

**KEY PRINCIPLE: If there is ANY credible connection between the person and the expected institution (through work, education, collaboration, etc.), consider it a match. Academic careers are fluid and multi-institutional.**

Respond ONLY in valid JSON format:
{{
    "match": true/false,
    "confidence": 0.0-1.0,
    "reason": "detailed explanation with specific evidence from the profile"
}}
"""
    
    # 调用OpenAI API
    for attempt in range(3):
        try:
            response = client.chat.completions.create(
                model=OPENAI_MODEL,
                messages=[
                    {"role": "system", "content": "You are an expert academic profile validator. Always respond in valid JSON format and consider the comprehensive nature of academic careers."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
                max_tokens=300,
                timeout=20
            )
            
            txt = response.choices[0].message.content.strip()
            
            # 清理响应格式
            if txt.startswith("```json"):
                txt = txt.replace("```json", "").replace("```", "").strip()
            elif txt.startswith("```"):
                txt = txt.replace("```", "").strip()
            
            # 解析JSON
            result = json.loads(txt)
            
            # 验证返回结果
            if not isinstance(result, dict) or "match" not in result or "confidence" not in result or "reason" not in result:
                raise ValueError("Missing required fields in response")
            
            # 确保confidence在有效范围内
            result["confidence"] = max(0.0, min(1.0, float(result["confidence"])))
            
            logger.info(f"✅ 增强验证成功: {result}")
            return result
            
        except json.JSONDecodeError as e:
            logger.warning(f"❌ JSON解析错误 (尝试 {attempt+1}): {str(e)}")
            if attempt < 2:
                time.sleep(2)
                
        except Exception as e:
            logger.warning(f"❌ OpenAI错误 (尝试 {attempt+1}): {str(e)[:100]}...")
            if attempt < 2:
                time.sleep(2)
    
    logger.error("🚫 所有OpenAI API尝试失败")
    
    # 基于简单的字符串匹配给出基础判断
    try:
        simple_match = simple_profile_verification(author_name, affiliation, profile)
        return simple_match
    except:
        return {"match": False, "confidence": 0.0, "reason": "openai_api_failed_and_fallback_failed"}

def simple_profile_verification(author_name, affiliation, profile):
    """简单的profile验证作为fallback"""
    
    # 基础姓名匹配
    profile_name = (profile.get("name") or "").lower()
    author_name_lower = author_name.lower()
    
    # 检查姓名匹配
    name_words = author_name_lower.split()
    profile_words = profile_name.split()
    
    name_match_count = 0
    for word in name_words:
        if len(word) > 2 and any(word in pword for pword in profile_words):
            name_match_count += 1
    
    name_match_ratio = name_match_count / len(name_words) if name_words else 0
    
    if name_match_ratio < 0.5:
        return {"match": False, "confidence": 0.0, "reason": "name_mismatch_in_fallback"}
    
    # 基础机构匹配
    affiliation_lower = affiliation.lower()
    
    # 检查所有可能的字段
    search_fields = [
        profile.get("headline", ""),
        profile.get("position", ""),
        profile.get("educations_details", "")
    ]
    
    # 添加工作经历
    experience = profile.get("experience", [])
    for exp in experience:
        if isinstance(exp, dict):
            search_fields.append(exp.get("company", ""))
    
    # 添加教育经历
    education = profile.get("education", [])
    for edu in education:
        if isinstance(edu, dict):
            search_fields.append(edu.get("school", ""))
            search_fields.append(edu.get("title", ""))
    
    # 检查是否有匹配
    affiliation_found = False
    for field in search_fields:
        field_lower = str(field).lower()
        if any(word in field_lower for word in affiliation_lower.split() if len(word) > 3):
            affiliation_found = True
            break
    
    if affiliation_found:
        confidence = 0.6 if name_match_ratio > 0.8 else 0.4
        return {"match": True, "confidence": confidence, "reason": "simple_string_matching_success"}
    else:
        return {"match": False, "confidence": 0.1, "reason": "no_affiliation_match_in_fallback"}

def is_valid_linkedin_url(url):
    if not url or pd.isna(url):
        return False
    try:
        parsed = urlparse(str(url))
        return "linkedin.com" in parsed.netloc and "/in/" in parsed.path
    except:
        return False

def compress_and_encode(data):
    json_str = json.dumps(data, ensure_ascii=False)
    compressed = gzip.compress(json_str.encode('utf-8'))
    return base64.b64encode(compressed).decode('ascii')

def process_row(row_data):
    idx, row = row_data
    author_name = row.get('Author Name') or row.get('author_name', '')
    affiliation = row.get('Affiliation') or row.get('affiliation', '')
    linkedin_url = row.get('LinkedIn_URL', '')
    
    result = {
        'profile_json': '',
        'llm_match': False,
        'llm_confidence': 0.0,
        'llm_reason': '',
        'fetch_status': 'skipped'
    }
    
    if not is_valid_linkedin_url(linkedin_url):
        result['llm_reason'] = 'invalid_or_empty_url'
        progress_tracker.increment_skipped()
        return idx, result
    
    try:
        profile_data = fetch_linkedin_profile(linkedin_url)
        
        if not profile_data or not isinstance(profile_data, dict):
            result['fetch_status'] = 'empty'
            result['llm_reason'] = 'empty_or_invalid_profile_data'
            progress_tracker.increment_error()
            return idx, result
        
        result['profile_json'] = compress_and_encode(profile_data)
        
        verification = verify_profile_openai(author_name, affiliation, profile_data)
        result['llm_match'] = verification.get('match', False)
        result['llm_confidence'] = verification.get('confidence', 0.0)
        result['llm_reason'] = verification.get('reason', '')
        result['fetch_status'] = 'success'
        
        progress_tracker.increment_success()
        
    except TypeError as e:
        result['fetch_status'] = 'error'
        result['llm_reason'] = f'verification_error_TypeError'
        progress_tracker.increment_error()
        logger.error(f"TypeError在验证 {linkedin_url}: {e}")
        
    except requests.HTTPError as e:
        result['fetch_status'] = 'http_error'
        result['llm_reason'] = f'http_error_{e.response.status_code}'
        progress_tracker.increment_error()
        logger.warning(f"HTTP error for {linkedin_url}: {e}")
        
    except Exception as e:
        result['fetch_status'] = 'error'
        result['llm_reason'] = f'error_{type(e).__name__}'
        progress_tracker.increment_error()
        logger.error(f"Error processing {linkedin_url}: {e}")
    
    return idx, result

def process_batch(batch_data):
    """Process a batch of rows using the batch API"""
    batch_urls = []
    batch_indices = []
    
    for idx, row in batch_data:
        linkedin_url = row.get('LinkedIn_URL', '')
        if is_valid_linkedin_url(linkedin_url):
            batch_urls.append(linkedin_url)
            batch_indices.append(idx)
    
    if not batch_urls:
        # Process individually for invalid URLs
        return [process_row(row_data) for row_data in batch_data]
    
    try:
        # Fetch all profiles in batch
        profiles_data = fetch_linkedin_profiles_batch(batch_urls)
        
        results = []
        
        for i, (idx, row) in enumerate(batch_data):
            author_name = row.get('Author Name') or row.get('author_name', '')
            affiliation = row.get('Affiliation') or row.get('affiliation', '')
            linkedin_url = row.get('LinkedIn_URL', '')
            
            result = {
                'profile_json': '',
                'llm_match': False,
                'llm_confidence': 0.0,
                'llm_reason': '',
                'fetch_status': 'skipped'
            }
            
            if not is_valid_linkedin_url(linkedin_url):
                result['llm_reason'] = 'invalid_or_empty_url'
                progress_tracker.increment_skipped()
                results.append((idx, result))
                continue
            
            # Find corresponding profile data by URL matching
            profile_data = None
            
            # 尝试多种匹配方式
            for profile in profiles_data:
                profile_id = profile.get('id', '')
                profile_name = profile.get('name', '').lower()
                
                # 方式1: 通过profile id匹配URL
                if profile_id and profile_id in linkedin_url:
                    profile_data = profile
                    logger.info(f"✅ URL匹配成功 (ID): {profile_id} -> {linkedin_url}")
                    break
                
                # 方式2: 通过姓名匹配 (备用)
                author_name_clean = author_name.lower().replace(' ', '-')
                if profile_name and author_name_clean in profile_name.replace(' ', '-'):
                    profile_data = profile
                    logger.info(f"✅ 姓名匹配成功: {profile_name} -> {author_name}")
                    break
            
            if not profile_data:
                # 调试信息：显示所有可用的profile
                logger.warning(f"❌ 无法匹配 {linkedin_url}")
                logger.warning(f"   期望作者: {author_name}")
                logger.warning(f"   可用profiles: {[p.get('id', 'no-id') + '|' + p.get('name', 'no-name') for p in profiles_data]}")
                
                result['fetch_status'] = 'empty'
                result['llm_reason'] = 'profile_not_found_in_batch'
                progress_tracker.increment_error()
                results.append((idx, result))
                continue
                
            try:
                result['profile_json'] = compress_and_encode(profile_data)
                
                verification = verify_profile_openai(author_name, affiliation, profile_data)
                result['llm_match'] = verification.get('match', False)
                result['llm_confidence'] = verification.get('confidence', 0.0)
                result['llm_reason'] = verification.get('reason', '')
                result['fetch_status'] = 'success'
                
                progress_tracker.increment_success()
                
            except Exception as e:
                result['fetch_status'] = 'error'
                result['llm_reason'] = f'verification_error_{type(e).__name__}'
                progress_tracker.increment_error()
                logger.error(f"Error verifying profile for {linkedin_url}: {e}")
            
            results.append((idx, result))
        
        return results
        
    except Exception as e:
        logger.error(f"Batch processing error: {e}")
        # Fall back to individual processing
        return [process_row(row_data) for row_data in batch_data]

def save_dataframe(df, filename):
    df.to_csv(filename, index=False, encoding='utf-8')
    logger.info(f"Saved progress to {filename}")

def main():
    if not os.path.exists(INPUT_CSV):
        logger.error(f"Input file {INPUT_CSV} not found")
        sys.exit(1)
    
    df = pd.read_csv(INPUT_CSV)
    
    required_columns = ['Author Name', 'Affiliation', 'LinkedIn_URL']
    alt_columns = ['Author Name', 'Affiliation', 'LinkedIn_URL']
    
    missing_cols = []
    for req_col, alt_col in zip(required_columns, alt_columns):
        if req_col not in df.columns and alt_col not in df.columns:
            missing_cols.append(f"{req_col} (or {alt_col})")
    
    if missing_cols:
        logger.error(f"Missing required columns: {missing_cols}")
        sys.exit(1)
    
    new_columns = ['profile_json', 'llm_match', 'llm_confidence', 'llm_reason', 'fetch_status']
    for col in new_columns:
        if col not in df.columns:
            df[col] = ''
    
    existing_output = None
    if os.path.exists(OUTPUT_CSV):
        try:
            existing_output = pd.read_csv(OUTPUT_CSV)
            logger.info(f"Found existing output file with {len(existing_output)} rows")
        except Exception as e:
            logger.warning(f"Could not read existing output file: {e}")
    
    rows_to_process = []
    for idx, row in df.iterrows():
        if existing_output is not None and idx < len(existing_output):
            existing_status = existing_output.iloc[idx].get('fetch_status', '')
            if existing_status == 'success':
                continue
        rows_to_process.append((idx, row))
    
    if not rows_to_process:
        logger.info("All rows already processed successfully")
        return
    
    logger.info(f"Processing {len(rows_to_process)} rows out of {len(df)} total")
    
    results = {}
    last_save_time = time.time()
    
    # Process in batches of 5 for better efficiency with API limits
    batch_size = 5
    batches = [rows_to_process[i:i + batch_size] for i in range(0, len(rows_to_process), batch_size)]
    
    with ThreadPoolExecutor(max_workers=2) as executor:  # Reduced workers for better stability
        with tqdm(total=len(rows_to_process), desc="Processing") as pbar:
            # Submit batch jobs
            futures = {executor.submit(process_batch, batch): batch for batch in batches}
            
            for future in futures:
                try:
                    batch_results = future.result()
                    
                    for idx, result in batch_results:
                        results[idx] = result
                        
                        for col, value in result.items():
                            df.at[idx, col] = value
                        
                        pbar.update(1)
                        pbar.set_postfix({
                            'Success': progress_tracker.success_count,
                            'Error': progress_tracker.error_count,
                            'Skipped': progress_tracker.skipped_count
                        })
                    
                    current_time = time.time()
                    if (len(results) % 100 == 0) or (current_time - last_save_time > 300):
                        save_dataframe(df, OUTPUT_CSV)
                        last_save_time = current_time
                        
                except Exception as e:
                    logger.error(f"Batch execution error: {e}")
                    # Fall back to individual processing for this batch
                    batch = futures[future]
                    for row_data in batch:
                        try:
                            idx, result = process_row(row_data)
                            results[idx] = result
                            for col, value in result.items():
                                df.at[idx, col] = value
                            pbar.update(1)
                        except Exception as row_error:
                            logger.error(f"Individual row processing error: {row_error}")
                            pbar.update(1)
    
    save_dataframe(df, OUTPUT_CSV)
    
    total_processed = len(rows_to_process)
    success_rate = (progress_tracker.success_count / total_processed * 100) if total_processed > 0 else 0
    
    confidences = []
    for idx, result in results.items():
        if result['fetch_status'] == 'success' and result['llm_confidence'] > 0:
            confidences.append(result['llm_confidence'])
    
    avg_confidence = sum(confidences) / len(confidences) if confidences else 0
    
    logger.info("="*50)
    logger.info("PROCESSING SUMMARY")
    logger.info("="*50)
    logger.info(f"Total rows processed: {total_processed}")
    logger.info(f"Successful: {progress_tracker.success_count} ({success_rate:.1f}%)")
    logger.info(f"Errors: {progress_tracker.error_count}")
    logger.info(f"Skipped: {progress_tracker.skipped_count}")
    logger.info(f"Average LLM confidence: {avg_confidence:.3f}")
    logger.info(f"Output saved to: {OUTPUT_CSV}")

if __name__ == "__main__":
    main()
