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

# 检查operation_logs表是否存在
cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='operation_logs'")
table_exists = cursor.fetchone() is not None
print(f"operation_logs表是否存在: {table_exists}")

if not table_exists:
    # 创建operation_logs表
    print("创建operation_logs表...")
    cursor.execute('''CREATE TABLE operation_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    action TEXT NOT NULL,
                    target_id TEXT,
                    target_type TEXT,
                    message TEXT NOT NULL,
                    details TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )''')
    conn.commit()

# 测试插入一条日志记录
print("测试插入一条日志记录...")
try:
    cursor.execute('''INSERT INTO operation_logs (user_id, action, target_id, target_type, message, details) 
                   VALUES (?, ?, ?, ?, ?, ?)''', 
               ('test_user', 'test_action', 'test_target', 'test_type', '测试日志', '测试详细信息'))
    conn.commit()
    print("日志插入成功")
except Exception as e:
    print(f"日志插入失败: {str(e)}")
    import traceback
    traceback.print_exc()

# 检查是否有日志记录
print("检查是否有日志记录...")
cursor.execute('SELECT COUNT(*) FROM operation_logs')
count = cursor.fetchone()[0]
print(f'operation_logs表中的记录数量: {count}')

# 查看所有日志记录
if count > 0:
    print("所有日志记录:")
cursor.execute('SELECT * FROM operation_logs ORDER BY created_at DESC')
logs = cursor.fetchall()
for log in logs:
    print(log)

# 关闭连接
conn.close()
print("测试完成")
