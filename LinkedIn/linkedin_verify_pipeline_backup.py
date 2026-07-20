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

INPUT_CSV = "data/database/authors_LinkedIn_test.csv"  
OUTPUT_CSV = "LinkedIn/authors_LinkedIn_verified_complete.csv"

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
    """验证LinkedIn档案，使用OpenAI API（增强版）"""
    
    # 输入验证
    if not isinstance(profile, dict):
        logger.warning(f"Profile不是字典类型: {type(profile)}")
        return {"match": False, "confidence": 0.0, "reason": "invalid_profile_data_type"}
    
    if not author_name or not affiliation:
        logger.warning("缺少必要的作者姓名或机构信息")
        return {"match": False, "confidence": 0.0, "reason": "missing_author_or_affiliation"}
    
    # 安全提取profile信息，处理None值
    profile_name = (profile.get("name") or "").lower()
    profile_headline = (profile.get("headline") or "").lower()
    profile_position = (profile.get("position") or "").lower()
    
    # 安全处理experience和education，确保它们是列表
    experience = profile.get("experience") or []
    if not isinstance(experience, list):
        experience = []
    
    education = profile.get("education") or []
    if not isinstance(education, list):
        education = []
    
    # 获取当前公司信息
    current_company = profile.get("current_company", {})
    if isinstance(current_company, dict):
        current_company_name = current_company.get("name") or ""
        current_position_title = current_company.get("title") or ""
    else:
        current_company_name = ""
        current_position_title = ""
    
    # 构建更全面的profile信息
    work_history = []
    for exp in experience[:5]:  # 增加到前5个工作经历
        if isinstance(exp, dict):
            work_history.append({
                "title": exp.get("title") or "",
                "company": exp.get("company") or "",
                "duration": exp.get("start_date", "") + " - " + exp.get("end_date", "")
            })
    
    edu_history = []
    for edu in education:  # 获取所有教育经历
        if isinstance(edu, dict):
            school_name = edu.get("school") or edu.get("title") or ""
            degree = edu.get("degree") or ""
            field = edu.get("field") or ""
            duration = ""
            if edu.get("start_year") and edu.get("end_year"):
                duration = f"{edu.get('start_year')}-{edu.get('end_year')}"
            
            edu_history.append({
                "degree": degree,
                "field": field, 
                "school": school_name,
                "duration": duration
            })
    
    # 获取更多详细信息
    snippet = {
        "name": profile.get("name"),
        "headline": profile.get("headline"),
        "location": profile.get("location") or profile.get("city"),
        "current_position": {
            "title": current_position_title,
            "company": current_company_name
        },
        "work_history": work_history,
        "education_history": edu_history,
        "educations_details": profile.get("educations_details", "")  # 特别关注这个字段
    }

    # 创建大学简称映射表
    university_mappings = {
        "sutd": "singapore university of technology and design",
        "nus": "national university of singapore", 
        "ntu": "nanyang technological university",
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
        "tsinghua": "tsinghua university",
        "peking": "peking university",
        "hku": "university of hong kong",
        "cuhk": "chinese university of hong kong",
        "hkust": "hong kong university of science and technology",
        "eth": "eth zurich",
        "epfl": "école polytechnique fédérale de lausanne",
        "tu delft": "delft university of technology",
        "tu munich": "technical university of munich",
        "rwth": "rwth aachen university",
        "ku leuven": "ku leuven",
        "tu berlin": "technical university of berlin",
        "tu vienna": "vienna university of technology",
        "kaist": "korea advanced institute of science and technology",
        "snu": "seoul national university",
        "tokyo": "university of tokyo",
        "kyoto": "kyoto university",
        "iit": "indian institute of technology",
        "iisc": "indian institute of science"
    }

    prompt = f"""
You are an expert data validator for academic profiles with deep knowledge of university names and their abbreviations.

Expected author name: "{author_name}"
Expected affiliation: "{affiliation}"

LinkedIn profile data:
```json
{json.dumps(snippet, ensure_ascii=False, indent=2)}
```

University abbreviations and aliases to consider:
{json.dumps(university_mappings, ensure_ascii=False, indent=2)}

Enhanced validation instructions:
1. NAME MATCHING:
   - Consider name variations (first/last name order, middle names, nicknames)
   - Account for cultural name differences (e.g., Chinese names)
   - Accept partial matches if core name components align

2. AFFILIATION MATCHING:
   - Check ALL sources: current position, work history, education history, and educations_details field
   - Use the university mappings above to match abbreviations with full names
   - Consider department/school within university (e.g., "Computer Science, MIT" matches "MIT")
   - For academics, ANY historical connection (work or education) should be considered valid
   - Look for partial matches and semantic equivalence

3. ACADEMIC CONTEXT:
   - Researchers often move between institutions
   - PhD/education affiliations are as important as current employment
   - Consider research collaborations and visiting positions
   - Multiple affiliations are common in academia

4. CONFIDENCE SCORING:
   - 0.9-1.0: Perfect name and clear affiliation match
   - 0.7-0.9: Good name match with reasonable affiliation connection
   - 0.5-0.7: Partial matches with some uncertainty
   - 0.3-0.5: Weak connection or ambiguous data
   - 0.0-0.3: Clear mismatch or insufficient information

Examples of positive matches:
- Expected: "Singapore University of Technology and Design" → Found: "SUTD" 
- Expected: "MIT" → Found: "Massachusetts Institute of Technology"
- Expected: "UC Berkeley" → Found: "University of California, Berkeley"

Respond ONLY in valid JSON format:
{{
"match": true/false,
"confidence": 0.0-1.0,
"reason": "detailed explanation of matching logic"
}}
"""
    
    # 尝试新的Gemini API，超时限制更短
    for attempt in range(2):  # 只重试2次
        try:
            # 使用新的API格式
            response = client.chat.completions.create(
                model=OPENAI_MODEL,
                messages=[
                    {"role": "system", "content": "You are an expert data validator. Respond only in valid JSON format."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.0,
                max_tokens=100,
                timeout=10  # 10秒超时
            )
            
            txt = response.choices[0].message.content.strip()
            if txt.startswith("```json"):
                txt = txt.replace("```json", "").replace("```", "").strip()
            
            result = json.loads(txt)
            logger.info(f"✅ OpenAI验证成功: {result}")
            return result
            
        except Exception as e:
            logger.warning(f"❌ OpenAI错误 (尝试 {attempt+1}): {str(e)[:100]}...")
            if attempt == 0:
                time.sleep(1)  # 只等待1秒
    
    # Gemini失败，直接标注为失效
    logger.warning("� Gemini API失效，返回失效状态")
    return {"match": False, "confidence": 0.0, "reason": "gemini_api_failed"}

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
