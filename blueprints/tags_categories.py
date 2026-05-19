from flask import Blueprint, request, jsonify, session


class _LazyAppImports:
    def __getattr__(self, name):
        from app import get_db, log_message, api_response, get_like_count, get_favorite_count
        _mapping = {
            'get_db': get_db,
            'log_message': log_message,
            'api_response': api_response,
            'get_like_count': get_like_count,
            'get_favorite_count': get_favorite_count,
        }
        if name not in _mapping:
            raise AttributeError(f"module 'app' has no attribute '{name}'")
        return _mapping[name]


_app = _LazyAppImports()

tags_categories_bp = Blueprint('tags_categories', __name__)


@tags_categories_bp.route('/api/search', methods=['GET'], endpoint='api_search')
def api_search():
    query = request.args.get('q', '').strip()
    search_type = request.args.get('type', 'all')
    limit = request.args.get('limit', 20, type=int)

    if not query:
        return _app.api_response(success=True, data={'files': [], 'ai_contents': [], 'total': 0})

    conn = _app.get_db()
    try:
        results = {'files': [], 'ai_contents': [], 'total': 0}

        if search_type in ('all', 'files'):
            like_query = f'%{query}%'
            file_rows = conn.execute('''
                SELECT f.id, f.filename, f.stored_name, f.size, f.project_name,
                       f.project_desc, f.user_id, f.created_at, f.folder_id,
                       u.username
                FROM files f LEFT JOIN users u ON f.user_id = u.id
                WHERE (f.filename LIKE ? OR f.project_name LIKE ? OR f.project_desc LIKE ?)
                  AND f.is_deleted IS NULL
                ORDER BY f.created_at DESC LIMIT ?
            ''', (like_query, like_query, like_query, limit)).fetchall()

            for r in file_rows:
                fd = dict(r)
                fd['like_count'] = _app.get_like_count(fd['id'])
                fd['favorite_count'] = _app.get_favorite_count(fd['id'])
                tag_rows = conn.execute(
                    '''SELECT t.name FROM tags t JOIN file_tags ft ON t.id = ft.tag_id
                       WHERE ft.file_id = ?''', (fd['id'],)).fetchall()
                fd['tags'] = [t['name'] for t in tag_rows]
                cat_rows = conn.execute(
                    '''SELECT c.name FROM categories c JOIN file_categories fc ON c.id = fc.category_id
                       WHERE fc.file_id = ?''', (fd['id'],)).fetchall()
                fd['categories'] = [c['name'] for c in cat_rows]
                results['files'].append(fd)

        if search_type in ('all', 'ai') and 'user_id' in session:
            like_query = f'%{query}%'
            ai_rows = conn.execute('''
                SELECT id, ai_function, prompt, response, created_at
                FROM ai_contents
                WHERE user_id = ? AND (prompt LIKE ? OR response LIKE ?)
                ORDER BY created_at DESC LIMIT ?
            ''', (session['user_id'], like_query, like_query, limit)).fetchall()
            results['ai_contents'] = [{
                'id': r['id'],
                'ai_function': r['ai_function'],
                'preview': (r['prompt'][:100] + '...') if len(r['prompt']) > 100 else r['prompt'],
                'created_at': r['created_at']
            } for r in ai_rows]

        results['total'] = len(results['files']) + len(results['ai_contents'])
        return _app.api_response(success=True, data=results)
    finally:
        conn.close()


@tags_categories_bp.route('/api/search/suggestions', methods=['GET'], endpoint='api_search_suggestions')
def api_search_suggestions():
    query = request.args.get('q', '').strip()
    if not query or len(query) < 2:
        return _app.api_response(success=True, data={'suggestions': []})

    conn = _app.get_db()
    try:
        like_query = f'%{query}%'
        prefix_query = f'{query}%'

        filename_rows = conn.execute(
            '''SELECT DISTINCT filename FROM files
               WHERE filename LIKE ? AND is_deleted IS NULL
               ORDER BY created_at DESC LIMIT 5''',
            (prefix_query,)).fetchall()

        project_rows = conn.execute(
            '''SELECT DISTINCT project_name FROM files
               WHERE project_name LIKE ? AND project_name != '' AND is_deleted IS NULL
               ORDER BY created_at DESC LIMIT 3''',
            (like_query,)).fetchall()

        tag_rows = conn.execute(
            '''SELECT DISTINCT name FROM tags WHERE name LIKE ? LIMIT 3''',
            (like_query,)).fetchall()

        suggestions = []
        for r in filename_rows:
            suggestions.append({'type': 'file', 'text': r['filename']})
        for r in project_rows:
            suggestions.append({'type': 'project', 'text': r['project_name']})
        for r in tag_rows:
            suggestions.append({'type': 'tag', 'text': r['name']})

        return _app.api_response(success=True, data={'suggestions': suggestions[:8]})
    finally:
        conn.close()


@tags_categories_bp.route('/api/search/history', methods=['GET', 'POST', 'DELETE'], endpoint='api_search_history')
def api_search_history():
    if 'user_id' not in session:
        return _app.api_response(success=False, message='请先登录', code=401)

    if request.method == 'GET':
        conn = _app.get_db()
        try:
            rows = conn.execute(
                '''SELECT DISTINCT message as query FROM operation_logs
                   WHERE user_id = ? AND action = 'search' AND message IS NOT NULL
                   ORDER BY created_at DESC LIMIT 10''',
                (session['user_id'],)).fetchall()
            history = [r['query'] for r in rows]
            return _app.api_response(success=True, data={'history': history})
        finally:
            conn.close()

    elif request.method == 'POST':
        data = request.get_json(silent=True) or {}
        q = data.get('q', '').strip()
        if q:
            _app.log_message(log_type='operation', log_level='INFO',
                       message=q, user_id=session['user_id'],
                       action='search', request=request)
        return _app.api_response(success=True)

    elif request.method == 'DELETE':
        conn = _app.get_db()
        try:
            conn.execute(
                "DELETE FROM operation_logs WHERE user_id = ? AND action = 'search'",
                (session['user_id'],))
            conn.commit()
            return _app.api_response(success=True, message='搜索历史已清除')
        finally:
            conn.close()


@tags_categories_bp.route('/api/categories', methods=['GET'], endpoint='api_get_categories')
def api_get_categories():
    conn = _app.get_db()
    try:
        rows = conn.execute('SELECT id, name, description, created_at FROM categories').fetchall()
        categories = [{'id': r['id'], 'name': r['name'], 'description': r['description'], 'created_at': r['created_at']} for r in rows]
        return _app.api_response(success=True, data={'categories': categories})
    finally:
        conn.close()


@tags_categories_bp.route('/api/tags/stats', methods=['GET'], endpoint='api_tags_stats')
def api_tags_stats():
    conn = _app.get_db()
    try:
        rows = conn.execute('''SELECT t.id, t.name, COUNT(ft.file_id) as file_count
                               FROM tags t LEFT JOIN file_tags ft ON t.id = ft.tag_id
                               GROUP BY t.id ORDER BY file_count DESC''').fetchall()
        stats = [{'id': r['id'], 'name': r['name'], 'file_count': r['file_count']} for r in rows]
        return _app.api_response(success=True, data={'tags': stats})
    finally:
        conn.close()


@tags_categories_bp.route('/api/storage-stats', methods=['GET'], endpoint='api_storage_stats')
def api_storage_stats():
    if 'user_id' not in session:
        return _app.api_response(success=False, message='请先登录', code=401)

    from app import get_user_storage_usage
    from datetime import datetime, timedelta

    try:
        usage = get_user_storage_usage(session['user_id'])

        conn = _app.get_db()
        try:
            type_rows = conn.execute('''
                SELECT
                    CASE
                        WHEN filename LIKE '%.html' OR filename LIKE '%.htm' THEN 'HTML'
                        WHEN filename LIKE '%.css' THEN 'CSS'
                        WHEN filename LIKE '%.js' OR filename LIKE '%.mjs' THEN 'JavaScript'
                        WHEN filename LIKE '%.ts' OR filename LIKE '%.tsx' THEN 'TypeScript'
                        WHEN filename LIKE '%.py' THEN 'Python'
                        WHEN filename LIKE '%.java' THEN 'Java'
                        WHEN filename LIKE '%.c' OR filename LIKE '%.cpp' OR filename LIKE '%.h' THEN 'C/C++'
                        WHEN filename LIKE '%.go' THEN 'Go'
                        WHEN filename LIKE '%.rs' THEN 'Rust'
                        WHEN filename LIKE '%.vue' THEN 'Vue'
                        WHEN filename LIKE '%.json' THEN 'JSON'
                        WHEN filename LIKE '%.xml' THEN 'XML'
                        WHEN filename LIKE '%.yaml' OR filename LIKE '%.yml' THEN 'YAML'
                        WHEN filename LIKE '%.toml' OR filename LIKE '%.ini' OR filename LIKE '%.cfg' THEN 'Config'
                        WHEN filename LIKE '%.md' OR filename LIKE '%.markdown' THEN 'Markdown'
                        WHEN filename LIKE '%.txt' OR filename LIKE '%.log' THEN 'Text'
                        WHEN filename LIKE '%.csv' THEN 'CSV'
                        WHEN filename LIKE '%.png' THEN 'PNG'
                        WHEN filename LIKE '%.jpg' OR filename LIKE '%.jpeg' THEN 'JPEG'
                        WHEN filename LIKE '%.gif' THEN 'GIF'
                        WHEN filename LIKE '%.svg' THEN 'SVG'
                        WHEN filename LIKE '%.webp' THEN 'WebP'
                        WHEN filename LIKE '%.ico' THEN 'ICO'
                        WHEN filename LIKE '%.mp4' OR filename LIKE '%.avi' OR filename LIKE '%.mov'
                            OR filename LIKE '%.mkv' OR filename LIKE '%.wmv' THEN 'Video'
                        WHEN filename LIKE '%.mp3' OR filename LIKE '%.wav' OR filename LIKE '%.flac'
                            OR filename LIKE '%.aac' OR filename LIKE '%.ogg' THEN 'Audio'
                        WHEN filename LIKE '%.pdf' THEN 'PDF'
                        WHEN filename LIKE '%.doc' OR filename LIKE '%.docx' THEN 'Word'
                        WHEN filename LIKE '%.xls' OR filename LIKE '%.xlsx' THEN 'Excel'
                        WHEN filename LIKE '%.ppt' OR filename LIKE '%.pptx' THEN 'PPT'
                        WHEN filename LIKE '%.zip' OR filename LIKE '%.rar' OR filename LIKE '%.7z'
                            OR filename LIKE '%.tar' OR filename LIKE '%.gz' THEN 'Archive'
                        WHEN filename LIKE '%.ttf' OR filename LIKE '%.woff' OR filename LIKE '%.woff2'
                            OR filename LIKE '%.otf' THEN 'Font'
                        WHEN filename LIKE '%.exe' OR filename LIKE '%.dmg' OR filename LIKE '%.msi'
                            OR filename LIKE '%.deb' OR filename LIKE '%.rpm' THEN 'Executable'
                        WHEN filename LIKE '%.sh' OR filename LIKE '%.bat' OR filename LIKE '%.ps1' THEN 'Script'
                        ELSE 'Other'
                    END as file_type,
                    COUNT(*) as file_count,
                    COALESCE(SUM(size), 0) as total_size
                FROM files WHERE user_id = ? AND COALESCE(is_deleted, 0) = 0
                GROUP BY file_type ORDER BY total_size DESC
            ''', (session['user_id'],)).fetchall()
            type_stats = [{'file_type': r['file_type'], 'file_count': r['file_count'], 'total_size': r['total_size']} for r in type_rows]

            large_files_rows = conn.execute('''
                SELECT f.id, f.filename, f.size, f.created_at, f.folder_id,
                       fo.name as folder_name
                FROM files f
                LEFT JOIN folders fo ON f.folder_id = fo.id
                WHERE f.user_id = ? AND COALESCE(f.is_deleted, 0) = 0
                ORDER BY f.size DESC LIMIT 10
            ''', (session['user_id'],)).fetchall()
            large_files = []
            for r in large_files_rows:
                large_files.append({
                    'id': r['id'], 'filename': r['filename'], 'size': r['size'],
                    'created_at': r['created_at'],
                    'folder_name': r['folder_name'] if r['folder_name'] else '未分类'
                })

            folder_stats_rows = conn.execute('''
                SELECT f.id, f.name as folder_name, f.created_at,
                       (SELECT COUNT(*) FROM files WHERE folder_id = f.id AND COALESCE(is_deleted, 0) = 0) as file_count,
                       (SELECT COALESCE(SUM(size), 0) FROM files WHERE folder_id = f.id AND COALESCE(is_deleted, 0) = 0) as total_size
                FROM folders f WHERE f.user_id = ?
                ORDER BY total_size DESC LIMIT 10
            ''', (session['user_id'],)).fetchall()
            folder_stats = [{'id': r['id'], 'folder_name': r['folder_name'], 'file_count': r['file_count'], 'total_size': r['total_size'], 'created_at': r['created_at']} for r in folder_stats_rows]

            untagged_size = conn.execute(
                'SELECT COALESCE(SUM(size), 0) as total FROM files WHERE user_id = ? AND id NOT IN (SELECT file_id FROM file_tags) AND COALESCE(is_deleted, 0) = 0',
                (session['user_id'],)).fetchone()['total']
            tagged_size = usage['total_size'] - untagged_size

            daily_rows = conn.execute('''
                SELECT DATE(created_at) as date, COALESCE(SUM(size), 0) as daily_size
                FROM files WHERE user_id = ? AND COALESCE(is_deleted, 0) = 0
                    AND created_at >= ?
                GROUP BY DATE(created_at) ORDER BY date
            ''', (session['user_id'], (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d'))).fetchall()

            daily_map = {r['date']: r['daily_size'] for r in daily_rows}

            base_size = conn.execute(
                'SELECT COALESCE(SUM(size), 0) as total FROM files WHERE user_id = ? AND COALESCE(is_deleted, 0) = 0 AND created_at < ?',
                (session['user_id'], (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d'))).fetchone()['total']

            trend_data = []
            cumulative = base_size
            for i in range(29, -1, -1):
                date = (datetime.now() - timedelta(days=i)).strftime('%Y-%m-%d')
                cumulative += daily_map.get(date, 0)
                trend_data.append({'date': date, 'size': cumulative})
        finally:
            conn.close()

        usage['type_stats'] = type_stats
        usage['trend_data'] = trend_data
        usage['large_files'] = large_files
        usage['folder_stats'] = folder_stats
        usage['tagged_size'] = tagged_size
        usage['untagged_size'] = untagged_size

        return _app.api_response(success=True, data=usage)
    except Exception as e:
        return _app.api_response(success=False, message=str(e))


@tags_categories_bp.route('/api/files/<file_id>/recommend-tags', methods=['GET'], endpoint='api_recommend_tags')
def api_recommend_tags(file_id):
    conn = _app.get_db()
    try:
        all_tags = conn.execute('SELECT id, name FROM tags ORDER BY name').fetchall()
        tags = [{'id': r['id'], 'name': r['name']} for r in all_tags]
        return _app.api_response(success=True, data={'tags': tags})
    finally:
        conn.close()


@tags_categories_bp.route('/api/tags/search', methods=['GET'], endpoint='api_tags_search')
def api_tags_search():
    query = request.args.get('q', '')
    conn = _app.get_db()
    try:
        if query:
            rows = conn.execute('SELECT id, name FROM tags WHERE name LIKE ?', (f'%{query}%',)).fetchall()
        else:
            rows = conn.execute('SELECT id, name FROM tags ORDER BY name LIMIT 20').fetchall()
        tags = [{'id': r['id'], 'name': r['name']} for r in rows]
        return _app.api_response(success=True, data={'tags': tags})
    finally:
        conn.close()


@tags_categories_bp.route('/api/tags/cloud', methods=['GET'], endpoint='api_tags_cloud')
def api_tags_cloud():
    conn = _app.get_db()
    try:
        rows = conn.execute('''SELECT t.id, t.name, COUNT(ft.file_id) as count
                               FROM tags t LEFT JOIN file_tags ft ON t.id = ft.tag_id
                               GROUP BY t.id ORDER BY count DESC LIMIT 50''').fetchall()
        tags = [{'id': r['id'], 'name': r['name'], 'count': r['count']} for r in rows]
        
        if tags:
            max_count = max(t['count'] for t in tags)
            min_count = min(t['count'] for t in tags)
            count_range = max_count - min_count if max_count > min_count else 1
            
            cloud = []
            for i, tag in enumerate(tags):
                normalized = (tag['count'] - min_count) / count_range if count_range > 0 else 0.5
                size = int(14 + normalized * 24)
                color_index = i % 10
                cloud.append({
                    'id': tag['id'],
                    'name': tag['name'],
                    'count': tag['count'],
                    'size': size,
                    'color_index': color_index
                })
        else:
            cloud = []
        
        return _app.api_response(success=True, data={'cloud': cloud, 'tags': tags})
    finally:
        conn.close()


@tags_categories_bp.route('/api/tags/overview', methods=['GET'], endpoint='api_tags_overview')
def api_tags_overview():
    conn = _app.get_db()
    try:
        total_tags = conn.execute('SELECT COUNT(*) FROM tags').fetchone()[0]
        total_categories = conn.execute('SELECT COUNT(*) FROM categories').fetchone()[0]
        tagged_files = conn.execute('SELECT COUNT(DISTINCT file_id) FROM file_tags').fetchone()[0]
        total_assignments = conn.execute('SELECT COUNT(*) FROM file_tags').fetchone()[0]

        total_files = conn.execute('SELECT COUNT(*) FROM files').fetchone()[0]
        untagged_files = total_files - tagged_files

        top_tags_rows = conn.execute(
            '''SELECT t.id, t.name, COUNT(ft.file_id) as count
               FROM tags t LEFT JOIN file_tags ft ON t.id = ft.tag_id
               GROUP BY t.id ORDER BY count DESC LIMIT 10''').fetchall()
        top_tags = [dict(r) for r in top_tags_rows]

        return _app.api_response(success=True, data={
            'total_tags': total_tags,
            'total_categories': total_categories,
            'tagged_files': tagged_files,
            'untagged_files': untagged_files,
            'total_assignments': total_assignments,
            'top_tags': top_tags
        })
    finally:
        conn.close()


@tags_categories_bp.route('/api/categories', methods=['POST'], endpoint='api_create_category')
def api_create_category():
    if 'user_id' not in session:
        return _app.api_response(success=False, message='请先登录')

    data = request.get_json()
    name = data.get('name')
    description = data.get('description', '')

    if not name:
        return _app.api_response(success=False, message='分类名称不能为空')

    conn = _app.get_db()
    try:
        conn.execute('INSERT INTO categories (name, description, user_id) VALUES (?, ?, ?)',
                   (name, description, session['user_id']))
        conn.commit()
        return _app.api_response(success=True, message='分类创建成功')
    finally:
        conn.close()


@tags_categories_bp.route('/api/tags', methods=['GET'], endpoint='api_get_tags')
def api_get_tags():
    conn = _app.get_db()
    try:
        rows = conn.execute('SELECT id, name, created_at FROM tags').fetchall()
        tags = [{'id': r['id'], 'name': r['name'], 'created_at': r['created_at']} for r in rows]
        return _app.api_response(success=True, data={'tags': tags})
    finally:
        conn.close()


@tags_categories_bp.route('/api/tags', methods=['POST'], endpoint='api_create_tag')
def api_create_tag():
    if 'user_id' not in session:
        return _app.api_response(success=False, message='请先登录')

    data = request.get_json()
    name = data.get('name')

    if not name:
        return _app.api_response(success=False, message='标签名称不能为空')

    conn = _app.get_db()
    try:
        conn.execute('INSERT INTO tags (name, user_id) VALUES (?, ?)', (name, session['user_id']))
        conn.commit()
        return _app.api_response(success=True, message='标签创建成功')
    finally:
        conn.close()


@tags_categories_bp.route('/api/files/<file_id>/categories', methods=['GET'], endpoint='api_get_file_categories')
def api_get_file_categories(file_id):
    conn = _app.get_db()
    try:
        rows = conn.execute('''SELECT c.id, c.name, c.description, c.created_at
                               FROM categories c JOIN file_categories fc ON c.id = fc.category_id
                               WHERE fc.file_id = ?''', (file_id,)).fetchall()
        categories = [{'id': r['id'], 'name': r['name'], 'description': r['description'], 'created_at': r['created_at']} for r in rows]
        return _app.api_response(success=True, data={'categories': categories})
    finally:
        conn.close()


@tags_categories_bp.route('/api/files/<file_id>/categories', methods=['POST'], endpoint='api_add_file_category')
def api_add_file_category(file_id):
    if 'user_id' not in session:
        return _app.api_response(success=False, message='请先登录')

    data = request.get_json()
    category_id = data.get('category_id')

    if not category_id:
        return _app.api_response(success=False, message='分类ID不能为空')

    conn = _app.get_db()
    try:
        existing = conn.execute('SELECT * FROM file_categories WHERE file_id = ? AND category_id = ?',
                               (file_id, category_id)).fetchone()
        if not existing:
            conn.execute('INSERT INTO file_categories (file_id, category_id) VALUES (?, ?)',
                        (file_id, category_id))
            conn.commit()
        return _app.api_response(success=True, message='分类添加成功')
    finally:
        conn.close()


@tags_categories_bp.route('/api/files/<file_id>/categories/<category_id>', methods=['DELETE'],
                           endpoint='api_remove_file_category')
def api_remove_file_category(file_id, category_id):
    if 'user_id' not in session:
        return _app.api_response(success=False, message='请先登录')

    conn = _app.get_db()
    try:
        conn.execute('DELETE FROM file_categories WHERE file_id = ? AND category_id = ?',
                    (file_id, category_id))
        conn.commit()
        return _app.api_response(success=True, message='分类移除成功')
    finally:
        conn.close()


@tags_categories_bp.route('/api/files/<file_id>/tags', methods=['GET'], endpoint='api_get_file_tags')
def api_get_file_tags(file_id):
    conn = _app.get_db()
    try:
        rows = conn.execute('''SELECT t.id, t.name, t.created_at
                               FROM tags t JOIN file_tags ft ON t.id = ft.tag_id
                               WHERE ft.file_id = ?''', (file_id,)).fetchall()
        tags = [{'id': r['id'], 'name': r['name'], 'created_at': r['created_at']} for r in rows]
        return _app.api_response(success=True, data={'tags': tags})
    finally:
        conn.close()


@tags_categories_bp.route('/api/files/<file_id>/tags', methods=['POST'], endpoint='api_add_file_tag')
def api_add_file_tag(file_id):
    if 'user_id' not in session:
        return _app.api_response(success=False, message='请先登录')

    data = request.get_json()
    tag_id = data.get('tag_id')

    if not tag_id:
        return _app.api_response(success=False, message='标签ID不能为空')

    conn = _app.get_db()
    try:
        existing = conn.execute('SELECT * FROM file_tags WHERE file_id = ? AND tag_id = ?',
                               (file_id, tag_id)).fetchone()
        if not existing:
            conn.execute('INSERT INTO file_tags (file_id, tag_id) VALUES (?, ?)', (file_id, tag_id))
            conn.commit()
        return _app.api_response(success=True, message='标签添加成功')
    finally:
        conn.close()


@tags_categories_bp.route('/api/files/<file_id>/tags/<tag_id>', methods=['DELETE'], endpoint='api_remove_file_tag')
def api_remove_file_tag(file_id, tag_id):
    if 'user_id' not in session:
        return _app.api_response(success=False, message='请先登录')

    conn = _app.get_db()
    try:
        conn.execute('DELETE FROM file_tags WHERE file_id = ? AND tag_id = ?', (file_id, tag_id))
        conn.commit()
        return _app.api_response(success=True, message='标签移除成功')
    finally:
        conn.close()


@tags_categories_bp.route('/api/tags/<tag_id>', methods=['PUT'], endpoint='api_update_tag')
def api_update_tag(tag_id):
    if 'user_id' not in session or session.get('role') != 'admin':
        return _app.api_response(success=False, message='权限不足', code=403)

    data = request.get_json() or {}
    new_name = data.get('name', '').strip()

    if not new_name:
        return _app.api_response(success=False, message='标签名称不能为空')

    conn = _app.get_db()
    try:
        conn.execute("UPDATE tags SET name = ? WHERE id = ?", (new_name, tag_id))
        conn.commit()
        return _app.api_response(success=True, message='标签更新成功')
    finally:
        conn.close()


@tags_categories_bp.route('/api/tags/<tag_id>', methods=['DELETE'], endpoint='api_delete_tag')
def api_delete_tag(tag_id):
    if 'user_id' not in session or session.get('role') != 'admin':
        return _app.api_response(success=False, message='权限不足', code=403)

    conn = _app.get_db()
    try:
        conn.execute("DELETE FROM file_tags WHERE tag_id = ?", (tag_id,))
        conn.execute("DELETE FROM tags WHERE id = ?", (tag_id,))
        conn.commit()
        return _app.api_response(success=True, message='标签已删除')
    finally:
        conn.close()


@tags_categories_bp.route('/api/categories/<cat_id>', methods=['PUT'], endpoint='api_update_category')
def api_update_category(cat_id):
    if 'user_id' not in session or session.get('role') != 'admin':
        return _app.api_response(success=False, message='权限不足', code=403)

    data = request.get_json() or {}
    new_name = data.get('name', '').strip()
    new_desc = data.get('description', '')

    if not new_name:
        return _app.api_response(success=False, message='分类名称不能为空')

    conn = _app.get_db()
    try:
        conn.execute("UPDATE categories SET name = ?, description = ? WHERE id = ?",
                    (new_name, new_desc, cat_id))
        conn.commit()
        return _app.api_response(success=True, message='分类更新成功')
    finally:
        conn.close()


@tags_categories_bp.route('/api/categories/<cat_id>', methods=['DELETE'], endpoint='api_delete_category')
def api_delete_category(cat_id):
    if 'user_id' not in session or session.get('role') != 'admin':
        return _app.api_response(success=False, message='权限不足', code=403)

    conn = _app.get_db()
    try:
        conn.execute("DELETE FROM file_categories WHERE category_id = ?", (cat_id,))
        conn.execute("DELETE FROM categories WHERE id = ?", (cat_id,))
        conn.commit()
        return _app.api_response(success=True, message='分类已删除')
    finally:
        conn.close()


@tags_categories_bp.route('/api/batch-add-tag', methods=['POST'], endpoint='api_batch_add_tag')
def api_batch_add_tag():
    if 'user_id' not in session:
        return _app.api_response(success=False, message='请先登录', code=401)

    data = request.get_json(silent=True) or {}
    file_ids = data.get('file_ids', [])
    tag_id = data.get('tag_id')

    if not file_ids or not tag_id:
        return _app.api_response(success=False, message='参数不完整')

    conn = _app.get_db()
    try:
        added_count = 0
        for fid in file_ids:
            existing = conn.execute('SELECT 1 FROM file_tags WHERE file_id = ? AND tag_id = ?',
                                   (fid, tag_id)).fetchone()
            if not existing:
                conn.execute('INSERT INTO file_tags (file_id, tag_id) VALUES (?, ?)', (fid, tag_id))
                added_count += 1

        conn.commit()

        _app.log_message(log_type='operation', log_level='INFO',
                   message=f'批量添加标签: {added_count} 个文件, 标签ID: {tag_id}',
                   user_id=session['user_id'], action='batch_add_tag', request=request)

        return _app.api_response(success=True, data={'added_count': added_count})
    finally:
        conn.close()


@tags_categories_bp.route('/api/files/by-tag/<tag_id>', methods=['GET'], endpoint='api_files_by_tag')
def api_files_by_tag(tag_id):
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    offset = (page - 1) * per_page

    conn = _app.get_db()
    try:
        tag_row = conn.execute("SELECT id, name FROM tags WHERE id = ?", (tag_id,)).fetchone()
        tag_info = {'id': tag_row['id'], 'name': tag_row['name']} if tag_row else None

        total = conn.execute(
            "SELECT COUNT(*) FROM file_tags ft JOIN files f ON ft.file_id = f.id WHERE ft.tag_id = ?",
            (tag_id,)).fetchone()[0]

        rows = conn.execute(
            """SELECT f.* FROM files f JOIN file_tags ft ON f.id = ft.file_id
               WHERE ft.tag_id = ? ORDER BY f.created_at DESC LIMIT ? OFFSET ?""",
            (tag_id, per_page, offset)).fetchall()

        files = []
        for row in rows:
            f = dict(row)
            f['like_count'] = _app.get_like_count(f['id'])
            f['favorite_count'] = _app.get_favorite_count(f['id'])
            file_tags = conn.execute(
                """SELECT t.id, t.name FROM tags t JOIN file_tags ft ON t.id = ft.tag_id
                   WHERE ft.file_id = ?""", (f['id'],)).fetchall()
            f['tags'] = [dict(t) for t in file_tags]
            files.append(f)

        return _app.api_response(success=True, data={
            'files': files,
            'tag_info': tag_info,
            'pagination': {
                'page': page,
                'per_page': per_page,
                'total': total,
                'total_pages': (total + per_page - 1) // per_page
            }
        })
    finally:
        conn.close()


@tags_categories_bp.route('/api/analytics/dashboard', methods=['GET'], endpoint='api_analytics_dashboard')
def api_analytics_dashboard():
    if 'user_id' not in session:
        return _app.api_response(success=False, message='请先登录', code=401)

    conn = _app.get_db()
    try:
        uid = session['user_id']
        from datetime import datetime, timedelta

        file_count = conn.execute('SELECT COUNT(*) FROM files WHERE user_id = ? AND is_deleted IS NULL', (uid,)).fetchone()[0]
        total_size = conn.execute('SELECT COALESCE(SUM(size),0) FROM files WHERE user_id = ? AND is_deleted IS NULL', (uid,)).fetchone()[0]
        total_likes = conn.execute('SELECT COUNT(*) FROM likes WHERE file_id IN (SELECT id FROM files WHERE user_id = ?)', (uid,)).fetchone()[0]
        total_favorites = conn.execute('SELECT COUNT(*) FROM favorites WHERE file_id IN (SELECT id FROM files WHERE user_id = ?)', (uid,)).fetchone()[0]
        total_views = conn.execute("SELECT COALESCE(SUM(view_count),0) FROM files WHERE user_id = ?", (uid,)).fetchone()[0]

        upload_trend = []
        for i in range(29, -1, -1):
            date = (datetime.now() - timedelta(days=i)).strftime('%Y-%m-%d')
            count = conn.execute(
                'SELECT COUNT(*) FROM files WHERE user_id = ? AND DATE(created_at) = ?',
                (uid, date)).fetchone()[0]
            size = conn.execute(
                'SELECT COALESCE(SUM(size),0) FROM files WHERE user_id = ? AND DATE(created_at) = ?',
                (uid, date)).fetchone()[0]
            upload_trend.append({'date': date, 'count': count, 'size': size})

        storage_trend = []
        for i in range(5, -1, -1):
            date = (datetime.now() - timedelta(days=i*30)).strftime('%Y-%m-%d')
            cumulative = conn.execute(
                'SELECT COALESCE(SUM(size),0) FROM files WHERE user_id = ? AND DATE(created_at) <= ?',
                (uid, date)).fetchone()[0]
            storage_trend.append({'date': date, 'size': cumulative})

        type_dist_rows = conn.execute('''
            SELECT
                CASE
                    WHEN filename LIKE '%.html' OR filename LIKE '%.htm' THEN 'HTML'
                    WHEN filename LIKE '%.css' THEN 'CSS'
                    WHEN filename LIKE '%.js' THEN 'JavaScript'
                    WHEN filename LIKE '%.py' THEN 'Python'
                    WHEN filename LIKE '%.json' THEN 'JSON'
                    WHEN filename LIKE '%.md' THEN 'Markdown'
                    WHEN filename LIKE '%.png' OR filename LIKE '%.jpg' OR filename LIKE '%.gif' OR filename LIKE '%.svg' OR filename LIKE '%.webp' THEN '图片'
                    WHEN filename LIKE '%.pdf' THEN 'PDF'
                    WHEN filename LIKE '%.mp4' OR filename LIKE '%.webm' OR filename LIKE '%.avi' THEN '视频'
                    WHEN filename LIKE '%.mp3' OR filename LIKE '%.wav' OR filename LIKE '%.ogg' THEN '音频'
                    WHEN filename LIKE '%.zip' OR filename LIKE '%.rar' OR filename LIKE '%.7z' THEN '压缩包'
                    ELSE '其他'
                END as file_type,
                COUNT(*) as count,
                COALESCE(SUM(size), 0) as total_size
            FROM files WHERE user_id = ? AND is_deleted IS NULL
            GROUP BY file_type ORDER BY count DESC
        ''', (uid,)).fetchall()
        type_distribution = [{'type': r['file_type'], 'count': r['count'], 'size': r['total_size']} for r in type_dist_rows]

        tag_cloud_rows = conn.execute('''
            SELECT t.name, COUNT(ft.file_id) as count
            FROM tags t JOIN file_tags ft ON t.id = ft.tag_id
            JOIN files f ON ft.file_id = f.id
            WHERE f.user_id = ? AND f.is_deleted IS NULL
            GROUP BY t.id ORDER BY count DESC LIMIT 20
        ''', (uid,)).fetchall()
        tag_cloud = [{'name': r['name'], 'count': r['count']} for r in tag_cloud_rows]

        hot_files_rows = conn.execute('''
            SELECT f.id, f.filename, f.size, f.created_at,
                   (SELECT COUNT(*) FROM likes WHERE file_id = f.id) as like_count,
                   (SELECT COUNT(*) FROM favorites WHERE file_id = f.id) as fav_count,
                   COALESCE(f.view_count, 0) as view_count
            FROM files f WHERE f.user_id = ? AND f.is_deleted IS NULL
            ORDER BY (COALESCE(f.view_count,0) + (SELECT COUNT(*) FROM likes WHERE file_id = f.id)*5 + (SELECT COUNT(*) FROM favorites WHERE file_id = f.id)*3) DESC
            LIMIT 10
        ''', (uid,)).fetchall()
        hot_files = [{'id': r['id'], 'filename': r['filename'], 'size': r['size'],
                      'like_count': r['like_count'], 'fav_count': r['fav_count'],
                      'view_count': r['view_count'], 'created_at': r['created_at']} for r in hot_files_rows]

        return _app.api_response(success=True, data={
            'overview': {
                'file_count': file_count,
                'total_size': total_size,
                'total_likes': total_likes,
                'total_favorites': total_favorites,
                'total_views': total_views
            },
            'upload_trend': upload_trend,
            'storage_trend': storage_trend,
            'type_distribution': type_distribution,
            'tag_cloud': tag_cloud,
            'hot_files': hot_files
        })
    except Exception as e:
        return _app.api_response(success=False, message=str(e))
    finally:
        conn.close()
