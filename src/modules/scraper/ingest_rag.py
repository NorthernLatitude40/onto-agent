import os
import requests
from bs4 import BeautifulSoup
from langchain_text_splitters import RecursiveCharacterTextSplitter
import openai
import psycopg2
from pgvector.psycopg2 import register_vector
from langchain_ollama import OllamaEmbeddings

# 配置你的 OpenAI API Key 和 PostgreSQL 数据库连接
# 建议在实际运行前通过环境变量设置
embeddings = OllamaEmbeddings(
    model="nomic-embed-text",
    base_url="http://host.docker.internal:11435"
)
DB_CONN_STRING = os.environ.get("DATABASE_URL")


def fetch_site_content(url: str):
    """抓取目标网页并提取干净的文本"""
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    response = requests.get(url, headers=headers, timeout=10)
    response.raise_for_status()
    
    soup = BeautifulSoup(response.text, 'html.parser')
    
    # 提取所有段落和标题文本
    text_blocks = []
    for tag in soup.find_all(['h1', 'h2', 'h3', 'p', 'li']):
        txt = tag.get_text(strip=True)
        if len(txt) > 15:  # 过滤太短的无意义字符
            text_blocks.append(txt)
            
    return "\n".join(text_blocks)

def generate_embedding(text: str):
    """调用 Ollama Embedding 模型生成向量"""
    return embeddings.embed_query(text)

def process_and_store():
    target_url = "https://getlostinnz.co.nz/"
    print(f"正在从 {target_url} 抓取内容...")
    
    try:
        raw_text = fetch_site_content(target_url)
    except Exception as e:
        print(f"抓取失败: {e}")
        return

    # 1. 文本切片 (Chunking)
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=600,
        chunk_overlap=100,
        length_function=len,
    )
    chunks = text_splitter.split_text(raw_text)
    print(f"文本切片完成，共生成 {len(chunks)} 个 Chunk。")

    # 2. 连接数据库
    conn = psycopg2.connect(DB_CONN_STRING)
    register_vector(conn)
    cur = conn.cursor()

    try:
        for idx, chunk in enumerate(chunks):
            title = f"Get Lost NZ 首页切片 #{idx + 1}"
            print(f"正在处理并向量化第 {idx + 1}/{len(chunks)} 个片段...")
            
            # 生成向量
            embedding = generate_embedding(chunk)
            
            # 写入 PostgreSQL rag_documents 表
            # 配合 source_url 和 chunk 索引实现幂等插入或更新
            cur.execute(
                """
                INSERT INTO rag_documents (title, content, category, source_url, metadata, embedding)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (source_url) DO NOTHING;
                """,
                (
                    title,
                    chunk,
                    "vehicle_guide",
                    f"{target_url}#chunk_{idx}",
                    '{"operator": "Get Lost NZ", "source": "homepage"}',
                    embedding
                )
            )
        conn.commit()
        print("🎉 所有文本切片已成功向量化并入库到 PostgreSQL (pgvector)！")
    except Exception as e:
        conn.rollback()
        print(f"入库失败: {e}")
    finally:
        cur.close()
        conn.close()

if __name__ == "__main__":
    process_and_store()