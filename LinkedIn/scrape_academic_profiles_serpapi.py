import csv
import time
import random
import logging
import re
import os
from datetime import datetime
from difflib import SequenceMatcher
from urllib.parse import urlparse
import requests
import pandas as pd

# ==============================================================================
# --- CONFIGURATION ---
# ==============================================================================
# 输入输出文件路径配置
CSV_FILE_PATH = "data/database/authors_master_20250730_143534_deduplicated.csv"  # 源数据文件路径
OUTPUT_CSV_PATH = "LinkedIn/linkedIn_profiles_test200_serpapi.csv"     # SerpAPI搜索结果输出文件

# API调用控制参数
SEARCH_DELAY = (0.5, 1.5)   # 搜索间隔秒数范围 (随机延时避免API限制)
MAX_RETRIES = 1             # API失败时的最大重试次数
RETRY_DELAY = (3, 10)       # 重试间隔范围 (秒)

# 进度保存和处理控制
SAVE_INTERVAL = 10          # 每处理N个作者保存一次进度 (防止数据丢失)
CONFIDENCE_THRESHOLD = 0.5  # 最低置信度阈值 (低于此值的结果会被拒绝)

# 运行模式控制
TEST_MODE = False           # False=生产模式处理全部数据, True=测试模式
TEST_LIMIT = 10             # 测试模式下处理的作者数量（已禁用）

# SerpAPI配置参数
import os
SERPAPI_KEY = os.getenv("SERPAPI_KEY", "YOUR_SERPAPI_KEY")  # SerpAPI密钥 - 从环境变量读取
SERPAPI_BASE_URL = "https://serpapi.com/search"  # SerpAPI基础URL

# —— "召回 + 精准" 双升级核心参数 ——
# LinkedIn查询模板 (按优先级排序，模板1优先级最高)
LINKEDIN_QUERIES_TPL = [
    '{name} {affiliation} LinkedIn',                       # 模板1：姓名 + 完整机构名 (召回率高，优先使用)
    '"{name}" site:linkedin.com',                          # 模板2：简单姓名搜索 (备用方案)
    '"{name}" site:linkedin.com/in {aff1} {aff2}',        # 模板3：姓名 + 机构关键词 (精准搜索)
    '"{name}" site:linkedin.com/pub {aff1} {aff2}',       # 模板4：pub页面 + 机构关键词 (覆盖更多格式)
]

SERPAPI_NUM_PER_QUERY = 20          # 每条查询获取的结果数量 (增加候选池大小)
CONFIDENCE_THRESHOLD = 0.58         # 提高置信度门槛以保证精确度 (0.58 > 0.5)
MIN_KEEP_THRESHOLD = 0.2            # 最低保留阈值 (低于此值直接丢弃，避免极低质量结果)

# 学术关键词库 (用于提高搜索准确性)
ACADEMIC_KEYWORDS = {
    'github': [
        'research', 'university', 'professor', 'phd', 'academic', 'lab', 'scholar', 
        'machine learning', 'nlp', 'ai', 'artificial intelligence', 'computer science'
    ],  # GitHub搜索时使用的学术相关关键词
    'linkedin': [
        'professor', 'researcher', 'phd', 'scientist', 'university', 'academic', 
        'research', 'associate professor', 'assistant professor', 'postdoc'
    ]   # LinkedIn搜索时使用的职业相关关键词
}

# LinkedIn个人资料URL正则表达式 (用于验证URL格式的合法性)
LINKEDIN_PROFILE_RE = re.compile(
    r'^https?://([\w\-]+\.)?linkedin\.com/'     # 匹配LinkedIn域名 (支持各国子域名)
    r'(in|pub)/[A-Za-z0-9\-_%]{3,100}/?$'      # 匹配/in/或/pub/路径和用户标识符
)

class AcademicProfileScraperAPI:
    """
    学术人员档案搜索器 - 使用SerpAPI进行LinkedIn和GitHub搜索
    
    核心功能：
    1. 多模板查询策略 - 提高召回率
    2. 严格置信度评分 - 保证精确度  
    3. 智能重试机制 - 处理API限制和网络问题
    4. 实时进度保存 - 防止数据丢失
    """
    
    def __init__(self, csv_file_path, api_key):
        """
        初始化搜索器
        
        Args:
            csv_file_path: 输入CSV文件路径
            api_key: SerpAPI密钥
        """
        self.csv_file_path = csv_file_path
        self.api_key = api_key
        self.setup_logging()
        
    def setup_logging(self):
        """
        设置日志记录系统
        - 同时输出到文件和控制台
        - 文件名包含时间戳以避免覆盖
        """
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(f'profile_scraper_api_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)

    def save_progress(self, header, data, message="✅ Progress saved."):
        """
        保存进度到CSV文件 - 双重保存策略防止数据丢失
        
        Args:
            header: CSV表头
            data: 数据行列表
            message: 保存完成后的日志消息
        """
        # 保存到原始输入文件 (更新源数据)
        with open(self.csv_file_path, mode='w', encoding='utf-8', newline='') as outfile:
            writer = csv.writer(outfile)
            writer.writerow(header)
            writer.writerows(data)
        
        # 保存到专门的输出文件 (SerpAPI搜索结果)
        with open(OUTPUT_CSV_PATH, mode='w', encoding='utf-8', newline='') as outfile:
            writer = csv.writer(outfile)
            writer.writerow(header)
            writer.writerows(data)
            
        self.logger.info(message)
        self.logger.info(f"   💾 Saved to: {OUTPUT_CSV_PATH}")

    def extract_affiliation_keywords(self, affiliation):
        """
        从机构名称中提取关键词用于搜索优化
        
        处理策略：
        1. 移除常见停用词 (of, the, and等)
        2. 提取有意义的词汇 (长度>2)  
        3. 识别并包含缩写词 (如MIT, UCLA等)
        4. 限制返回最多3个关键词避免查询过长
        
        Args:
            affiliation: 机构名称字符串
            
        Returns:
            list: 提取的关键词列表
        """
        if not affiliation:
            return []
        
        # 定义停用词 - 这些词在搜索中没有区分度
        stop_words = {'of', 'the', 'and', 'at', 'in', 'for', 'university', 'college', 'institute', 'department'}
        
        # 提取英文单词并过滤停用词和短词
        words = re.findall(r'\b[A-Za-z]+\b', affiliation.lower())
        keywords = [word for word in words if len(word) > 2 and word not in stop_words]
        
        # 单独提取缩写词 (全大写字母，2个字符以上)
        abbreviations = re.findall(r'\b[A-Z]{2,}\b', affiliation)
        keywords.extend([abbr.lower() for abbr in abbreviations])
        
        return keywords[:3]  # 最多返回3个关键词避免查询过于复杂

    def calculate_name_similarity(self, name1, name2):
        """计算姓名相似度"""
        name1_clean = re.sub(r'[^a-zA-Z\s]', '', name1.lower().strip())
        name2_clean = re.sub(r'[^a-zA-Z\s]', '', name2.lower().strip())
        return SequenceMatcher(None, name1_clean, name2_clean).ratio()

    def search_with_serpapi(self, query, retry_count=0):
        """
        SerpAPI搜索接口 - 带智能重试机制
        
        处理的错误类型：
        1. API配额/限制错误 - 等待后重试
        2. HTTP临时错误 (429, 403, 502等) - 递增延时重试  
        3. 网络超时 - 短延时重试
        4. 连接错误 - 中延时重试
        5. 其他异常 - 通用重试
        
        Args:
            query: 搜索查询字符串
            retry_count: 当前重试次数
            
        Returns:
            dict: SerpAPI响应数据，失败时返回None
        """
        try:
            # 构建API请求参数
            params = {
                'engine': 'google',      # 使用Google搜索引擎
                'q': query,              # 搜索查询
                'api_key': self.api_key, # API密钥
                'num': 10                # 获取结果数量
            }
            
            # 发送API请求
            response = requests.get(SERPAPI_BASE_URL, params=params, timeout=30)
            
            if response.status_code == 200:
                data = response.json()
                
                # 检查API响应中的错误信息
                if 'error' in data:
                    error_msg = data['error']
                    self.logger.warning(f"SerpAPI returned error: {error_msg}")
                    
                    # 判断是否为可重试的配额/限制错误
                    if any(keyword in error_msg.lower() for keyword in ['rate limit', 'quota', 'blocked', 'access denied', 'forbidden']):
                        if retry_count < MAX_RETRIES:
                            wait_time = (retry_count + 1) * 5  # 递增等待：5, 10, 15秒
                            self.logger.info(f"🔄 Retrying in {wait_time} seconds... (attempt {retry_count + 1}/{MAX_RETRIES})")
                            time.sleep(wait_time)
                            return self.search_with_serpapi(query, retry_count + 1)
                        else:
                            self.logger.error(f"❌ Max retries ({MAX_RETRIES}) reached for query: {query}")
                            return None
                    else:
                        return None  # 不可重试的错误直接返回
                
                return data  # 成功响应
            
            # 处理HTTP临时错误状态码
            elif response.status_code in [429, 403, 502, 503, 504]:
                if retry_count < MAX_RETRIES:
                    wait_time = (retry_count + 1) * 10  # 递增等待：10, 20, 30秒
                    self.logger.warning(f"⚠️ HTTP {response.status_code} error. Retrying in {wait_time} seconds... (attempt {retry_count + 1}/{MAX_RETRIES})")
                    time.sleep(wait_time)
                    return self.search_with_serpapi(query, retry_count + 1)
                else:
                    self.logger.error(f"❌ Max retries ({MAX_RETRIES}) reached. HTTP {response.status_code} for query: {query}")
                    return None
            else:
                self.logger.error(f"SerpAPI request failed with status {response.status_code}")
                return None
                
        except requests.exceptions.Timeout:
            # 处理超时错误
            if retry_count < MAX_RETRIES:
                wait_time = (retry_count + 1) * 3  # 超时重试间隔：3, 6, 9秒
                self.logger.warning(f"⏰ Request timeout. Retrying in {wait_time} seconds... (attempt {retry_count + 1}/{MAX_RETRIES})")
                time.sleep(wait_time)
                return self.search_with_serpapi(query, retry_count + 1)
            else:
                self.logger.error(f"❌ Max retries ({MAX_RETRIES}) reached due to timeout for query: {query}")
                return None
                
        except requests.exceptions.ConnectionError:
            # 处理连接错误
            if retry_count < MAX_RETRIES:
                wait_time = (retry_count + 1) * 5  # 连接错误重试间隔：5, 10, 15秒
                self.logger.warning(f"🔌 Connection error. Retrying in {wait_time} seconds... (attempt {retry_count + 1}/{MAX_RETRIES})")
                time.sleep(wait_time)
                return self.search_with_serpapi(query, retry_count + 1)
            else:
                self.logger.error(f"❌ Max retries ({MAX_RETRIES}) reached due to connection error for query: {query}")
                return None
                
        except Exception as e:
            # 处理其他未预期的错误
            if retry_count < MAX_RETRIES:
                wait_time = (retry_count + 1) * 3  # 其他错误重试间隔：3, 6, 9秒
                self.logger.warning(f"❓ Unexpected error: {str(e)}. Retrying in {wait_time} seconds... (attempt {retry_count + 1}/{MAX_RETRIES})")
                time.sleep(wait_time)
                return self.search_with_serpapi(query, retry_count + 1)
            else:
                self.logger.error(f"❌ Max retries ({MAX_RETRIES}) reached due to error: {str(e)}")
                return None

    def search_github_profile(self, author_name, affiliation, retry_count=0):
        """搜索GitHub个人资料，带重试机制"""
        try:
            affil_keywords = self.extract_affiliation_keywords(affiliation)
            affil_str = ' '.join(affil_keywords) if affil_keywords else ''
            
            # 添加学术关键词提高搜索准确性
            github_academic_terms = ' OR '.join(ACADEMIC_KEYWORDS['github'][:5])  # 使用前5个关键词避免查询过长
            
            # 构建搜索查询
            query = f'"{author_name}" github {affil_str} ({github_academic_terms}) site:github.com'
            
            # 使用SerpAPI搜索
            search_results = self.search_with_serpapi(query)
            
            if not search_results:
                if retry_count < MAX_RETRIES:
                    self.logger.warning(f"🔄 GitHub search failed, retrying... (attempt {retry_count + 1}/{MAX_RETRIES})")
                    time.sleep(3)  # 短暂等待
                    return self.search_github_profile(author_name, affiliation, retry_count + 1)
                else:
                    return None, 0, "Error"
            
            if 'organic_results' not in search_results:
                return None, 0, "Not Found"
            
            # 提取GitHub链接
            github_links = self.extract_github_links_from_results(search_results['organic_results'])
            
            if not github_links:
                return None, 0, "Not Found"
            
            # 验证每个链接并计算置信度
            for link in github_links[:3]:  # 最多检查前3个结果
                confidence = self.calculate_github_confidence(link, author_name, affiliation)
                if confidence >= CONFIDENCE_THRESHOLD:
                    return link, confidence, "Success"
            
            # 如果没有高置信度匹配，返回最佳结果
            if github_links:
                best_link = github_links[0]
                confidence = self.calculate_github_confidence(best_link, author_name, affiliation)
                return best_link, confidence, "Low Confidence"
            
            return None, 0, "Not Found"
            
        except Exception as e:
            if retry_count < MAX_RETRIES:
                self.logger.warning(f"🔄 GitHub search exception, retrying... (attempt {retry_count + 1}/{MAX_RETRIES}): {str(e)}")
                time.sleep(3)
                return self.search_github_profile(author_name, affiliation, retry_count + 1)
            else:
                self.logger.error(f"GitHub search error for {author_name}: {str(e)}")
                return None, 0, "Error"

    def search_linkedin_profile(self, author_name, affiliation, retry_count=0):
        """
        LinkedIn个人资料搜索主函数 - "召回 + 精准"双升级架构
        
        执行流程：
        1. 召回阶段：使用多模板查询获取候选结果
        2. 精准阶段：对每个候选结果计算置信度评分
        3. 选择阶段：选择最高置信度且超过阈值的结果
        
        Args:
            author_name: 作者姓名
            affiliation: 机构名称  
            retry_count: 重试计数
            
        Returns:
            tuple: (LinkedIn_URL, confidence_score, status)
        """
        try:
            # ===== 召回阶段：获取候选结果 =====
            candidates = self.search_linkedin_candidates(author_name, affiliation)

            # ===== 精准阶段：评分和选择 =====
            best_link, best_conf = None, 0
            
            for item in candidates:
                url = item.get('link', '')
                
                # 验证URL格式合法性
                if not self.is_linkedin_profile_url(url):
                    continue
                    
                # 计算置信度分数
                conf = self.calc_linkedin_conf(url, item, author_name, affiliation)
                
                # 更新最佳结果
                if conf > best_conf:
                    best_link, best_conf = url, conf

            # ===== 决策阶段：根据置信度返回结果 =====
            if best_conf >= CONFIDENCE_THRESHOLD:
                return best_link, best_conf, "Success"              # 高置信度：成功
            elif best_conf >= MIN_KEEP_THRESHOLD:
                return best_link, best_conf, "Low Confidence"       # 中等置信度：需要人工确认
            else:
                return None, 0, "Not Found"                         # 极低置信度：直接丢弃
            
        except Exception as e:
            # 错误重试机制
            if retry_count < MAX_RETRIES:
                self.logger.warning(f"🔄 LinkedIn search exception, retrying... (attempt {retry_count + 1}/{MAX_RETRIES}): {str(e)}")
                time.sleep(3)
                return self.search_linkedin_profile(author_name, affiliation, retry_count + 1)
            else:
                self.logger.error(f"LinkedIn search error for {author_name}: {str(e)}")
                return None, 0, "Error"

    def extract_github_links_from_results(self, results):
        """从SerpAPI结果中提取GitHub链接"""
        github_links = []
        
        for result in results:
            link = result.get('link', '')
            if 'github.com/' in link and self.is_github_profile_url(link):
                github_links.append(link)
        
        return list(dict.fromkeys(github_links))  # 去重

    def extract_linkedin_links_from_results(self, results):
        """从SerpAPI结果中提取LinkedIn链接"""
        linkedin_links = []
        
        for result in results:
            link = result.get('link', '')
            if 'linkedin.com/in/' in link and self.is_linkedin_profile_url(link):
                linkedin_links.append(link)
        
        return list(dict.fromkeys(linkedin_links))  # 去重

    def is_github_profile_url(self, url):
        """验证是否为GitHub个人资料URL"""
        try:
            parsed = urlparse(url)
            if 'github.com' not in parsed.netloc:
                return False
            
            path_parts = [p for p in parsed.path.split('/') if p]
            # GitHub个人资料URL格式: github.com/username
            return len(path_parts) == 1 and not any(keyword in url.lower() for keyword in ['gist', 'orgs', 'repos'])
        except:
            return False

    def is_linkedin_profile_url(self, url):
        """验证是否为LinkedIn个人资料URL"""
        if not LINKEDIN_PROFILE_RE.match(url):
            return False
        ban_parts = ('/company/', '/groups/', '/pulse/', '/jobs?', '/learning/')
        return not any(p in url for p in ban_parts)

    def search_linkedin_candidates(self, author_name, affiliation):
        """
        优先模板LinkedIn搜索 - "召回"阶段的核心实现
        
        策略说明：
        1. 优先使用模板1进行搜索，提高精准度
        2. 如果模板1结果不足，再使用其他模板补充
        3. 为每个结果标记查询来源以便后续优先级排序
        4. 构建丰富的候选结果池供后续精准评分
        
        Args:
            author_name: 作者姓名
            affiliation: 机构名称
            
        Returns:
            list: 去重后的候选结果列表，每个结果包含_query_priority标记
        """
        # 提取机构关键词用于模板3和4
        aff_kws = self.extract_affiliation_keywords(affiliation)
        aff1, aff2 = (aff_kws + ['',''])[:2]   # 确保有两个占位符，不足时用空字符串

        all_items = []
        
        # 优先使用模板1 (姓名 + 完整机构名)
        priority_template = LINKEDIN_QUERIES_TPL[0]
        q1 = priority_template.format(name=author_name, aff1=aff1, aff2=aff2, affiliation=affiliation)
        
        search_results = self.search_with_serpapi(q1)
        if search_results and 'organic_results' in search_results:
            items = search_results['organic_results'][:SERPAPI_NUM_PER_QUERY]
            for item in items:
                item['_query_priority'] = 0  # 模板1优先级最高
            all_items.extend(items)
        
        # 如果模板1结果少于5个，使用其他模板补充
        valid_linkedin_count = sum(1 for item in all_items if 'linkedin.com' in item.get('link', ''))
        if valid_linkedin_count < 5:
            for i, tpl in enumerate(LINKEDIN_QUERIES_TPL[1:], 1):  # 从模板2开始
                q = tpl.format(name=author_name, aff1=aff1, aff2=aff2, affiliation=affiliation)
                
                search_results = self.search_with_serpapi(q)
                if search_results and 'organic_results' in search_results:
                    items = search_results['organic_results'][:10]  # 其他模板减少结果数
                    
                    for item in items:
                        item['_query_priority'] = i  # 设置较低优先级
                    all_items.extend(items)

        # 根据URL去重并保留最高优先级的结果
        seen, uniq_items = set(), []
        
        # 先按优先级排序：模板1(priority=0) > 模板2(priority=1) > ...
        all_items.sort(key=lambda x: x.get('_query_priority', 999))
        
        # 遍历排序后的结果，每个URL只保留第一次出现的（即优先级最高的）
        for it in all_items:
            url = it.get('link','')
            if url not in seen and 'linkedin.com' in url:
                seen.add(url)
                uniq_items.append(it)
                
        return uniq_items

    def calc_linkedin_conf(self, link, serp_item, author_name, affiliation):
        """
        改进的LinkedIn置信度计算函数 - 核心算法
        
        评分维度 (总分1.0)：
        1. 姓名匹配度 (0-0.5分) - 占总分的一半
           - URL slug与作者姓名的匹配程度
           - 采用严格匹配策略防止错误识别
        2. 机构匹配度 (0-0.4分) - 提高机构权重
           - 标题/摘要中机构关键词的出现情况
        3. 内容匹配度 (0-0.1分) - 辅助验证
           - 标题/摘要中姓名的出现
        4. 负面惩罚 (-0.2分) - 质量过滤
           - 随机数字、招聘页面等低质量指标扣分
        
        严格匹配规则：
        - 单名：必须100%匹配
        - 双名：至少匹配50% (1/2)
        - 三名及以上：至少匹配67% (2/3) 且至少匹配2个词
        
        Args:
            link: LinkedIn URL
            serp_item: 搜索结果项 (包含title, snippet等)
            author_name: 作者姓名
            affiliation: 机构名称
            
        Returns:
            float: 置信度分数 (0.0-1.0)
        """
        # 提取URL末尾的用户标识符并标准化处理
        slug = link.rstrip('/').split('/')[-1].lower()
        name_tokens = [t.lower() for t in author_name.split() if len(t) > 1]
        aff_tokens = self.extract_affiliation_keywords(affiliation)
        
        # 调试输出：显示解析的基础信息
        self.logger.info(f"      🔍 LinkedIn置信度计算 for: {author_name}")
        self.logger.info(f"         URL: {link}")
        self.logger.info(f"         URL slug: '{slug}'")
        self.logger.info(f"         姓名词汇: {name_tokens}")
        self.logger.info(f"         机构关键词: {aff_tokens}")

        # (1) 姓名匹配检查 0–0.5分 (占总分一半)
        slug_clean = slug.replace('-', ' ')  # 将连字符替换为空格便于匹配
        slug_hit = sum(tok in slug_clean for tok in name_tokens)  # 计算匹配的姓名词数
        name_match_ratio = slug_hit / len(name_tokens) if name_tokens else 0
        
        self.logger.info(f"         姓名匹配: {slug_hit}/{len(name_tokens)} = {name_match_ratio:.2f}")
        
        # 严格姓名匹配要求 - 防止同名异人的错误匹配
        if len(name_tokens) == 1:
            # 单名：必须100%匹配 (如 "Smith" 必须在URL中出现)
            if name_match_ratio < 1.0:
                self.logger.info(f"         ❌ 单名必须100%匹配，实际{name_match_ratio:.2f} < 1.0")
                return 0.0
        elif len(name_tokens) == 2:
            # 双名：至少匹配50%（1个词）(如 "John Smith" 至少要有John或Smith)
            if name_match_ratio < 0.5:
                self.logger.info(f"         ❌ 双名必须50%+匹配，实际{name_match_ratio:.2f} < 0.5")
                return 0.0
        elif len(name_tokens) >= 3:
            # 三名或更多：至少匹配67%（2/3）并且匹配数>=2
            # 例如 "John Michael Smith" 必须至少匹配其中2个词
            if name_match_ratio < 0.67 or slug_hit < 2:
                self.logger.info(f"         ❌ 三名+必须67%+匹配且≥2词，实际{name_match_ratio:.2f}, 匹配{slug_hit}词")
                return 0.0
        
        # 姓名得分：占总分一半 (0.5分)
        name_score = name_match_ratio * 0.5
        
        # (2) 机构匹配度 0–0.4分 - 提高权重
        snippet = (serp_item.get('title','') + serp_item.get('snippet','')).lower()
        aff_hit_count = sum(1 for k in aff_tokens if k in snippet)
        aff_match_ratio = aff_hit_count / len(aff_tokens) if aff_tokens else 0
        aff_score = aff_match_ratio * 0.4
        
        self.logger.info(f"         机构匹配: {aff_hit_count}/{len(aff_tokens)} = {aff_match_ratio:.2f}")
        
        # (3) 内容匹配度 0–0.1分 - 姓名在标题/摘要中的出现
        if name_tokens:
            text_hit = sum(tok in snippet for tok in name_tokens) / len(name_tokens)
        else:
            text_hit = 0
        content_score = text_hit * 0.1
        
        # 基础得分
        score = name_score + aff_score + content_score
        self.logger.info(f"         得分构成: 姓名{name_score:.3f} + 机构{aff_score:.3f} + 内容{content_score:.3f} = {score:.3f}")

        # (4) 负面惩罚 0–0.2分 - 过滤低质量结果
        penalties = 0
        if re.search(r'\d{4,}', slug):  # 包含4位以上数字（通常是随机ID）
            penalties += 0.1
            self.logger.info(f"         ⚠️ 随机数字惩罚: -0.1")
        if 'jobs' in link:  # 招聘相关页面
            penalties += 0.1
            self.logger.info(f"         ⚠️ 招聘页面惩罚: -0.1")
        score -= penalties

        # 最终筛选机制：姓名或机构匹配度小于70%的结果降级
        if name_match_ratio < 0.7 and aff_match_ratio < 0.7:
            # 如果姓名和机构匹配度都小于70%，直接返回低分
            final_score = min(score * 0.3, 0.4)  # 强制降到低置信度范围
            self.logger.info(f"         📉 70%筛选降级: {score:.3f} → {final_score:.3f} (姓名{name_match_ratio:.2f}<0.7且机构{aff_match_ratio:.2f}<0.7)")
            return final_score
        else:
            final_score = max(0, min(score, 1.0))  # 确保分数在[0,1]范围内
            self.logger.info(f"         🎯 最终得分: {final_score:.3f} (阈值: {CONFIDENCE_THRESHOLD})")
            return final_score

    def calculate_github_confidence(self, url, author_name, affiliation):
        """计算GitHub链接的置信度（基于URL分析）"""
        confidence_score = 0.0
        
        # 检查用户名与姓名的相似度
        username = url.split('/')[-1]
        name_similarity = self.calculate_name_similarity(author_name, username.replace('-', ' ').replace('_', ' '))
        confidence_score += name_similarity * 0.6  # 主要依据用户名匹配
        
        # 检查机构关键词是否在用户名中
        affil_keywords = self.extract_affiliation_keywords(affiliation)
        for keyword in affil_keywords:
            if keyword.lower() in username.lower():
                confidence_score += 0.2
                break
        
        # 如果用户名包含学术相关词汇
        academic_indicators = ACADEMIC_KEYWORDS['github'][:8]  # 使用定义的学术关键词
        for indicator in academic_indicators:
            if indicator.lower().replace(' ', '') in username.lower():
                confidence_score += 0.1
                break
        
        return min(confidence_score, 1.0)

    def calculate_linkedin_confidence(self, url, author_name, affiliation):
        """计算LinkedIn链接的置信度（基于URL分析）"""
        confidence_score = 0.0
        
        # LinkedIn URL通常包含姓名信息
        url_lower = url.lower()
        
        # 检查姓名在URL中的出现
        name_parts = author_name.lower().split()
        matches = sum(1 for part in name_parts if len(part) > 2 and part in url_lower)
        if matches > 0:
            confidence_score += min(matches * 0.3, 0.7)
        
        # 检查机构关键词
        affil_keywords = self.extract_affiliation_keywords(affiliation)
        for keyword in affil_keywords:
            if keyword.lower() in url_lower:
                confidence_score += 0.2
                break
        
        # LinkedIn URL结构良好性检查
        if '/in/' in url and len(url.split('/')) >= 5:
            confidence_score += 0.1
        
        return min(confidence_score, 1.0)

    def generate_final_report(self, data_rows, status_idx, github_url_idx, linkedin_url_idx, processed_count):
        """生成最终处理报告"""
        try:
            # 统计数据
            success_count = sum(1 for row in data_rows if row[status_idx] == "Success")
            error_count = sum(1 for row in data_rows if row[status_idx] == "Error")
            not_found_count = sum(1 for row in data_rows if row[status_idx] == "Not Found")
            github_found = sum(1 for row in data_rows if row[github_url_idx].strip())
            linkedin_found = sum(1 for row in data_rows if row[linkedin_url_idx].strip())
            both_found = sum(1 for row in data_rows if row[github_url_idx].strip() and row[linkedin_url_idx].strip())
            
            self.logger.info("============================================================")
            self.logger.info("📊 FINAL PROCESSING REPORT")
            self.logger.info("============================================================")
            self.logger.info(f"📋 Total Authors Processed: {processed_count}")
            self.logger.info(f"✅ Successfully Found Profiles: {success_count} ({success_count/processed_count*100:.1f}%)")
            self.logger.info(f"❌ Errors: {error_count}")
            self.logger.info(f"❓ Not Found: {not_found_count}")
            self.logger.info("")
            self.logger.info("🔗 Profile Discovery:")
            self.logger.info(f"   GitHub: {github_found} ({github_found/processed_count*100:.1f}%)")
            self.logger.info(f"   LinkedIn: {linkedin_found} ({linkedin_found/processed_count*100:.1f}%)")
            self.logger.info(f"   Both: {both_found}")
            self.logger.info("")
            self.logger.info(f"💾 Output saved to: {OUTPUT_CSV_PATH}")
            self.logger.info("============================================================")
            
        except Exception as e:
            self.logger.error(f"Error generating final report: {str(e)}")

    def random_delay(self):
        """随机延时"""
        delay = random.uniform(*SEARCH_DELAY)
        time.sleep(delay)

    def run_scraping(self):
        """主执行逻辑"""
        if self.api_key == "YOUR_SERPAPI_KEY":
            self.logger.error("❌ Please set your SerpAPI key in the SERPAPI_KEY variable")
            return
        
        try:
            # 读取数据 - 支持CSV和Excel格式
            if self.csv_file_path.endswith('.xlsx') or self.csv_file_path.endswith('.xls'):
                # 读取Excel文件
                df = pd.read_excel(self.csv_file_path)
                header = df.columns.tolist()
                data_rows = df.values.tolist()
            else:
                # 读取CSV文件
                with open(self.csv_file_path, mode='r', encoding='utf-8', newline='') as infile:
                    reader = csv.reader(infile)
                    all_data = list(reader)
                header = all_data[0]
                data_rows = all_data[1:]
            
            # 添加新列如果不存在
            new_columns = ['GitHub_URL', 'LinkedIn_URL', 'GitHub_Confidence', 'LinkedIn_Confidence', 'Search_Status']
            for col in new_columns:
                if col not in header:
                    header.append(col)
                    for row in data_rows:
                        row.append('')
            
            # 找到需要处理的行
            github_url_idx = header.index('GitHub_URL')
            linkedin_url_idx = header.index('LinkedIn_URL')
            status_idx = header.index('Search_Status')
            
            rows_to_process = [
                (i, row) for i, row in enumerate(data_rows) 
                if not row[status_idx].strip()  # 只检查Search_Status是否为空
            ]
            
            if not rows_to_process:
                self.logger.info("✅ All tasks are complete. Exiting script.")
                return
            
            self.logger.info(f"🚀 Production mode: processing all {len(rows_to_process)} authors")
            self.logger.info(f"📁 Output will be saved to: {OUTPUT_CSV_PATH}")
            self.logger.info(f"💾 Progress saved every {SAVE_INTERVAL} authors")
            self.logger.info("Starting SerpAPI scraping...")
            
            for i, (row_idx, row_data) in enumerate(rows_to_process):
                try:
                    author_name = row_data[0]  # Author Name
                    affiliation = row_data[1]  # Affiliation
                    
                    self.logger.info(f"📊 Processing {i+1}/{len(rows_to_process)}: {author_name}")
                    self.logger.info(f"   🏛️ Affiliation: {affiliation}")
                    
                    # 搜索GitHub
                    github_url, github_conf, github_status = self.search_github_profile(author_name, affiliation)
                    self.random_delay()  # API调用间隔
                    
                    # 搜索LinkedIn
                    linkedin_url, linkedin_conf, linkedin_status = self.search_linkedin_profile(author_name, affiliation)
                    self.random_delay()  # API调用间隔
                    
                    # 更新数据
                    data_rows[row_idx][github_url_idx] = github_url or ''
                    data_rows[row_idx][linkedin_url_idx] = linkedin_url or ''
                    data_rows[row_idx][header.index('GitHub_Confidence')] = f"{github_conf:.3f}" if github_conf > 0 else ''
                    data_rows[row_idx][header.index('LinkedIn_Confidence')] = f"{linkedin_conf:.3f}" if linkedin_conf > 0 else ''
                    
                    # 设置状态 - 修正逻辑：考虑置信度阈值和搜索状态
                    if "Error" in github_status or "Error" in linkedin_status:
                        status = "Error"
                    elif github_status == "Success" or linkedin_status == "Success":
                        # 至少有一个高置信度匹配
                        status = "Success"
                    elif github_status == "Low Confidence" or linkedin_status == "Low Confidence":
                        # 只有低置信度匹配，需要人工确认
                        status = "Low Confidence"
                    elif github_url or linkedin_url:
                        # 找到URL但置信度很低的情况
                        status = "Low Confidence"
                    else:
                        status = "Not Found"
                    
                    data_rows[row_idx][status_idx] = status
                    
                    # 日志记录
                    self.logger.info(f"   ✅ Results for {author_name} ({affiliation}):")
                    self.logger.info(f"      GitHub: {github_url or 'Not found'} (conf: {github_conf:.3f})")
                    self.logger.info(f"      LinkedIn: {linkedin_url or 'Not found'} (conf: {linkedin_conf:.3f})")
                    self.logger.info(f"      Status: {status}")
                    
                    # 定期保存进度
                    if (i + 1) % SAVE_INTERVAL == 0:
                        self.save_progress(header, data_rows, f"🔄 Processed {i + 1}/{len(rows_to_process)} authors...")
                    
                except Exception as e:
                    self.logger.error(f"Error processing {author_name}: {str(e)}")
                    data_rows[row_idx][status_idx] = "Error"
            
            # 最终保存
            self.save_progress(header, data_rows, "🎉 All processing completed!")
            
            # 生成最终统计报告
            self.generate_final_report(data_rows, status_idx, github_url_idx, linkedin_url_idx, len(rows_to_process))
            
        except KeyboardInterrupt:
            self.logger.info("🛑 User interrupted. Exiting.")
        except Exception as e:
            self.logger.error(f"Unexpected error: {str(e)}")

def main():
    """
    主程序入口
    
    执行流程：
    1. 验证API密钥配置
    2. 创建搜索器实例
    3. 开始批量搜索处理
    """
    # 检查API密钥是否正确配置
    if SERPAPI_KEY == "YOUR_SERPAPI_KEY":
        print("❌ Error: Please set your SerpAPI key in the SERPAPI_KEY variable")
        print("🔗 Get your free API key at: https://serpapi.com/")
        return
    
    # 创建搜索器实例并开始处理
    scraper = AcademicProfileScraperAPI(CSV_FILE_PATH, SERPAPI_KEY)
    scraper.run_scraping()

if __name__ == "__main__":
    main()
