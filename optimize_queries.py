# 优化数据库查询函数
import re

# 读取app.py文件内容
with open('app.py', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. 优化get_file_by_id函数
new_get_file_by_id = '''def get_file_by_id(file_id, user_id=None, check_owner=True):
    conn = get_db()
    try:
        # 获取文件基本信息
        if check_owner and user_id:
            file_query = 'SELECT * FROM files WHERE id = ? AND user_id = ?'
            file_params = (file_id, user_id)
        else:
            file_query = 'SELECT * FROM files WHERE id = ?'
            file_params = (file_id,)
        
        row = conn.execute(file_query, file_params).fetchone()
        
        if not row:
            return None
        
        # 使用JOIN优化查询，减少数据库查询次数
        # 1. 同时获取点赞数和收藏数
        stats_query = """
            SELECT 
                (SELECT COUNT(*) FROM likes WHERE file_id = ?) as like_count,
                (SELECT COUNT(*) FROM favorites WHERE file_id = ?) as favorite_count
        """
        stats_result = conn.execute(stats_query, (file_id, file_id)).fetchone()
        like_count = stats_result['like_count']
        favorite_count = stats_result['favorite_count']
        
        # 2. 获取文件分类
        categories_query = """
            SELECT c.id, c.name, c.description
            FROM categories c 
            JOIN file_categories fc ON c.id = fc.category_id 
            WHERE fc.file_id = ?
        """
        category_rows = conn.execute(categories_query, (file_id,)).fetchall()
        categories = [{
            "id": row["id"],
            "name": row["name"],
            "description": row["description"]
        } for row in category_rows]
        
        # 3. 获取文件标签
        tags_query = """
            SELECT t.id, t.name
            FROM tags t 
            JOIN file_tags ft ON t.id = ft.tag_id 
            WHERE ft.file_id = ?
        """
        tag_rows = conn.execute(tags_query, (file_id,)).fetchall()
        tags = [{
            "id": row["id"],
            "name": row["name"]
        } for row in tag_rows]
        
        # 检查 created_at 字段是否存在
        created_at = row["created_at"] if "created_at" in row.keys() else ""
        
        return {
            "id": row["id"], 
            "filename": row["filename"], 
            "stored_name": row["stored_name"],
            "path": row["path"], 
            "size": row["size"], 
            "dkfile": json.loads(row["dkfile"] if row["dkfile"] else "{}"),
            "project_name": row["project_name"], 
            "project_desc": row["project_desc"],
            "user_id": row["user_id"],
            "like_count": like_count,
            "favorite_count": favorite_count,
            "categories": categories,
            "tags": tags,
            "created_at": created_at
        }
    finally:
        conn.close()'''

# 2. 优化get_favorite_files函数
new_get_favorite_files = '''def get_favorite_files(user_id):
    """获取用户收藏的文件列表，只返回HTML文件且排除项目文件夹中的文件"""
    conn = get_db()
    try:
        # 使用JOIN和子查询优化查询，减少数据库查询次数
        # 1. 获取所有收藏文件及基本信息
        files_query = """
            SELECT f.*, fav.created_at as favorite_created_at
            FROM files f 
            JOIN favorites fav ON f.id = fav.file_id 
            WHERE fav.user_id = ? 
            AND f.filename LIKE ? 
            AND (f.folder_id IS NULL OR f.folder_id = "") 
            ORDER BY fav.created_at DESC
        """
        files_params = (user_id, '%.html')
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
                "created_at": row["created_at"] if "created_at" in row.keys() else "",
                "favorite_created_at": row["favorite_created_at"]
            })
        
        return result
    finally:
        conn.close()'''

# 使用正则表达式替换函数
content = re.sub(r'def get_file_by_id\(file_id, user_id=None, check_owner=True\):.*?return None\s*finally:\s*conn.close()', 
                new_get_file_by_id, content, flags=re.DOTALL)

content = re.sub(r'def get_favorite_files\(user_id\):.*?return result\s*finally:\s*conn.close()', 
                new_get_favorite_files, content, flags=re.DOTALL)

# 写入优化后的内容
with open('app.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("数据库查询函数优化完成！")