-- 1. 如果資料庫存在就先刪除，然後建立全新資料庫
DROP DATABASE IF EXISTS my_agent_db;
CREATE DATABASE my_agent_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE my_agent_db;

-- 2. 建立用戶表 (users)
CREATE TABLE users (
    user_id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(50) NOT NULL,
    email VARCHAR(100),
    registration_date DATE
);

-- 3. 建立商品表 (products)
CREATE TABLE products (
    product_id INT AUTO_INCREMENT PRIMARY KEY,
    product_name VARCHAR(100) NOT NULL,
    category VARCHAR(50),
    price DECIMAL(10, 2),
    stock INT
);

-- 4. 建立訂單表 (orders)
CREATE TABLE orders (
    order_id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT,
    order_date DATE,
    total_amount DECIMAL(10, 2),
    FOREIGN KEY (user_id) REFERENCES users(user_id)
);

-- 5. 建立訂單明細表 (order_items)
CREATE TABLE order_items (
    item_id INT AUTO_INCREMENT PRIMARY KEY,
    order_id INT,                               -- 關聯到 orders 表
    product_id INT,                             -- 關聯到 products 表
    quantity INT NOT NULL,                      -- 購買數量
    price_per_unit DECIMAL(10, 2) NOT NULL,     -- 購買時的單價
    FOREIGN KEY (order_id) REFERENCES orders(order_id),
    FOREIGN KEY (product_id) REFERENCES products(product_id)
);

-- 6. 插入用戶測試數據
-- 生成的自增 ID：張小明 (1), 李美玲 (2), 王大同 (3)
INSERT INTO users (username, email, registration_date) VALUES
('張小明', 'xiaoming@email.com', '2026-01-15'),
('李美玲', 'meiling@email.com', '2026-02-20'),
('王大同', 'datong@email.com', '2026-03-05');

-- 7. 插入商品測試數據
-- 生成的自增 ID：iPhone (1), 耳機 (2), 辦公椅 (3), 隨行杯 (4)
INSERT INTO products (product_name, category, price, stock) VALUES
('iPhone 17 Pro', '電子產品', 36900.00, 50),
('無線降噪耳機', '電子產品', 5490.00, 120),
('人體工學辦公椅', '家具', 4500.00, 30),
('保溫隨行杯', '生活用品', 790.00, 200);

-- 8. 插入訂單測試數據
-- 生成的自增 ID：訂單 A (1), 訂單 B (2), 訂單 C (3)
INSERT INTO orders (user_id, order_date, total_amount) VALUES
(1, '2026-06-10', 36900.00),  -- 訂單ID: 1 (張小明)
(1, '2026-06-12', 790.00),   -- 訂單ID: 2 (張小明)
(2, '2026-06-14', 5490.00);  -- 訂單ID: 3 (李美玲)

-- 9. 插入訂單明細測試數據 (補上這段，Agent 才能查到具體商品！)
INSERT INTO order_items (order_id, product_id, quantity, price_per_unit) VALUES
(1, 1, 1, 36900.00),  -- 訂單 1 包含：1 支 iPhone 17 Pro
(2, 4, 1, 790.00),    -- 訂單 2 包含：1 個 保溫隨行杯
(3, 2, 1, 5490.00);   -- 訂單 3 包含：1 副 無線降噪耳機
