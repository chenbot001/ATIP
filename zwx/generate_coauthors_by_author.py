#!/usr/bin/env python3
"""
生成每位作者与合作者的合作关系CSV文件

从authorships.csv中分析每位作者与其合作者之间的合作关系，
统计合作次数并按次数排序，输出为coauthors_by_author.csv文件。

输出字段：
- researcher_id: 本作者ID
- author_name: 本作者姓名
- coauthor_id: 合作者ID
- coauthor_name: 合作者姓名
- num_collaborations: 与该合作者合作的论文数量
- rank: 合作者在该作者的合作列表中的排名（按合作次数降序）
"""

import pandas as pd
import os
from typing import Dict, List, Tuple
from collections import defaultdict

def generate_coauthors_by_author(input_file: str, output_file: str) -> None:
    """
    生成每位作者与合作者的合作关系CSV文件
    
    Args:
        input_file: 输入的authorships.csv文件路径
        output_file: 输出的coauthors_by_author.csv文件路径
    """
    
    print(f"读取文件: {input_file}")
    
    # 读取authorships数据
    try:
        df = pd.read_csv(input_file)
        print(f"成功读取 {len(df)} 行数据")
    except Exception as e:
        print(f"读取文件出错: {e}")
        return
    
    # 检查必要的列是否存在
    required_columns = ['researcher_id', 'paper_id', 'author_name']
    missing_columns = [col for col in required_columns if col not in df.columns]
    if missing_columns:
        print(f"缺少必要的列: {missing_columns}")
        return
    
    print("分析作者合作关系...")
    
    # 为提高性能，预先创建作者ID到姓名的映射
    author_id_to_name = dict(zip(df['researcher_id'], df['author_name']))
    
    # 统计每对作者之间的合作次数
    collaboration_counts = defaultdict(int)  # (author1_id, author2_id) -> count
    
    # 按论文分组处理，使用更高效的方法
    print("统计合作次数...")
    grouped = df.groupby('paper_id')['researcher_id'].apply(list)
    total_papers = len(grouped)
    
    for i, (paper_id, authors) in enumerate(grouped.items()):
        # 对于每篇论文的每对作者，增加合作计数
        for j, author1 in enumerate(authors):
            for k, author2 in enumerate(authors):
                if j != k:  # 不统计自己与自己的合作
                    # 确保较小的ID在前，避免重复计数
                    pair = (min(author1, author2), max(author1, author2))
                    collaboration_counts[pair] += 1
        
        if (i + 1) % 1000 == 0 or (i + 1) == total_papers:
            print(f"已处理 {i + 1}/{total_papers} 篇论文 ({(i + 1) / total_papers * 100:.1f}%)")
    
    print("构建作者合作关系表...")
    
    # 构建每位作者的合作者列表
    author_collaborations = defaultdict(list)  # author_id -> [(coauthor_id, count), ...]
    
    for (author1, author2), count in collaboration_counts.items():
        # 由于我们用了min/max确保顺序，需要为两个方向都添加记录
        author_collaborations[author1].append((author2, count))
        author_collaborations[author2].append((author1, count))
    
    # 为每位作者的合作者按合作次数排序并添加排名
    coauthor_relationships = []
    
    unique_authors = list(author_id_to_name.keys())  # 使用实际存在的作者ID
    total_authors = len(unique_authors)
    
    for i, author_id in enumerate(unique_authors):
        author_name = author_id_to_name[author_id]
        
        # 获取该作者的所有合作者，按合作次数降序排序
        collaborators = author_collaborations.get(author_id, [])
        collaborators.sort(key=lambda x: x[1], reverse=True)  # 按合作次数降序
        
        # 为每个合作者添加排名
        for rank, (coauthor_id, num_collaborations) in enumerate(collaborators, 1):
            coauthor_name = author_id_to_name.get(coauthor_id, "Unknown")
            
            coauthor_relationships.append({
                'researcher_id': author_id,
                'author_name': author_name,
                'coauthor_id': coauthor_id,
                'coauthor_name': coauthor_name,
                'num_collaborations': num_collaborations,
                'rank': rank
            })
        
        if (i + 1) % 1000 == 0 or (i + 1) == total_authors:
            print(f"已处理 {i + 1}/{total_authors} 位作者 ({(i + 1) / total_authors * 100:.1f}%)")
    
    # 创建DataFrame并保存
    result_df = pd.DataFrame(coauthor_relationships)
    
    if len(result_df) == 0:
        print("警告: 没有找到任何合作关系")
        return
    
    # 按researcher_id和rank排序，确保输出有序
    result_df = result_df.sort_values(['researcher_id', 'rank'])
    
    print(f"保存结果到: {output_file}")
    result_df.to_csv(output_file, index=False, encoding='utf-8')
    
    print(f"完成! 共处理 {len(result_df)} 条合作关系记录")
    
    # 显示统计信息
    print("\n=== 统计信息 ===")
    print(f"总合作关系记录数: {len(result_df)}")
    print(f"独特作者数: {result_df['researcher_id'].nunique()}")
    print(f"独特合作者数: {result_df['coauthor_id'].nunique()}")
    
    # 统计每位作者的合作者数量
    collaborators_per_author = result_df.groupby('researcher_id').size()
    print(f"平均每位作者的合作者数量: {collaborators_per_author.mean():.2f}")
    print(f"每位作者合作者数量中位数: {collaborators_per_author.median():.0f}")
    print(f"最多合作者数量: {collaborators_per_author.max()}")
    print(f"最少合作者数量: {collaborators_per_author.min()}")
    
    # 统计合作次数分布
    collaboration_counts_dist = result_df['num_collaborations'].value_counts().sort_index()
    print(f"\n合作次数分布（前10种）:")
    for count in sorted(collaboration_counts_dist.index, reverse=True)[:10]:
        print(f"  合作{count}次: {collaboration_counts_dist[count]} 对")
    
    # 找出合作最多的作者对
    max_collaboration = result_df['num_collaborations'].max()
    most_collaborative = result_df[result_df['num_collaborations'] == max_collaboration].iloc[0]
    print(f"\n合作最多的作者对:")
    print(f"  {most_collaborative['author_name']} (ID: {most_collaborative['researcher_id']}) ")
    print(f"  与 {most_collaborative['coauthor_name']} (ID: {most_collaborative['coauthor_id']})")
    print(f"  共合作 {max_collaboration} 次")
    
    # 显示前几个示例
    print("\n=== 前5个示例 ===")
    sample_authors = result_df['researcher_id'].unique()[:2]  # 取前2位作者作为示例
    
    for author_id in sample_authors:
        author_data = result_df[result_df['researcher_id'] == author_id].head(5)  # 只显示前5个合作者
        if len(author_data) > 0:
            author_name = author_data.iloc[0]['author_name']
            print(f"\n作者: {author_name} (ID: {author_id})")
            print(f"合作者总数: {len(result_df[result_df['researcher_id'] == author_id])}")
            print("前5个合作者:")
            for _, row in author_data.iterrows():
                print(f"  {row['rank']}. {row['coauthor_name']} (ID: {row['coauthor_id']}) - {row['num_collaborations']}次合作")

def main():
    """主函数"""
    
    # 文件路径设置
    data_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data')
    input_file = os.path.join(data_dir, 'authorships.csv')
    output_file = os.path.join(data_dir, 'coauthors_by_author.csv')
    
    # 检查输入文件是否存在
    if not os.path.exists(input_file):
        print(f"输入文件不存在: {input_file}")
        return
    
    print("=== 生成每位作者与合作者的合作关系 ===")
    print(f"输入文件: {input_file}")
    print(f"输出文件: {output_file}")
    print()
    
    # 生成合作关系数据
    generate_coauthors_by_author(input_file, output_file)

if __name__ == "__main__":
    main()
