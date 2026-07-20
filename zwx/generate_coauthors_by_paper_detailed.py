#!/usr/bin/env python3
"""
生成每篇论文的详细作者信息CSV文件

从authorships.csv中提取每篇论文的所有作者信息，包括作者顺序，
输出为coauthors_by_paper.csv文件，每位作者占据一行。

输出字段：
- paper_id: 论文ID
- researcher_id: 研究者ID
- author_name: 作者姓名
- authorship_order: 作者在论文中的顺序（从1开始）
"""

import pandas as pd
import os
from typing import List, Dict

def generate_detailed_coauthors_by_paper(input_file: str, output_file: str) -> None:
    """
    生成每篇论文的详细作者信息CSV文件
    
    Args:
        input_file: 输入的authorships.csv文件路径
        output_file: 输出的coauthors_by_paper.csv文件路径
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
    
    print("处理每篇论文的作者信息...")
    
    # 按paper_id分组，为每篇论文的作者添加顺序信息
    detailed_coauthors_data = []
    
    grouped = df.groupby('paper_id')
    total_papers = len(grouped)
    
    for i, (paper_id, group) in enumerate(grouped):
        # 为每篇论文的作者按出现顺序编号
        for order, (_, row) in enumerate(group.iterrows(), start=1):
            author_info = {
                'paper_id': int(paper_id),
                'researcher_id': int(row['researcher_id']) if pd.notna(row['researcher_id']) else None,
                'author_name': str(row['author_name']) if pd.notna(row['author_name']) else None,
                'authorship_order': order
            }
            detailed_coauthors_data.append(author_info)
        
        # 显示进度
        if (i + 1) % 1000 == 0 or (i + 1) == total_papers:
            print(f"已处理 {i + 1}/{total_papers} 篇论文 ({(i + 1) / total_papers * 100:.1f}%)")
    
    # 创建DataFrame并保存
    result_df = pd.DataFrame(detailed_coauthors_data)
    
    print(f"保存结果到: {output_file}")
    result_df.to_csv(output_file, index=False, encoding='utf-8')
    
    print(f"完成! 共处理 {len(result_df)} 条作者记录")
    
    # 显示一些统计信息
    print("\n=== 统计信息 ===")
    print(f"总作者记录数: {len(result_df)}")
    print(f"独特论文数: {result_df['paper_id'].nunique()}")
    print(f"独特作者数: {result_df['researcher_id'].nunique()}")
    
    # 统计每篇论文的作者数量分布
    authors_per_paper = result_df.groupby('paper_id').size()
    print(f"平均每篇论文作者数: {authors_per_paper.mean():.2f}")
    print(f"每篇论文作者数中位数: {authors_per_paper.median():.0f}")
    print(f"最多作者数的论文: {authors_per_paper.max()} 位作者")
    print(f"最少作者数的论文: {authors_per_paper.min()} 位作者")
    
    # 统计作者顺序分布
    order_counts = result_df['authorship_order'].value_counts().sort_index()
    print(f"\n作者顺序分布（前10位）:")
    for order in range(1, min(11, len(order_counts) + 1)):
        if order in order_counts.index:
            print(f"  第{order}作者: {order_counts[order]} 人次")
    
    # 显示前几个示例
    print("\n=== 前5个示例 ===")
    sample_papers = result_df['paper_id'].unique()[:2]  # 取前2篇论文作为示例
    
    for paper_id in sample_papers:
        paper_authors = result_df[result_df['paper_id'] == paper_id].sort_values('authorship_order')
        print(f"\n论文ID: {paper_id}")
        print(f"作者数量: {len(paper_authors)}")
        print("作者列表:")
        for _, author in paper_authors.iterrows():
            print(f"  {author['authorship_order']}. ID: {author['researcher_id']}, 姓名: {author['author_name']}")

def main():
    """主函数"""
    
    # 文件路径设置
    data_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data')
    input_file = os.path.join(data_dir, 'authorships.csv')
    output_file = os.path.join(data_dir, 'coauthors_by_paper.csv')
    
    # 检查输入文件是否存在
    if not os.path.exists(input_file):
        print(f"输入文件不存在: {input_file}")
        return
    
    print("=== 生成每篇论文的详细作者信息 ===")
    print(f"输入文件: {input_file}")
    print(f"输出文件: {output_file}")
    print()
    
    # 生成详细作者信息
    generate_detailed_coauthors_by_paper(input_file, output_file)

if __name__ == "__main__":
    main()
