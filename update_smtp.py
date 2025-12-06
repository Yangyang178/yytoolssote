import os
import sqlite3

# 获取当前目录
current_dir = os.path.dirname(os.path.abspath(__file__))

# 数据库文件路径
db_path = os.path.join(current_dir, 'data', 'db.sqlite')

def update_smtp_config(email, password):
    """更新SMTP配置"""
    env_file = os.path.join(current_dir, '.env')
    
    # 读取.env文件内容
    with open(env_file, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    # 更新SMTP配置
    new_lines = []
    for line in lines:
        if line.startswith('SMTP_USERNAME'):
            new_lines.append(f'SMTP_USERNAME={email}\n')
        elif line.startswith('SMTP_PASSWORD'):
            new_lines.append(f'SMTP_PASSWORD={password}\n')
        elif line.startswith('SMTP_FROM'):
            new_lines.append(f'SMTP_FROM={email}\n')
        else:
            new_lines.append(line)
    
    # 写入更新后的内容
    with open(env_file, 'w', encoding='utf-8') as f:
        f.writelines(new_lines)
    
    print(f"SMTP配置已更新：")
    print(f"- 邮箱：{email}")
    print(f"- 授权码：{password}")
    return True

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
        
        print(f"成功删除邮箱 {email} 的记录：")
        print(f"- 用户记录：{deleted_rows} 条")
        print(f"- 验证代码：{deleted_codes} 条")
        return True
    except Exception as e:
        print(f"删除失败：{str(e)}")
        conn.rollback()
        return False
    finally:
        conn.close()

if __name__ == "__main__":
    # 示例用法：update_smtp_config('your_email@qq.com', 'your_password')
    pass