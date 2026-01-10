import sqlite3
from pathlib import Path

# 数据库文件路径
BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
DB_FILE = DATA_DIR / "db.sqlite"

# 确保数据目录存在
DATA_DIR.mkdir(parents=True, exist_ok=True)

print(f"数据库文件路径: {DB_FILE}")
print(f"数据库文件是否存在: {DB_FILE.exists()}")

# 连接到数据库
conn = sqlite3.connect(str(DB_FILE))
cursor = conn.cursor()

# 测试：插入一条特定用户的操作日志
user_id = "84603e1bb00944bba4fe08ce55ab3552"  # 实际用户ID
print(f"\n测试插入一条用户 {user_id} 的操作日志...")
try:
    cursor.execute('''INSERT INTO operation_logs (user_id, action, target_id, target_type, message, details) 
                   VALUES (?, ?, ?, ?, ?, ?)''', 
               (user_id, 'delete', 'test_file_id', 'file', '删除文件', '文件名: 测试文件.txt'))
    conn.commit()
    print("日志插入成功")
except Exception as e:
    print(f"日志插入失败: {str(e)}")
    import traceback
    traceback.print_exc()

# 测试：查询特定用户的操作日志
print(f"\n查询用户 {user_id} 的操作日志:")
cursor.execute('SELECT * FROM operation_logs WHERE user_id = ? ORDER BY created_at DESC', (user_id,))
logs = cursor.fetchall()
print(f"找到 {len(logs)} 条日志")
for log in logs:
    print(log)

# 测试：查询所有操作日志
print("\n查询所有操作日志:")
cursor.execute('SELECT * FROM operation_logs ORDER BY created_at DESC')
all_logs = cursor.fetchall()
print(f"总共找到 {len(all_logs)} 条日志")
for log in all_logs:
    print(log)

# 关闭连接
conn.close()
print("测试完成")
