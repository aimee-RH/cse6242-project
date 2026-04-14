import pandas as pd
import numpy as np

def filter_csv_columns(input_file, output_file):
    """
    读取CSV文件，仅保留指定的字段，并保存为新文件
    
    Parameters:
    input_file (str): 输入CSV文件路径
    output_file (str): 输出CSV文件路径
    """
    
    # 定义要保留的字段列表
    columns_to_keep = [
        'id',
        'title', 
        'publication_year',
        'fwci',
        'cited_by_count',
        'citation_normalized_percentile.value',
        'citation_normalized_percentile.is_in_top_1_percent',
        'citation_normalized_percentile.is_in_top_10_percent',
        'primary_topic.subfield.id',
        'primary_topic.subfield.display_name', 
        'primary_topic.field.id',
        'primary_topic.field.display_name',
        'primary_location.source.id',
        'primary_location.source.display_name',
        'primary_location.source.type',  # 新增字段
        'authorships.author.id',
        'authorships.author.display_name'
    ]
    
    print(f"开始处理文件: {input_file}")
    print(f"准备保留 {len(columns_to_keep)} 个字段")
    
    try:
        # 读取CSV文件
        df = pd.read_csv(input_file)
        print(f"原始数据形状: {df.shape}")
        
        # 检查哪些字段实际存在于文件中
        existing_columns = [col for col in columns_to_keep if col in df.columns]
        missing_columns = [col for col in columns_to_keep if col not in df.columns]
        
        print(f"找到 {len(existing_columns)} 个目标字段")
        
        if missing_columns:
            print(f"警告: 以下 {len(missing_columns)} 个字段在文件中不存在:")
            for col in missing_columns:
                print(f"  - {col}")
            
            # 显示最接近的可用列名（用于调试）
            print("\n可用的类似列名:")
            all_columns = df.columns.tolist()
            for missing_col in missing_columns[:5]:  # 只显示前5个
                similar = [col for col in all_columns if missing_col.split('.')[-1] in col]
                if similar:
                    print(f"  '{missing_col}' 类似: {similar[:3]}")
        
        # 仅保留存在的字段
        filtered_df = df[existing_columns]
        
        # 检查数据质量
        print(f"\n数据质量检查:")
        print(f"处理后的数据形状: {filtered_df.shape}")
        print(f"总行数: {len(filtered_df)}")
        
        # 检查关键字段的缺失值
        key_columns = ['id', 'title', 'publication_year', 'primary_location.source.type']
        for col in key_columns:
            if col in filtered_df.columns:
                missing_count = filtered_df[col].isna().sum()
                print(f"  {col}: {missing_count} 个缺失值 ({missing_count/len(filtered_df)*100:.1f}%)")
        
        # 如果 primary_location.source.type 存在，显示其值分布
        if 'primary_location.source.type' in filtered_df.columns:
            type_distribution = filtered_df['primary_location.source.type'].value_counts()
            print(f"\nprimary_location.source.type 分布:")
            for type_val, count in type_distribution.head(10).items():
                print(f"  {type_val}: {count} 篇论文")
        
        # 保存处理后的数据
        filtered_df.to_csv(output_file, index=False)
        print(f"\n处理完成! 输出文件: {output_file}")
        
        # 显示前几行作为预览
        print(f"\n数据预览 (前3行):")
        print(filtered_df.head(3).to_string(max_colwidth=30))
        
        return filtered_df
        
    except FileNotFoundError:
        print(f"错误: 找不到输入文件 {input_file}")
        return None
    except Exception as e:
        print(f"处理过程中发生错误: {e}")
        return None

def check_data_types(df):
    """
    检查数据框中各列的数据类型
    """
    if df is not None:
        print(f"\n各列数据类型:")
        for col in df.columns:
            dtype = df[col].dtype
            unique_count = df[col].nunique() if df[col].dtype == 'object' else 'N/A'
            sample_value = df[col].iloc[0] if len(df) > 0 else "N/A"
            print(f"  {col}: {dtype} (唯一值: {unique_count})")
            print(f"    示例: {str(sample_value)[:50]}...")

# 使用示例
if __name__ == "__main__":
    # 设置文件路径
    input_csv = "ALLDATA.csv"
    output_csv = "FILTERED_DATA_wTpye.csv"
    
    # 执行处理
    filtered_data = filter_csv_columns(input_csv, output_csv)
    
    # 检查数据类型
    check_data_types(filtered_data)