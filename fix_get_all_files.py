#!/usr/bin/env python3
# 手动修复get_all_files函数

with open('app.py', 'r', encoding='utf-8') as f:
    content = f.read()

# 定义修复后的get_all_files函数
fixed_get_all_files = '''def get_all_files(user_id=None):
    conn = get_db()
    try:
        # 使用JOIN和子查询优化查询，减少数据库连接次数
        # 1. 获取所有文件及基本信息
        if user_id:
            files_query = "SELECT * FROM files WHERE user_id = ? ORDER BY id DESC"
            files_params = (user_id,)
        else:
            files_query = "SELECT * FROM files ORDER BY id DESC"
            files_params = ()
        
        rows = conn.execute(files_query, files_params).fetchall()
        
        # 如果没有文件，直接返回空列表
        if not rows:
            return []
        
        # 获取所有文件ID
        file_ids = [row["id"] for row in rows]
        
        # 初始化结果字典
        like_counts = {}
        favorite_counts = {}
        categories_map = {}
        tags_map = {}
        
        if file_ids:
            # 2. 批量获取点赞数 - 使用参数化查询
            placeholders = ",".join(["?"] * len(file_ids))
            likes_query = f"SELECT file_id, COUNT(*) as count FROM likes WHERE file_id IN ({placeholders}) GROUP BY file_id"
            likes_result = conn.execute(likes_query, file_ids).fetchall()
            like_counts = {row["file_id"]: row["count"] for row in likes_result}
            
            # 3. 批量获取收藏数 - 使用参数化查询
            favorites_query = f"SELECT file_id, COUNT(*) as count FROM favorites WHERE file_id IN ({placeholders}) GROUP BY file_id"
            favorites_result = conn.execute(favorites_query, file_ids).fetchall()
            favorite_counts = {row["file_id"]: row["count"] for row in favorites_result}
            
            # 4. 批量获取文件分类 - 使用参数化查询
            categories_query = f"""
                SELECT fc.file_id, c.id, c.name, c.description
                FROM file_categories fc
                JOIN categories c ON fc.category_id = c.id
                WHERE fc.file_id IN ({placeholders})
            """
            categories_result = conn.execute(categories_query, file_ids).fetchall()
            
            # 按file_id分组分类
            for row in categories_result:
                file_id = row["file_id"]
                if file_id not in categories_map:
                    categories_map[file_id] = []
                categories_map[file_id].append({
                    "id": row["id"],
                    "name": row["name"],
                    "description": row["description"]
                })
            
            # 5. 批量获取文件标签 - 使用参数化查询
            tags_query = f"""
                SELECT ft.file_id, t.id, t.name
                FROM file_tags ft
                JOIN tags t ON ft.tag_id = t.id
                WHERE ft.file_id IN ({placeholders})
            """
            tags_result = conn.execute(tags_query, file_ids).fetchall()
            
            # 按file_id分组标签
            for row in tags_result:
                file_id = row["file_id"]
                if file_id not in tags_map:
                    tags_map[file_id] = []
                tags_map[file_id].append({
                    "id": row["id"],
                    "name": row["name"]
                })
        
        # 6. 组装结果
        result = []
        for row in rows:
            file_id = row["id"]
            result.append({
                "id": file_id, 
                "filename": row["filename"], 
                "stored_name": row["stored_name"],
                "path": row["path"], 
                "size": row["size"], 
                "dkfile": json.loads(row["dkfile"] if row["dkfile"] else "{}"),
                "project_name": row["project_name"], 
                "project_desc": row["project_desc"],
                "like_count": like_counts.get(file_id, 0),
                "favorite_count": favorite_counts.get(file_id, 0),
                "categories": categories_map.get(file_id, []),
                "tags": tags_map.get(file_id, []),
                "created_at": row["created_at"] if "created_at" in row.keys() else ""
            })
        
        return result
    finally:
        conn.close()
'''

# 替换原有的get_all_files函数
import re
# 使用正则表达式匹配原函数（包括重复代码）
pattern = r'def get_all_files.*?def '  # 匹配从def get_all_files开始到下一个def函数开始
# 确保匹配整个函数，包括换行符
fixed_content = re.sub(pattern, fixed_get_all_files + 'def ', content, flags=re.DOTALL)

# 如果函数是最后一个函数，需要特殊处理
if 'def get_all_files' in fixed_content and 'def ' not in fixed_content.split('def get_all_files')[-1]:
    # 函数是最后一个，匹配到文件结束
    pattern = r'def get_all_files.*$'  # 匹配从def get_all_files开始到文件结束
    fixed_content = re.sub(pattern, fixed_get_all_files, content, flags=re.DOTALL)

# 写入修复后的内容
with open('app.py', 'w', encoding='utf-8') as f:
    f.write(fixed_content)

print("修复完成！")
