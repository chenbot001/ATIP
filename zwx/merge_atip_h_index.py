#!/usr/bin/env python3
"""
将 author_citation_metrics.csv 中的 atip_h_index 根据 author_id 
对应到 top100_hindex_authors.csv 的新列中
"""

import pandas as pd
import os

def merge_atip_h_index():
    """
    合并两个文件，添加 atip_h_index 列
    """
    
    try:
        # 读取两个文件
        print("正在读取文件...")
        
        # 读取 top100 文件
        top100_file = "data/metric/top100_hindex_authors.csv"
        if not os.path.exists(top100_file):
            # 如果在 metric 文件夹中找不到，尝试在根目录
            top100_file = "top100_hindex_authors.csv"
        
        df_top100 = pd.read_csv(top100_file)
        print(f"成功读取 top100 文件: {len(df_top100)} 行")
        
        # 读取 author_citation_metrics 文件
        metrics_file = "data/author_citation_metrics.csv"
        df_metrics = pd.read_csv(metrics_file)
        print(f"成功读取 metrics 文件: {len(df_metrics)} 行")
        
        # 显示原始数据信息
        print(f"\nTop100 文件列名: {list(df_top100.columns)}")
        print(f"Metrics 文件列名: {list(df_metrics.columns)}")
        
        # 只保留需要的列（author_id 和 atip_h_index）
        df_metrics_subset = df_metrics[['author_id', 'atip_h_index']].copy()
        
        # 合并数据 - 左连接，保留所有 top100 的记录
        print("\n正在合并数据...")
        df_merged = df_top100.merge(
            df_metrics_subset, 
            on='author_id', 
            how='left'
        )
        
        # 检查合并结果
        print(f"合并后数据形状: {df_merged.shape}")
        print(f"成功匹配的记录数: {df_merged['atip_h_index'].notna().sum()}")
        print(f"未匹配的记录数: {df_merged['atip_h_index'].isna().sum()}")
        
        # 将未匹配的 NaN 值填充为 0 或保持 NaN（根据需要）
        # df_merged['atip_h_index'] = df_merged['atip_h_index'].fillna(0)
        
        # 显示前几行结果
        print("\n前10行结果预览:")
        print(df_merged.head(10).to_string(index=False))
        
        # 保存结果
        output_file = "top100_hindex_authors_with_atip.csv"
        df_merged.to_csv(output_file, index=False, encoding='utf-8')
        
        print(f"\n✅ 合并完成！结果已保存到: {output_file}")
        
        # 显示一些统计信息
        print("\n=== 统计信息 ===")
        print(f"原始 h_index 范围: {df_merged['h_index'].min()} - {df_merged['h_index'].max()}")
        if df_merged['atip_h_index'].notna().any():
            valid_atip = df_merged['atip_h_index'].dropna()
            print(f"ATIP h_index 范围: {valid_atip.min()} - {valid_atip.max()}")
            print(f"ATIP h_index 平均值: {valid_atip.mean():.2f}")
        
        # 显示对比信息（原始 h_index vs atip_h_index）
        print("\n=== 前10名对比（原始 h_index vs ATIP h_index）===")
        comparison = df_merged[['author_name', 'h_index', 'atip_h_index']].head(10)
        print(comparison.to_string(index=False))
        
        return True
        
    except FileNotFoundError as e:
        print(f"❌ 错误：找不到文件 {e}")
        return False
    except Exception as e:
        print(f"❌ 处理过程中出现错误: {str(e)}")
        return False

def main():
    """主函数"""
    print("开始合并 atip_h_index 数据...")
    success = merge_atip_h_index()
    
    if success:
        print("\n🎉 合并操作完成成功！")
    else:
        print("\n❌ 合并操作失败，请检查错误信息")

if __name__ == "__main__":
    main()
