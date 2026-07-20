#!/usr/bin/env python3
"""
处理作者数据，生成前100名h_index最高的作者列表

功能：
1. 创建新列 author_name，将 first_name 和 last_name 用空格连接
2. 保留指定列：author_id, author_name, h_index, publication_count
3. 按照 h_index 从高到低排序
4. 只保留前 100 名作者
5. 将结果保存为新的 CSV 文件
"""

import pandas as pd
import os

def process_authors_data(input_file, output_file="top100_hindex_authors.csv"):
    """
    处理作者数据并生成前100名h_index最高的作者列表
    
    参数:
    input_file (str): 输入CSV文件路径
    output_file (str): 输出CSV文件路径
    """
    
    try:
        # 读取CSV文件
        print(f"正在读取文件: {input_file}")
        df = pd.read_csv(input_file)
        print(f"成功读取 {len(df)} 行数据")
        
        # 显示原始数据的基本信息
        print(f"原始数据列名: {list(df.columns)}")
        print(f"数据形状: {df.shape}")
        
        # 检查必需的列是否存在
        required_columns = ['author_id', 'first_name', 'last_name', 'h_index', 'publication_count']
        missing_columns = [col for col in required_columns if col not in df.columns]
        
        if missing_columns:
            print(f"警告：缺少以下列: {missing_columns}")
            return False
        
        # 1. 创建新列 author_name，将 first_name 和 last_name 用空格连接
        print("正在创建 author_name 列...")
        df['author_name'] = df['first_name'].astype(str) + ' ' + df['last_name'].astype(str)
        
        # 2. 保留指定的列
        print("正在选择指定列...")
        columns_to_keep = ['author_id', 'author_name', 'h_index', 'publication_count']
        df_selected = df[columns_to_keep].copy()
        
        # 3. 按照 h_index 从高到低排序
        print("正在按 h_index 排序...")
        df_sorted = df_selected.sort_values('h_index', ascending=False)
        
        # 4. 只保留前 100 名作者
        print("正在筛选前100名作者...")
        df_top100 = df_sorted.head(100)
        
        # 显示处理后的数据信息
        print(f"处理后数据形状: {df_top100.shape}")
        print(f"h_index 范围: {df_top100['h_index'].min()} - {df_top100['h_index'].max()}")
        
        # 5. 将结果保存为新的 CSV 文件
        print(f"正在保存结果到: {output_file}")
        df_top100.to_csv(output_file, index=False, encoding='utf-8')
        
        # 显示前10行结果
        print("\n前10行结果预览:")
        print(df_top100.head(10).to_string(index=False))
        
        print(f"\n✅ 处理完成！结果已保存到: {output_file}")
        return True
        
    except FileNotFoundError:
        print(f"❌ 错误：找不到文件 {input_file}")
        return False
    except Exception as e:
        print(f"❌ 处理过程中出现错误: {str(e)}")
        return False

def main():
    """主函数"""
    
    # 输入文件路径 - 根据您的需求修改这里
    # 原始路径：/mnt/data/03d1345a-df87-4ca5-b95b-33d134b0c4d7.csv
    # 当前示例使用工作目录中的文件
    
    # 选项1：使用您提到的原始文件路径（如果在Linux/Mac环境下）
    # input_file = "/mnt/data/03d1345a-df87-4ca5-b95b-33d134b0c4d7.csv"
    
    # 选项2：使用当前工作目录中的文件
    input_file = "data/database/megatable_authors.csv"
    
    # 选项3：如果文件在其他位置，请修改为正确的路径
    # input_file = "your_file_path_here.csv"
    
    # 输出文件路径
    output_file = "top100_hindex_authors.csv"
    
    # 检查输入文件是否存在
    if not os.path.exists(input_file):
        print(f"❌ 输入文件不存在: {input_file}")
        print("请修改 input_file 变量为正确的文件路径")
        return
    
    # 处理数据
    success = process_authors_data(input_file, output_file)
    
    if success:
        print(f"\n🎉 所有操作完成成功！")
        print(f"📁 输出文件: {output_file}")
    else:
        print("\n❌ 处理失败，请检查错误信息")

if __name__ == "__main__":
    main()
