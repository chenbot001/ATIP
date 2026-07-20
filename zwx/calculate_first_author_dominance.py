#!/usr/bin/env python3
"""
计算作者的第一作者占主导地位的比例
根据 authorships.csv 和 author_megatable.csv 计算 first_author_dominance
"""

import pandas as pd
import numpy as np

def calculate_first_author_dominance():
    """
    计算每位作者的第一作者占主导地位比例
    """
    
    # 读取数据文件
    print("正在读取数据文件...")
    authorships_df = pd.read_csv('data/authorships.csv')
    author_megatable_df = pd.read_csv('author_megatable.csv')
    
    print(f"authorships.csv 包含 {len(authorships_df)} 条记录")
    print(f"author_megatable.csv 包含 {len(author_megatable_df)} 位作者")
    
    # 从 authorships.csv 中计算每位作者的统计数据
    print("正在计算作者统计数据...")
    
    # 计算每位作者的总论文数
    total_papers = authorships_df.groupby('author_id').size().reset_index(name='total_paper_count')
    
    # 计算每位作者的第一作者论文数
    first_author_papers = authorships_df[authorships_df['is_first_author'] == True].groupby('author_id').size().reset_index(name='first_author_paper_count')
    
    # 合并统计数据
    author_stats = total_papers.merge(first_author_papers, on='author_id', how='left')
    
    # 填充缺失值（没有第一作者论文的作者）
    author_stats['first_author_paper_count'] = author_stats['first_author_paper_count'].fillna(0)
    
    # 计算 first_author_dominance
    author_stats['first_author_dominance'] = np.where(
        author_stats['total_paper_count'] > 0,
        author_stats['first_author_paper_count'] / author_stats['total_paper_count'],
        0.0
    )
    
    # 保留三位小数
    author_stats['first_author_dominance'] = author_stats['first_author_dominance'].round(3)
    
    print(f"计算得到 {len(author_stats)} 位作者的统计数据")
    
    # 只保留在 author_megatable.csv 中出现的作者
    target_authors = set(author_megatable_df['author_id'].unique())
    author_stats_filtered = author_stats[author_stats['author_id'].isin(target_authors)]
    
    print(f"其中 {len(author_stats_filtered)} 位作者在目标列表中")
    
    # 合并到 author_megatable
    print("正在合并数据...")
    
    # 如果原表已经有 first_author_dominance 列，先删除它
    if 'first_author_dominance' in author_megatable_df.columns:
        author_megatable_df = author_megatable_df.drop('first_author_dominance', axis=1)
    
    # 合并新计算的 first_author_dominance
    result_df = author_megatable_df.merge(
        author_stats_filtered[['author_id', 'first_author_dominance']], 
        on='author_id', 
        how='left'
    )
    
    # 对于没有在 authorships.csv 中找到的作者，设置 first_author_dominance = 0.0
    result_df['first_author_dominance'] = result_df['first_author_dominance'].fillna(0.0)
    
    # 保存结果
    output_file = 'author_megatable_with_dominance.csv'
    result_df.to_csv(output_file, index=False)
    
    print(f"结果已保存到 {output_file}")
    
    # 显示统计信息
    print("\n统计信息:")
    print(f"总作者数: {len(result_df)}")
    print(f"有发表记录的作者数: {len(result_df[result_df['first_author_dominance'] > 0])}")
    print(f"first_author_dominance 平均值: {result_df['first_author_dominance'].mean():.3f}")
    print(f"first_author_dominance 中位数: {result_df['first_author_dominance'].median():.3f}")
    print(f"first_author_dominance 最大值: {result_df['first_author_dominance'].max():.3f}")
    
    # 显示一些样本数据
    print("\n样本数据:")
    sample_df = result_df[['author_id', 'first_name', 'last_name', 'first_author_dominance']].head(10)
    print(sample_df.to_string(index=False))
    
    return result_df

if __name__ == "__main__":
    result = calculate_first_author_dominance()
