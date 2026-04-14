import pandas as pd
import numpy as np

def clean_and_format_data(input_file, output_file):
    """
    清洗和格式化数据：
    1. 将authorship字段格式化为列表格式 [xxx,xxx,...,xxx]
    2. 去除primary_location.source.id或title为空白的数据
    """
    
    print(f"开始处理文件: {input_file}")
    
    try:
        # 尝试不同的编码格式读取CSV文件
        encodings_to_try = ['utf-8', 'latin-1', 'iso-8859-1', 'cp1252']
        df = None
        
        for encoding in encodings_to_try:
            try:
                print(f"尝试使用 {encoding} 编码读取文件...")
                df = pd.read_csv(input_file, encoding=encoding)
                print(f"✓ 成功使用 {encoding} 编码读取文件")
                break
            except UnicodeDecodeError as e:
                print(f"✗ {encoding} 编码失败: {e}")
                continue
        
        # 如果所有编码都失败，尝试自动检测
        if df is None:
            print("尝试自动检测编码...")
            import chardet
            with open(input_file, 'rb') as f:
                raw_data = f.read()
                encoding_result = chardet.detect(raw_data)
                detected_encoding = encoding_result['encoding']
                confidence = encoding_result['confidence']
                print(f"检测到编码: {detected_encoding} (置信度: {confidence:.2f})")
            
            if detected_encoding:
                df = pd.read_csv(input_file, encoding=detected_encoding)
            else:
                # 最后尝试使用错误忽略模式
                print("使用错误忽略模式读取文件...")
                df = pd.read_csv(input_file, encoding='utf-8', errors='ignore')
        
        print(f"原始数据形状: {df.shape}")
        print(f"原始数据行数: {len(df)}")
        
        # 检查缺失值情况
        print("\n缺失值统计 (处理前):")
        key_columns = ['primary_location.source.id', 'title']
        for col in key_columns:
            if col in df.columns:
                missing_count = df[col].isna().sum()
                print(f"  {col}: {missing_count} 个缺失值 ({missing_count/len(df)*100:.1f}%)")
        
        # 步骤1: 去除primary_location.source.id或title为空白的数据
        initial_count = len(df)
        
        # 创建过滤条件
        filter_conditions = []
        if 'primary_location.source.id' in df.columns:
            # 同时检查NaN和空字符串
            filter_conditions.append(
                df['primary_location.source.id'].notna() & 
                (df['primary_location.source.id'].astype(str) != '') &
                (df['primary_location.source.id'].astype(str) != 'nan')
            )
        if 'title' in df.columns:
            filter_conditions.append(
                df['title'].notna() & 
                (df['title'].astype(str) != '') &
                (df['title'].astype(str) != 'nan')
            )
        
        # 应用过滤条件
        if filter_conditions:
            # 合并所有条件（使用逻辑与）
            combined_condition = filter_conditions[0]
            for condition in filter_conditions[1:]:
                combined_condition = combined_condition & condition
            
            df_cleaned = df[combined_condition].copy()
        else:
            df_cleaned = df.copy()
        
        removed_count = initial_count - len(df_cleaned)
        print(f"\n数据清洗: 移除了 {removed_count} 行空白数据")
        print(f"清洗后数据形状: {df_cleaned.shape}")
        
        # 步骤2: 格式化authorship字段为列表格式
        authorship_columns = [
            'authorships.author.id',
            'authorships.author.display_name'
        ]
        
        for col in authorship_columns:
            if col in df_cleaned.columns:
                print(f"\n处理列: {col}")
                
                # 统计原始格式
                sample_value = df_cleaned[col].iloc[0] if len(df_cleaned) > 0 else "N/A"
                print(f"  示例原始值: {str(sample_value)[:100]}...")
                
                # 格式化函数
                def format_as_list(x):
                    if pd.isna(x) or str(x).strip() in ['', 'nan', 'None']:
                        return "[]"
                    elif isinstance(x, str):
                        # 如果已经是列表格式，保持原样
                        if x.startswith('[') and x.endswith(']'):
                            return x
                        # 如果是管道符分隔，转换为列表格式
                        elif '|' in x:
                            items = [f'"{item.strip()}"' for item in x.split('|') if item.strip() and item.strip() != 'nan']
                            return f"[{','.join(items)}]" if items else "[]"
                        # 如果是单个值，包装成列表
                        elif x.strip():
                            return f'["{x.strip()}"]'
                        # 空值返回空列表
                        else:
                            return "[]"
                    else:
                        return "[]"
                
                # 应用格式化
                df_cleaned[col] = df_cleaned[col].apply(format_as_list)
                
                # 显示处理后的示例
                formatted_sample = df_cleaned[col].iloc[0] if len(df_cleaned) > 0 else "N/A"
                print(f"  格式化后示例: {formatted_sample[:100]}...")
        
        # 检查其他可能有多值的字段，也进行格式化
        other_multi_value_columns = [
            'primary_topic.subfield.id',
            'primary_topic.subfield.display_name', 
            'primary_topic.field.id',
            'primary_topic.field.display_name',
            'primary_location.source.id',
            'primary_location.source.display_name',
            'primary_location.source.type'
        ]
        
        for col in other_multi_value_columns:
            if col in df_cleaned.columns:
                print(f"\n检查列: {col}")
                
                # 检查是否有管道符分隔的值
                has_pipe = df_cleaned[col].apply(
                    lambda x: '|' in str(x) if pd.notna(x) and str(x) != 'nan' else False
                ).any()
                
                if has_pipe:
                    print(f"  检测到多值数据，进行格式化...")
                    df_cleaned[col] = df_cleaned[col].apply(
                        lambda x: f"[{','.join([f'\"{item.strip()}\"' for item in str(x).split('|') if item.strip() and item.strip() != 'nan'])}]" 
                        if pd.notna(x) and str(x) != 'nan' and '|' in str(x) else x
                    )
        
        # 最终数据质量检查
        print(f"\n最终数据质量检查:")
        print(f"处理后数据形状: {df_cleaned.shape}")
        print(f"有效数据行数: {len(df_cleaned)}")
        
        # 检查关键字段的缺失值（处理后）
        print(f"\n缺失值统计 (处理后):")
        for col in key_columns:
            if col in df_cleaned.columns:
                missing_count = df_cleaned[col].isna().sum()
                print(f"  {col}: {missing_count} 个缺失值 ({missing_count/len(df_cleaned)*100:.1f}%)")
        
        # 保存处理后的数据（使用UTF-8编码保存）
        df_cleaned.to_csv(output_file, index=False, encoding='utf-8')
        print(f"\n处理完成! 输出文件: {output_file}")
        
        # 显示前几行作为预览
        print(f"\n数据预览 (前2行):")
        preview_columns = [col for col in df_cleaned.columns if any(keyword in col for keyword in ['author', 'title', 'source.id'])]
        preview_df = df_cleaned[preview_columns].head(2) if preview_columns else df_cleaned.head(2)
        print(preview_df.to_string(max_colwidth=50))
        
        return df_cleaned
        
    except Exception as e:
        print(f"处理过程中发生错误: {e}")
        import traceback
        traceback.print_exc()
        return None

def validate_formatted_data(df):
    """
    验证格式化后的数据
    """
    if df is not None:
        print(f"\n格式化验证:")
        
        # 检查authorship字段格式
        authorship_cols = [col for col in df.columns if 'author' in col]
        for col in authorship_cols:
            if col in df.columns:
                sample = df[col].iloc[0] if len(df) > 0 else "N/A"
                is_list_format = isinstance(sample, str) and sample.startswith('[') and sample.endswith(']')
                print(f"  {col}: {'✓ 列表格式' if is_list_format else '✗ 非列表格式'} -> {str(sample)[:80]}...")

# 使用示例
if __name__ == "__main__":
    # 设置文件路径
    input_csv = "FILTERED_DATA_wType.csv"
    output_csv = "CLEANED_FORMATTED_DATA_wType.csv"
    
    # 执行处理
    cleaned_data = clean_and_format_data(input_csv, output_csv)
    
    # 验证结果
    validate_formatted_data(cleaned_data)