# 修复get_all_files函数中的重复代码问题
import re

# 读取app.py文件内容
with open('app.py', 'r', encoding='utf-8') as f:
    content = f.read()

# 定义新的get_all_files函数
new_get_all_files = '''def get_all_files(user_id=None):
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
        file_ids_str = ",".join([f"'{file_id}'" for file_id in file_ids])
        
        # 2. 批量获取点赞数
        likes_query = f"SELECT file_id, COUNT(*) as count FROM likes WHERE file_id IN ({file_ids_str}) GROUP BY file_id"
        likes_result = conn.execute(likes_query).fetchall()
        like_counts = {row["file_id"]: row["count"] for row in likes_result}
        
        # 3. 批量获取收藏数
        favorites_query = f"SELECT file_id, COUNT(*) as count FROM favorites WHERE file_id IN ({file_ids_str}) GROUP BY file_id"
        favorites_result = conn.execute(favorites_query).fetchall()
        favorite_counts = {row["file_id"]: row["count"] for row in favorites_result}
        
        # 4. 批量获取文件分类
        categories_query = f"""
            SELECT fc.file_id, c.id, c.name, c.description
            FROM file_categories fc
            JOIN categories c ON fc.category_id = c.id
            WHERE fc.file_id IN ({file_ids_str})
        """
        categories_result = conn.execute(categories_query).fetchall()
        
        # 按file_id分组分类
        categories_map = {}
        for row in categories_result:
            file_id = row["file_id"]
            if file_id not in categories_map:
                categories_map[file_id] = []
            categories_map[file_id].append({
                "id": row["id"],
                "name": row["name"],
                "description": row["description"]
            })
        
        # 5. 批量获取文件标签
        tags_query = f"""
            SELECT ft.file_id, t.id, t.name
            FROM file_tags ft
            JOIN tags t ON ft.tag_id = t.id
            WHERE ft.file_id IN ({file_ids_str})
        """
        tags_result = conn.execute(tags_query).fetchall()
        
        # 按file_id分组标签
        tags_map = {}
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
        conn.close()'''

# 使用正则表达式替换整个get_all_files函数
pattern = r'def get_all_files\(user_id=None\):.*?return result\s*finally:\s*conn.close()' 
new_content = re.sub(pattern, new_get_all_files, content, flags=re.DOTALL)

# 写入修复后的内容
with open('app.py', 'w', encoding='utf-8') as f:
    f.write(new_content)

print("修复完成！")