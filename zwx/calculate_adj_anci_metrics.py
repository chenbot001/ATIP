#!/usr/bin/env python3
"""
计算作者的调整后分数引用指标
计算 adj_anci_frac 和 adj_anci_p_frac
"""

import pandas as pd
import numpy as np

def calculate_adj_anci_metrics():
    """
    计算每位作者的调整后分数引用指标
    adj_anci_frac = C_frac / sqrt(Y)
    adj_anci_p_frac = C_frac / (P * sqrt(Y))
    """
    
    print("正在读取数据文件...")
    
    # 读取数据文件
    authorships_df = pd.read_csv('data/authorships.csv')
    citation_details_df = pd.read_csv('data/citation_details.csv')
    author_megatable_df = pd.read_csv('author_megatable_with_dominance.csv')  # 使用包含dominance的版本
    
    print(f"authorships.csv 包含 {len(authorships_df)} 条记录")
    print(f"citation_details.csv 包含 {len(citation_details_df)} 条记录")
    print(f"author_megatable.csv 包含 {len(author_megatable_df)} 位作者")
    
    # 获取目标作者集合
    target_authors = set(author_megatable_df['author_id'].unique())
    print(f"目标作者数量: {len(target_authors)}")
    
    # 1. 从 authorships.csv 统计每位作者的论文数量 P
    print("正在统计每位作者的论文数量...")
    author_paper_counts = authorships_df.groupby('author_id').size().reset_index(name='P')
    print(f"有发表记录的作者数: {len(author_paper_counts)}")
    
    # 2. 统计每篇论文的作者数量
    print("正在统计每篇论文的作者数量...")
    paper_author_counts = authorships_df.groupby('paper_id').size().reset_index(name='author_count')
    print(f"论文总数: {len(paper_author_counts)}")
    
    # 3. 从 citation_details.csv 统计每篇论文的引用次数 C
    print("正在统计每篇论文的引用次数...")
    paper_citations = citation_details_df.groupby('target_paper_id').size().reset_index(name='C')
    print(f"有引用记录的论文数: {len(paper_citations)}")
    
    # 4. 合并论文信息（作者数量 + 引用次数）
    print("正在合并论文信息...")
    paper_info = paper_author_counts.merge(
        paper_citations, 
        left_on='paper_id', 
        right_on='target_paper_id', 
        how='left'
    )
    # 填充没有引用的论文
    paper_info['C'] = paper_info['C'].fillna(0)
    
    # 计算每篇论文的分数引用 (C / author_count)
    paper_info['fractional_citations'] = paper_info['C'] / paper_info['author_count']
    
    print(f"合并后的论文信息: {len(paper_info)} 篇论文")
    
    # 5. 将分数引用分配给每位作者
    print("正在计算每位作者的分数引用总和...")
    
    # 合并 authorships 和 paper_info 来获取每个作者-论文组合的分数引用
    author_paper_citations = authorships_df.merge(
        paper_info[['paper_id', 'fractional_citations']], 
        on='paper_id', 
        how='left'
    )
    
    # 填充没有引用信息的论文
    author_paper_citations['fractional_citations'] = author_paper_citations['fractional_citations'].fillna(0)
    
    # 按作者聚合，计算 C_frac
    author_cfrac = author_paper_citations.groupby('author_id')['fractional_citations'].sum().reset_index()
    author_cfrac.rename(columns={'fractional_citations': 'C_frac'}, inplace=True)
    
    print(f"计算得到 {len(author_cfrac)} 位作者的 C_frac")
    
    # 6. 合并作者的 P 和 C_frac
    author_stats = author_paper_counts.merge(author_cfrac, on='author_id', how='left')
    author_stats['C_frac'] = author_stats['C_frac'].fillna(0)
    
    # 7. 从 author_megatable 获取 career_length (Y)
    print("正在获取作者的学术生涯长度...")
    author_career = author_megatable_df[['author_id', 'career_length']].copy()
    
    # 合并所有统计数据
    author_complete = author_stats.merge(author_career, on='author_id', how='right')
    
    # 填充缺失值
    author_complete['P'] = author_complete['P'].fillna(1)  # 没有论文记录的设为1
    author_complete['C_frac'] = author_complete['C_frac'].fillna(0)  # 没有引用记录的设为0
    author_complete['career_length'] = author_complete['career_length'].fillna(1)  # 没有career_length的设为1
    
    # 确保Y > 0
    author_complete['Y'] = np.maximum(author_complete['career_length'], 1)
    
    print(f"最终作者统计数据: {len(author_complete)} 位作者")
    
    # 8. 计算 adj_anci_frac 和 adj_anci_p_frac
    print("正在计算调整后分数引用指标...")
    
    # adj_anci_frac = C_frac / sqrt(Y)
    author_complete['adj_anci_frac'] = author_complete['C_frac'] / np.sqrt(author_complete['Y'])
    
    # adj_anci_p_frac = C_frac / (P * sqrt(Y))
    # 避免除以0
    denominator = author_complete['P'] * np.sqrt(author_complete['Y'])
    author_complete['adj_anci_p_frac'] = np.where(
        denominator > 0,
        author_complete['C_frac'] / denominator,
        0.0
    )
    
    # 保留三位小数
    author_complete['adj_anci_frac'] = author_complete['adj_anci_frac'].round(3)
    author_complete['adj_anci_p_frac'] = author_complete['adj_anci_p_frac'].round(3)
    
    # 9. 合并到原始 author_megatable
    print("正在合并结果到原始表格...")
    
    # 如果原表已经有这些列，先删除它们
    cols_to_drop = ['adj_anci_frac', 'adj_anci_p_frac']
    for col in cols_to_drop:
        if col in author_megatable_df.columns:
            author_megatable_df = author_megatable_df.drop(col, axis=1)
    
    # 合并新计算的指标
    result_df = author_megatable_df.merge(
        author_complete[['author_id', 'adj_anci_frac', 'adj_anci_p_frac']], 
        on='author_id', 
        how='left'
    )
    
    # 填充缺失值
    result_df['adj_anci_frac'] = result_df['adj_anci_frac'].fillna(0.0)
    result_df['adj_anci_p_frac'] = result_df['adj_anci_p_frac'].fillna(0.0)
    
    # 10. 保存结果
    output_file = 'author_megatable_with_anci.csv'
    result_df.to_csv(output_file, index=False)
    
    print(f"结果已保存到 {output_file}")
    
    # 显示统计信息
    print("\n统计信息:")
    print(f"总作者数: {len(result_df)}")
    print(f"有分数引用的作者数: {len(result_df[result_df['adj_anci_frac'] > 0])}")
    print(f"adj_anci_frac 平均值: {result_df['adj_anci_frac'].mean():.3f}")
    print(f"adj_anci_frac 中位数: {result_df['adj_anci_frac'].median():.3f}")
    print(f"adj_anci_frac 最大值: {result_df['adj_anci_frac'].max():.3f}")
    print(f"adj_anci_p_frac 平均值: {result_df['adj_anci_p_frac'].mean():.3f}")
    print(f"adj_anci_p_frac 中位数: {result_df['adj_anci_p_frac'].median():.3f}")
    print(f"adj_anci_p_frac 最大值: {result_df['adj_anci_p_frac'].max():.3f}")
    
    # 显示一些样本数据
    print("\n样本数据:")
    sample_df = result_df[['author_id', 'first_name', 'last_name', 'career_length', 'adj_anci_frac', 'adj_anci_p_frac']].head(10)
    print(sample_df.to_string(index=False))
    
    return result_df

if __name__ == "__main__":
    result = calculate_adj_anci_metrics()
