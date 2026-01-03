import sqlite3

# 连接数据库
conn = sqlite3.connect('data/db.sqlite')
cursor = conn.cursor()

# 获取所有用户信息
print("数据库中的所有用户:")
print("ID, Email, Username, Role")
print("-" * 60)

cursor.execute("SELECT * FROM users")
rows = cursor.fetchall()

for row in rows:
    # 打印所有字段，查看完整结构
    print(f"完整行数据: {row}")
    print(f"字段数量: {len(row)}")
    
    # 尝试获取role字段（索引6）
    role = "user"  # 默认值
    if len(row) > 6:  # 如果有role字段
        role = row[6]
    
    print(f"处理后的用户: {row[0]}, {row[1]}, {row[2]}, {role}")
    print("-" * 60)

# 关闭连接
conn.close()
