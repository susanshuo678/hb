import sqlite3

# 连接数据库
conn = sqlite3.connect('app/database/bounty.db')
cursor = conn.cursor()

def add_column(table, col_def):
    try:
        cursor.execute(f"ALTER TABLE {table} ADD COLUMN {col_def}")
        print(f"✅ {table} 表添加字段成功: {col_def}")
    except Exception as e:
        print(f"ℹ️ {table} 字段可能已存在: {e}")

# 1. 升级 Tasks 表：增加价格模式、关联素材分类
add_column("tasks", "price_mode VARCHAR DEFAULT 'fixed'") # fixed/dynamic
add_column("tasks", "material_category_id INTEGER DEFAULT NULL") # 关联的素材库分类ID

# 2. 升级 Submissions 表：增加最终结算金额、关联的具体素材ID
add_column("submissions", "final_amount FLOAT DEFAULT 0")
add_column("submissions", "assigned_material_id INTEGER DEFAULT NULL") # 领取的素材ID

# 3. 创建素材库相关表
try:
    # 素材分类表 (如：小红书3月第1批、新品宣发A组)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS material_categories (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name VARCHAR,
        total_count INTEGER DEFAULT 0,
        used_count INTEGER DEFAULT 0,
        created_at DATETIME
    )
    """)
    
    # 具体素材表 (每一条图文)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS materials (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        category_id INTEGER,
        content TEXT,          -- 文案
        images TEXT,           -- 图片路径(逗号分隔)
        status VARCHAR DEFAULT 'unused', -- unused(闲置), locked(被占用), used(已核销)
        used_by_user_id INTEGER,
        used_at DATETIME,
        created_at DATETIME,
        FOREIGN KEY(category_id) REFERENCES material_categories(id)
    )
    """)
    print("✅ 素材库相关表创建成功")
except Exception as e:
    print(f"❌ 建表失败: {e}")

conn.commit()
conn.close()
print("🎉 数据库升级完成 V2！")