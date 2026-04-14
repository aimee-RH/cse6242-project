import pandas as pd
import plotly.express as px

# 数据预处理函数
def preprocess_data(df):
    # 数据预处理：清理引号
    df['research_topic'] = df['research_topic'].str.replace('"', '')
    df['sample_title'] = df['sample_title'].str.replace('"', '')

    # 创建完整的年份范围（确保连续性）
    all_years = range(df['year'].min(), df['year'].max() + 1)
    all_topics = df['research_topic'].unique()

    # 创建完整的时间序列数据
    full_index = pd.MultiIndex.from_product([all_years, all_topics], names=['year', 'research_topic'])
    full_df = pd.DataFrame(index=full_index).reset_index()

    # 合并原始数据
    merged_df = pd.merge(full_df, df, on=['year', 'research_topic'], how='left')
    merged_df['paper_count'] = merged_df['paper_count'].fillna(0)

    return merged_df


def create_clean_streamgraph(df, top_n=15):
    # 计算每个主题的总论文数
    topic_totals = df.groupby('research_topic')['paper_count'].sum().sort_values(ascending=False)
    top_topics = topic_totals.head(top_n).index
    
    filtered_df = df[df['research_topic'].isin(top_topics)].copy()
    
    # 数据清洗
    filtered_df = filtered_df.fillna({
        'sample_title': 'NaN',
        'research_topic': 'NaN',
        'paper_count': 0
    })
    
    # 创建简洁的悬浮文本
    filtered_df['hover_text'] = (
        filtered_df['research_topic'] + "<br>" +
        "Number of Papers:" + filtered_df['paper_count'].astype(int).astype(str)
    )
    
    fig = px.area(filtered_df, 
                  x='year', 
                  y='paper_count', 
                  color='research_topic',
                  title=f'Research Topics Stream Graph (Top {top_n})',
                  labels={'paper_count': 'Number of Papers', 'year': 'Year'},
                  hover_name='hover_text')
    
    # 优化布局
    fig.update_layout(
        height=600,
        showlegend=True,
        legend=dict(
            orientation="v",
            yanchor="top",
            y=0.98,
            xanchor="left",
            x=1.02,
            font=dict(size=11)
        ),
        hovermode='x unified',
        margin=dict(r=150, t=80, b=80, l=80),
        hoverlabel=dict(
            bgcolor="white",
            font_size=11,
            font_family="Arial"
        )
    )
    
    # 简化悬浮模板
    fig.update_traces(
        hovertemplate='%{hovertext}<extra></extra>'
    )
    
    return fig

# 运行
if __name__ == "__main__":
    df = pd.read_csv('research_area_by_year_utf8.csv')
    merged_df = preprocess_data(df)
    fig = create_clean_streamgraph(merged_df, top_n=15)
    fig.show()