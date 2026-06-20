from neo4j import GraphDatabase

# 1. 初始化驱动
driver = GraphDatabase.driver("bolt://localhost:7687", auth=("neo4j", "zxcvbnm,"))


# 2. 定义查询函数
def get_purchased_products(customer_name):
    # 使用 execute_query 直接运行 Cypher 语句
    records, summary, keys = driver.execute_query(
        """
        MATCH (c:Customer)-[:BUY]->(p)
        WHERE c.name = $name
        RETURN p.name AS product_name
        """,
        name=customer_name,  # 传入参数，防止 SQL/Cypher 注入
        database_="neo4j",  # 可选：指定数据库，默认是 neo4j
    )

    # 3. 解析并返回结果列表
    return [record["product_name"] for record in records]


# --- 测试调用 ---
if __name__ == "__main__":
    products = get_purchased_products("张三")
    print(f"张三购买的商品有: {products}")

    # 记得在程序结束时关闭驱动
    driver.close()
