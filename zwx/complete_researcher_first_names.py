#!/usr/bin/env python3
"""
作者姓名补全脚本
根据 author_id 从 authorships.csv 中获取论文标题，再根据 title 匹配 ACL 作者姓名来补全 first_name
"""

import pandas as pd
import re
import unicodedata
from typing import Tuple, Optional, Dict, List
import sys


def normalize_text(text: str) -> str:
    """标准化文本：去除变音符号、标点、转为小写、去除多余空格"""
    if pd.isna(text) or not text:
        return ""
    
    # 去除变音符号 (Unicode normalization)
    text = unicodedata.normalize('NFD', text)
    text = ''.join(char for char in text if unicodedata.category(char) != 'Mn')
    
    # 转为小写
    text = text.lower()
    
    # 去除标点符号和特殊字符，只保留字母、数字和空格
    text = re.sub(r'[^\w\s]', '', text)
    
    # 去除多余空格
    text = ' '.join(text.split())
    
    return text


def is_name_incomplete(first_name: str) -> bool:
    """判断 first_name 是否不完整"""
    if pd.isna(first_name) or not first_name.strip():
        return True
    
    # 如果只有一个字符，或者以点结尾，认为是不完整的
    name = first_name.strip()
    if len(name) <= 1 or name.endswith('.'):
        return True
    
    return False


def names_match(incomplete_first: str, incomplete_last: str, 
                complete_first: str, complete_last: str) -> bool:
    """
    检查两个姓名是否匹配
    要求：last_name 完全一致，first_name 首字母一致
    """
    if pd.isna(incomplete_last) or pd.isna(complete_last):
        return False
    if pd.isna(incomplete_first) or pd.isna(complete_first):
        return False
    
    # last_name 必须完全一致（忽略大小写和空格）
    if normalize_text(incomplete_last) != normalize_text(complete_last):
        return False
    
    # first_name 首字母必须一致
    incomplete_first = incomplete_first.strip()
    complete_first = complete_first.strip()
    
    if not incomplete_first or not complete_first:
        return False
    
    # 获取首字母（忽略大小写）
    incomplete_initial = incomplete_first[0].lower()
    complete_initial = complete_first[0].lower()
    
    return incomplete_initial == complete_initial


def get_author_paper_titles(researcher_id: int, authorships_df: pd.DataFrame) -> List[str]:
    """获取研究者的所有论文标题"""
    author_papers = authorships_df[authorships_df['author_id'] == researcher_id]
    return author_papers['paper_title'].unique().tolist()


def find_matching_acl_names_by_title(paper_title: str, acl_data: pd.DataFrame, 
                                    incomplete_first: str, incomplete_last: str) -> List[Tuple[str, str]]:
    """
    根据 paper_title 在 ACL 数据中查找匹配的作者姓名
    返回: [(first_name, last_name), ...]
    """
    matches = []
    
    if pd.notna(paper_title) and paper_title:
        normalized_title = normalize_text(paper_title)
        
        # 查找标题匹配的记录
        title_matches = acl_data[
            acl_data['paper_title'].apply(lambda x: normalize_text(str(x)) == normalized_title)
        ]
        
        for _, row in title_matches.iterrows():
            acl_first = row.get('first_name', '')
            acl_last = row.get('last_name', '')
            
            if names_match(incomplete_first, incomplete_last, acl_first, acl_last):
                # 避免重复
                if (acl_first, acl_last) not in matches:
                    matches.append((acl_first, acl_last))
    
    return matches


def complete_researcher_names():
    """主函数：补全研究者姓名"""
    
    # 读取数据文件
    print("正在读取数据文件...")
    
    try:
        # 读取研究者画像数据
        researchers_df = pd.read_csv('/Users/kele/实习/阿联酋/爬取/AI_Researcher_Network/data/author_profiles.csv')
        print(f"研究者画像数据: {len(researchers_df)} 条记录")
        
        # 读取作者关系数据
        authorships_df = pd.read_csv('/Users/kele/实习/阿联酋/爬取/AI_Researcher_Network/data/authorships.csv')
        print(f"作者关系数据: {len(authorships_df)} 条记录")
        
        # 读取 ACL 作者数据
        acl_df = pd.read_csv('/Users/kele/实习/阿联酋/爬取/AI_Researcher_Network/data/author_data_with_paper.csv')
        print(f"ACL 作者数据: {len(acl_df)} 条记录")
        
    except Exception as e:
        print(f"读取数据文件时出错: {e}")
        return
    
    # 统计信息
    total_researchers = len(researchers_df)
    
    # 使用正确的字段名
    id_field = 'author_id' if 'author_id' in researchers_df.columns else 'researcher_id'
    
    incomplete_researchers = researchers_df[
        researchers_df['first_name'].apply(is_name_incomplete)
    ]
    total_incomplete = len(incomplete_researchers)
    
    print(f"\n=== 数据统计 ===")
    print(f"总研究者数量: {total_researchers}")
    print(f"first_name 不完整的研究者数量: {total_incomplete}")
    print(f"不完整比例: {total_incomplete/total_researchers:.2%}")
    
    # 补全处理
    print(f"\n开始补全处理...")
    
    completed_count = 0
    title_matches = 0
    no_papers_count = 0
    no_matches_count = 0
    processed_count = 0
    
    completed_examples = []
    
    # 复制数据框用于修改
    result_df = researchers_df.copy()
    
    for idx, researcher in incomplete_researchers.iterrows():
        processed_count += 1
        
        # 每处理100个研究者显示一次进度
        if processed_count % 100 == 0:
            print(f"处理进度: {processed_count}/{total_incomplete} ({processed_count/total_incomplete:.1%})")
            print(f"  当前已补全: {completed_count} 个研究者")
        researcher_id = researcher[id_field]  # 使用动态字段名
        incomplete_first = researcher['first_name']
        incomplete_last = researcher['last_name']
        
        if pd.isna(incomplete_last):
            continue
        
        # 1. 根据 researcher_id 找到所有论文标题
        author_paper_titles = get_author_paper_titles(researcher_id, authorships_df)
        
        if not author_paper_titles:
            no_papers_count += 1
            continue
        
        # 2. 使用论文标题在 ACL 数据中查找匹配的作者姓名
        found_match = False
        completed_name = ""
        matched_title = ""
        
        for paper_title in author_paper_titles:
            # 在 ACL 数据中查找匹配的作者姓名
            matching_names = find_matching_acl_names_by_title(
                paper_title, acl_df, incomplete_first, incomplete_last
            )
            
            if matching_names:
                # 选择第一个匹配的姓名
                complete_first, complete_last = matching_names[0]
                
                # 更新数据
                result_df.at[idx, 'first_name'] = complete_first
                completed_count += 1
                found_match = True
                completed_name = f"{complete_first} {complete_last}"
                matched_title = paper_title
                title_matches += 1
                
                # 每隔50个补全或前10个补全时输出详细信息
                if completed_count <= 10 or completed_count % 50 == 0:
                    print(f"✓ 补全成功 #{completed_count}: ID={researcher_id}")
                    print(f"   原姓名: {incomplete_first} {incomplete_last}")
                    print(f"   补全后: {completed_name}")
                    print(f"   匹配论文: {matched_title[:50]}{'...' if len(matched_title) > 50 else ''}")
                    print()
                
                # 保存前几个示例
                if len(completed_examples) < 10:
                    completed_examples.append({
                        'researcher_id': str(researcher_id),
                        'original_name': f"{incomplete_first} {incomplete_last}",
                        'completed_name': completed_name,
                        'paper_title': matched_title[:60] + "..." if len(matched_title) > 60 else matched_title
                    })
                
                break
        
        if not found_match:
            no_matches_count += 1
            # 偶尔显示无法匹配的情况（每1000个显示一次）
            if processed_count % 1000 == 0 and no_matches_count > 0:
                print(f"ⓘ 无法匹配示例: ID={researcher_id}, 姓名={incomplete_first} {incomplete_last}")
    
    print(f"处理完成: {processed_count}/{total_incomplete} ({100.0:.1%})")
    print(f"最终补全数量: {completed_count}")
    
    # 输出统计结果
    print(f"\n=== 补全结果统计 ===")
    print(f"成功补全的研究者数量: {completed_count}")
    print(f"补全率: {completed_count/total_incomplete:.2%}")
    print(f"  - 通过 Title 匹配: {title_matches} ({title_matches/total_incomplete:.2%})")
    print(f"未找到论文的研究者: {no_papers_count} ({no_papers_count/total_incomplete:.2%})")
    print(f"找到论文但无匹配姓名: {no_matches_count} ({no_matches_count/total_incomplete:.2%})")
    
    # 显示补全示例
    if completed_examples:
        print(f"\n=== 补全示例 ===")
        for i, example in enumerate(completed_examples, 1):
            print(f"{i}. ID: {example['researcher_id']}")
            print(f"   原姓名: {example['original_name']}")
            print(f"   补全后: {example['completed_name']}")
            print(f"   论文标题: {example['paper_title']}")
            print()
    
    # 保存结果
    output_file = '/Users/kele/实习/阿联酋/爬取/AI_Researcher_Network/data/researcher_profiles_completed2.csv'
    result_df.to_csv(output_file, index=False)
    print(f"补全结果已保存到: {output_file}")
    
    # 验证补全后的完整性
    final_incomplete = result_df[result_df['first_name'].apply(is_name_incomplete)]
    print(f"\n=== 最终统计 ===")
    print(f"补全后仍不完整的 first_name 数量: {len(final_incomplete)}")
    print(f"最终完整率: {(total_researchers - len(final_incomplete))/total_researchers:.2%}")


if __name__ == "__main__":
    complete_researcher_names()
