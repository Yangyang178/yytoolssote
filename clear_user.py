import sqlite3
import os

# 数据库文件路径
db_path = os.path.join(os.path.dirname(__file__), 'data', 'db.sqlite3')

# 确保data目录存在
os.makedirs(os.path.dirname(db_path), exist_ok=True)

def init_db():
    """初始化数据库，创建所有必要的表"""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # 创建users表
        cursor.execute('''CREATE TABLE IF NOT EXISTS users (
                        id TEXT PRIMARY KEY,
                        email TEXT NOT NULL UNIQUE,
                        username TEXT NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )''')
        
        # 创建verification_codes表
        cursor.execute('''CREATE TABLE IF NOT EXISTS verification_codes (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        email TEXT NOT NULL,
                        code TEXT NOT NULL,
                        purpose TEXT NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        expires_at TIMESTAMP NOT NULL
                    )''')
        
        # 创建files表
        cursor.execute('''CREATE TABLE IF NOT EXISTS files (
                        id TEXT PRIMARY KEY,
                        filename TEXT NOT NULL,
                        stored_name TEXT NOT NULL,
                        path TEXT NOT NULL,
                        size INTEGER NOT NULL,
                        dkfile TEXT,
                        project_name TEXT,
                        project_desc TEXT,
                        user_id TEXT DEFAULT "default_user"
                    )''')
        
        # 创建access_logs表
        cursor.execute('''CREATE TABLE IF NOT EXISTS access_logs (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        file_id TEXT NOT NULL,
                        user_id TEXT,
                        action TEXT NOT NULL,
                        ip_address TEXT,
                        user_agent TEXT,
                        access_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )''')
        
        conn.commit()
        print("数据库初始化成功")
        return True
    except Exception as e:
        print(f"数据库初始化失败：{str(e)}")
        conn.rollback()
        return False
    finally:
        conn.close()

def clear_user_by_email(email):
    """删除指定邮箱的用户记录"""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # 删除用户记录
        cursor.execute('DELETE FROM users WHERE email = ?', (email,))
        deleted_rows = cursor.rowcount
        conn.commit()
        
        # 删除该用户的验证代码记录
        cursor.execute('DELETE FROM verification_codes WHERE email = ?', (email,))
        deleted_codes = cursor.rowcount
        conn.commit()
        
        # 删除该用户的文件记录
        cursor.execute('DELETE FROM files WHERE user_id IN (SELECT id FROM users WHERE email = ?)', (email,))
        deleted_files = cursor.rowcount
        conn.commit()
        
        # 删除该用户的访问日志记录
        cursor.execute('DELETE FROM access_logs WHERE user_id IN (SELECT id FROM users WHERE email = ?)', (email,))
        deleted_logs = cursor.rowcount
        conn.commit()
        
        print(f"成功删除邮箱 {email} 的记录：")
        print(f"- 用户记录：{deleted_rows} 条")
        print(f"- 验证代码：{deleted_codes} 条")
        print(f"- 文件记录：{deleted_files} 条")
        print(f"- 访问日志：{deleted_logs} 条")
        return True
    except Exception as e:
        print(f"删除失败：{str(e)}")
        conn.rollback()
        return False
    finally:
        conn.close()

if __name__ == "__main__":
    # 初始化数据库
    init_db()
    
    # 要删除的邮箱
    email_to_clear = "1990909398@qq.com"
    clear_user_by_email(email_to_clear)