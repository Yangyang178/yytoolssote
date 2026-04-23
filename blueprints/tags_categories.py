from flask import Blueprint, request, jsonify, session
from app import (get_db, log_message, api_response)

tags_categories_bp = Blueprint('tags_categories', __name__)


@tags_categories_bp.route('/api/categories', methods=['GET'], endpoint='api_get_categories')
def api_get_categories():
    conn = get_db()
    try:
        rows = conn.execute('SELECT id, name, description, created_at FROM categories').fetchall()
        categories = [{'id': r['id'], 'name': r['name'], 'description': r['description'], 'created_at': r['created_at']} for r in rows]
        return api_response(success=True, data={'categories': categories})
    finally:
        conn.close()


@tags_categories_bp.route('/api/categories', methods=['POST'], endpoint='api_create_category')
def api_create_category():
    if 'user_id' not in session:
        return api_response(success=False, message='请先登录')

    data = request.get_json()
    name = data.get('name')
    description = data.get('description', '')

    if not name:
        return api_response(success=False, message='分类名称不能为空')

    conn = get_db()
    try:
        conn.execute('INSERT INTO categories (name, description, user_id) VALUES (?, ?, ?)',
                   (name, description, session['user_id']))
        conn.commit()
        return api_response(success=True, message='分类创建成功')
    finally:
        conn.close()


@tags_categories_bp.route('/api/tags', methods=['GET'], endpoint='api_get_tags')
def api_get_tags():
    conn = get_db()
    try:
        rows = conn.execute('SELECT id, name, created_at FROM tags').fetchall()
        tags = [{'id': r['id'], 'name': r['name'], 'created_at': r['created_at']} for r in rows]
        return api_response(success=True, data={'tags': tags})
    finally:
        conn.close()


@tags_categories_bp.route('/api/tags', methods=['POST'], endpoint='api_create_tag')
def api_create_tag():
    if 'user_id' not in session:
        return api_response(success=False, message='请先登录')

    data = request.get_json()
    name = data.get('name')

    if not name:
        return api_response(success=False, message='标签名称不能为空')

    conn = get_db()
    try:
        conn.execute('INSERT INTO tags (name, user_id) VALUES (?, ?)', (name, session['user_id']))
        conn.commit()
        return api_response(success=True, message='标签创建成功')
    finally:
        conn.close()


@tags_categories_bp.route('/api/files/<file_id>/categories', methods=['GET'], endpoint='api_get_file_categories')
def api_get_file_categories(file_id):
    conn = get_db()
    try:
        rows = conn.execute('''SELECT c.id, c.name, c.description, c.created_at
                               FROM categories c JOIN file_categories fc ON c.id = fc.category_id
                               WHERE fc.file_id = ?''', (file_id,)).fetchall()
        categories = [{'id': r['id'], 'name': r['name'], 'description': r['description'], 'created_at': r['created_at']} for r in rows]
        return api_response(success=True, data={'categories': categories})
    finally:
        conn.close()


@tags_categories_bp.route('/api/files/<file_id>/categories', methods=['POST'], endpoint='api_add_file_category')
def api_add_file_category(file_id):
    if 'user_id' not in session:
        return api_response(success=False, message='请先登录')

    data = request.get_json()
    category_id = data.get('category_id')

    if not category_id:
        return api_response(success=False, message='分类ID不能为空')

    conn = get_db()
    try:
        existing = conn.execute('SELECT * FROM file_categories WHERE file_id = ? AND category_id = ?',
                               (file_id, category_id)).fetchone()
        if not existing:
            conn.execute('INSERT INTO file_categories (file_id, category_id) VALUES (?, ?)',
                        (file_id, category_id))
            conn.commit()
        return api_response(success=True, message='分类添加成功')
    finally:
        conn.close()


@tags_categories_bp.route('/api/files/<file_id>/categories/<category_id>', methods=['DELETE'],
                           endpoint='api_remove_file_category')
def api_remove_file_category(file_id, category_id):
    if 'user_id' not in session:
        return api_response(success=False, message='请先登录')

    conn = get_db()
    try:
        conn.execute('DELETE FROM file_categories WHERE file_id = ? AND category_id = ?',
                    (file_id, category_id))
        conn.commit()
        return api_response(success=True, message='分类移除成功')
    finally:
        conn.close()


@tags_categories_bp.route('/api/files/<file_id>/tags', methods=['GET'], endpoint='api_get_file_tags')
def api_get_file_tags(file_id):
    conn = get_db()
    try:
        rows = conn.execute('''SELECT t.id, t.name, t.created_at
                               FROM tags t JOIN file_tags ft ON t.id = ft.tag_id
                               WHERE ft.file_id = ?''', (file_id,)).fetchall()
        tags = [{'id': r['id'], 'name': r['name'], 'created_at': r['created_at']} for r in rows]
        return api_response(success=True, data={'tags': tags})
    finally:
        conn.close()


@tags_categories_bp.route('/api/files/<file_id>/tags', methods=['POST'], endpoint='api_add_file_tag')
def api_add_file_tag(file_id):
    if 'user_id' not in session:
        return api_response(success=False, message='请先登录')

    data = request.get_json()
    tag_id = data.get('tag_id')

    if not tag_id:
        return api_response(success=False, message='标签ID不能为空')

    conn = get_db()
    try:
        existing = conn.execute('SELECT * FROM file_tags WHERE file_id = ? AND tag_id = ?',
                               (file_id, tag_id)).fetchone()
        if not existing:
            conn.execute('INSERT INTO file_tags (file_id, tag_id) VALUES (?, ?)', (file_id, tag_id))
            conn.commit()
        return api_response(success=True, message='标签添加成功')
    finally:
        conn.close()


@tags_categories_bp.route('/api/files/<file_id>/tags/<tag_id>', methods=['DELETE'], endpoint='api_remove_file_tag')
def api_remove_file_tag(file_id, tag_id):
    if 'user_id' not in session:
        return api_response(success=False, message='请先登录')

    conn = get_db()
    try:
        conn.execute('DELETE FROM file_tags WHERE file_id = ? AND tag_id = ?', (file_id, tag_id))
        conn.commit()
        return api_response(success=True, message='标签移除成功')
    finally:
        conn.close()


@tags_categories_bp.route('/api/tags/<tag_id>', methods=['PUT'], endpoint='api_update_tag')
def api_update_tag(tag_id):
    if 'user_id' not in session or session.get('role') != 'admin':
        return api_response(success=False, message='权限不足', code=403)

    data = request.get_json() or {}
    new_name = data.get('name', '').strip()

    if not new_name:
        return api_response(success=False, message='标签名称不能为空')

    conn = get_db()
    try:
        conn.execute("UPDATE tags SET name = ? WHERE id = ?", (new_name, tag_id))
        conn.commit()
        return api_response(success=True, message='标签更新成功')
    finally:
        conn.close()


@tags_categories_bp.route('/api/tags/<tag_id>', methods=['DELETE'], endpoint='api_delete_tag')
def api_delete_tag(tag_id):
    if 'user_id' not in session or session.get('role') != 'admin':
        return api_response(success=False, message='权限不足', code=403)

    conn = get_db()
    try:
        conn.execute("DELETE FROM file_tags WHERE tag_id = ?", (tag_id,))
        conn.execute("DELETE FROM tags WHERE id = ?", (tag_id,))
        conn.commit()
        return api_response(success=True, message='标签已删除')
    finally:
        conn.close()


@tags_categories_bp.route('/api/categories/<cat_id>', methods=['PUT'], endpoint='api_update_category')
def api_update_category(cat_id):
    if 'user_id' not in session or session.get('role') != 'admin':
        return api_response(success=False, message='权限不足', code=403)

    data = request.get_json() or {}
    new_name = data.get('name', '').strip()
    new_desc = data.get('description', '')

    if not new_name:
        return api_response(success=False, message='分类名称不能为空')

    conn = get_db()
    try:
        conn.execute("UPDATE categories SET name = ?, description = ? WHERE id = ?",
                    (new_name, new_desc, cat_id))
        conn.commit()
        return api_response(success=True, message='分类更新成功')
    finally:
        conn.close()


@tags_categories_bp.route('/api/categories/<cat_id>', methods=['DELETE'], endpoint='api_delete_category')
def api_delete_category(cat_id):
    if 'user_id' not in session or session.get('role') != 'admin':
        return api_response(success=False, message='权限不足', code=403)

    conn = get_db()
    try:
        conn.execute("DELETE FROM file_categories WHERE category_id = ?", (cat_id,))
        conn.execute("DELETE FROM categories WHERE id = ?", (cat_id,))
        conn.commit()
        return api_response(success=True, message='分类已删除')
    finally:
        conn.close()


@tags_categories_bp.route('/api/batch-add-tag', methods=['POST'], endpoint='api_batch_add_tag')
def api_batch_add_tag():
    if 'user_id' not in session:
        return api_response(success=False, message='请先登录', code=401)

    data = request.get_json(silent=True) or {}
    file_ids = data.get('file_ids', [])
    tag_id = data.get('tag_id')

    if not file_ids or not tag_id:
        return api_response(success=False, message='参数不完整')

    conn = get_db()
    try:
        added_count = 0
        for fid in file_ids:
            existing = conn.execute('SELECT 1 FROM file_tags WHERE file_id = ? AND tag_id = ?',
                                   (fid, tag_id)).fetchone()
            if not existing:
                conn.execute('INSERT INTO file_tags (file_id, tag_id) VALUES (?, ?)', (fid, tag_id))
                added_count += 1

        conn.commit()

        log_message(log_type='operation', log_level='INFO',
                   message=f'批量添加标签: {added_count} 个文件, 标签ID: {tag_id}',
                   user_id=session['user_id'], action='batch_add_tag', request=request)

        return api_response(success=True, data={'added_count': added_count})
    finally:
        conn.close()


@tags_categories_bp.route('/api/files/by-tag/<tag_id>', methods=['GET'], endpoint='api_files_by_tag')
def api_files_by_tag(tag_id):
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    offset = (page - 1) * per_page

    conn = get_db()
    try:
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
            f['like_count'] = get_like_count(f['id'])
            f['favorite_count'] = get_favorite_count(f['id'])
            files.append(f)

        return api_response(success=True, data={
            'files': files,
            'pagination': {
                'page': page,
                'per_page': per_page,
                'total': total,
                'total_pages': (total + per_page - 1) // per_page
            }
        })
    finally:
        conn.close()
