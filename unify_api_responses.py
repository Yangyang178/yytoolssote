#!/usr/bin/env python3
"""
统一API响应格式脚本
将所有直接使用jsonify返回响应的API端点修改为使用api_response()函数
"""

import re

def main():
    # 读取app.py文件内容
    with open('app.py', 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 定义需要替换的模式
    patterns = [
        # 模式1: return jsonify({'success': True, ...})
        (r'return jsonify\(\{\s*(["\']success["\']):\s*True\s*(?:,\s*(["\']\w+["\']):\s*([^,]+))*(?:,\s*(["\']\w+["\']):\s*([^}]+))?\}\)(?:,\s*(\d+))?',
         r'return api_response(\n        success=True\2\5\6)'),
        
        # 模式2: return jsonify({'success': False, ...})
        (r'return jsonify\(\{\s*(["\']success["\']):\s*False\s*(?:,\s*(["\']\w+["\']):\s*([^,}]+))*(?:,\s*(["\']\w+["\']):\s*([^}]+))?\}\)(?:,\s*(\d+))?',
         r'return api_response(\n        success=False\2\5\6)'),
        
        # 模式3: 处理包含更多属性的响应
        (r'return jsonify\(\{\s*(["\']success["\']):\s*(True|False)\s*,\s*(["\']\w+["\']):\s*([^,}]+)\s*,\s*(["\']\w+["\']):\s*([^}]+)\}\)(?:,\s*(\d+))?',
         r'return api_response(\n        success=\2,\n        \3=\4,\n        \5=\6\7)'),
        
        # 模式4: 处理interactions端点的特殊响应
        (r'return jsonify\(\{\s*(["\']success["\']):\s*True\s*,\s*(["\']like_count["\']):\s*like_count\s*,\s*(["\']favorite_count["\']):\s*favorite_count\s*,\s*(["\']is_liked["\']):\s*is_liked\s*,\s*(["\']is_favorited["\']):\s*is_favorited\s*\}\)',
         r'return api_response(\n        success=True,\n        data=\{\n            "like_count": like_count,\n            "favorite_count": favorite_count,\n            "is_liked": is_liked,\n            "is_favorited": is_favorited\n        \})'),
        
        # 模式5: 处理categories GET端点的特殊响应
        (r'return jsonify\(\{\s*(["\']success["\']):\s*True\s*,\s*(["\']categories["\']):\s*\[\{\s*(["\']id["\']):\s*row\[(?:[\"\'])id(?:[\"\'])\]\s*,\s*(["\']name["\']):\s*row\[(?:[\"\'])name(?:[\"\'])\]\s*,\s*(["\']description["\']):\s*row\[(?:[\"\'])description(?:[\"\'])\]\s*,\s*(["\']created_at["\']):\s*row\[(?:[\"\'])created_at(?:[\"\'])\]\s*\}\s*for\s*row\s*in\s*rows\]\s*\}\)',
         r'return api_response(\n        success=True,\n        data=\{\n            "categories": [{\n                "id": row["id"],\n                "name": row["name"],\n                "description": row["description"],\n                "created_at": row["created_at"]\n            } for row in rows]\n        \})'),
        
        # 模式6: 处理tags GET端点的特殊响应
        (r'return jsonify\(\{\s*(["\']success["\']):\s*True\s*,\s*(["\']tags["\']):\s*\[\{\s*(["\']id["\']):\s*row\[(?:[\"\'])id(?:[\"\'])\]\s*,\s*(["\']name["\']):\s*row\[(?:[\"\'])name(?:[\"\'])\]\s*,\s*(["\']created_at["\']):\s*row\[(?:[\"\'])created_at(?:[\"\'])\]\s*\}\s*for\s*row\s*in\s*rows\]\s*\}\)',
         r'return api_response(\n        success=True,\n        data=\{\n            "tags": [{\n                "id": row["id"],\n                "name": row["name"],\n                "created_at": row["created_at"]\n            } for row in rows]\n        \})'),
        
        # 模式7: 处理文件版本相关端点
        (r'return jsonify\(\{\s*(["\']success["\']):\s*(True|False)\s*(?:,\s*(["\']\w+["\']):\s*([^}]+))?\}\)(?:,\s*(\d+))?',
         r'return api_response(\n        success=\2\3\4\5)')
    ]
    
    # 应用替换
    new_content = content
    for pattern, replacement in patterns:
        new_content = re.sub(pattern, replacement, new_content, flags=re.MULTILINE | re.DOTALL)
    
    # 手动处理一些特殊情况
    # 处理send-email-code端点
    new_content = re.sub(
        r'return jsonify\(\{\s*(["\']success["\']):\s*False\s*,\s*(["\']message["\']):\s*["\']请输入邮箱地址["\']\s*\}\),\s*400',
        r'return api_response(\n        success=False,\n        message="请输入邮箱地址",\n        code=400)',
        new_content
    )
    
    new_content = re.sub(
        r'return jsonify\(\{\s*(["\']success["\']):\s*False\s*,\s*(["\']message["\']):\s*["\']该邮箱已被使用["\']\s*\}\),\s*400',
        r'return api_response(\n        success=False,\n        message="该邮箱已被使用",\n        code=400)',
        new_content
    )
    
    new_content = re.sub(
        r'return jsonify\(\{\s*(["\']success["\']):\s*True\s*,\s*(["\']message["\']):\s*["\']验证码已发送["\']\s*\}\)',
        r'return api_response(\n        success=True,\n        message="验证码已发送")',
        new_content
    )
    
    new_content = re.sub(
        r'return jsonify\(\{\s*(["\']success["\']):\s*True\s*,\s*(["\']message["\']):\s*["\']验证码已发送\(调试模式：\' \+ message \+ \'\)\["\']\s*\}\)',
        r'return api_response(\n        success=True,\n        message="验证码已发送（调试模式：" + message + "）")',
        new_content
    )
    
    new_content = re.sub(
        r'return jsonify\(\{\s*(["\']success["\']):\s*False\s*,\s*(["\']message["\']):\s*f\["\']发送验证码失败：\' \s*\+ \s*str\(e\) \s*\+ \s*["\']\}\),\s*500',
        r'return api_response(\n        success=False,\n        message=f"发送验证码失败：{str(e)}",\n        code=500)',
        new_content
    )
    
    # 处理batch-delete端点
    new_content = re.sub(
        r'return jsonify\(\{\s*(["\']success["\']):\s*False\s*,\s*(["\']message["\']):\s*["\']请提供要删除的文件ID列表["\']\s*\}\),\s*400',
        r'return api_response(\n        success=False,\n        message="请提供要删除的文件ID列表",\n        code=400)',
        new_content
    )
    
    new_content = re.sub(
        r'return jsonify\(\{\s*(["\']success["\']):\s*True\s*,\s*(["\']message["\']):\s*f\["\']成功删除 \' \s*\+ \s*deleted_count \s*\+ \s*["\'] 个文件\["\']\s*,\s*(["\']deleted_count["\']):\s*deleted_count\s*\}\)',
        r'return api_response(\n        success=True,\n        message=f"成功删除 {deleted_count} 个文件",\n        data={"deleted_count": deleted_count})',
        new_content
    )
    
    # 处理batch-download端点
    new_content = re.sub(
        r'return jsonify\(\{\s*(["\']success["\']):\s*False\s*,\s*(["\']message["\']):\s*f\["\']批量下载失败: \' \s*\+ \s*str\(e\) \s*\+ \s*["\']\}\),\s*500',
        r'return api_response(\n        success=False,\n        message=f"批量下载失败: {str(e)}",\n        code=500)',
        new_content
    )
    
    new_content = re.sub(
        r'return jsonify\(\{\s*(["\']success["\']):\s*False\s*,\s*(["\']message["\']):\s*f\["\']请求处理失败: \' \s*\+ \s*str\(e\) \s*\+ \s*["\']\}\),\s*400',
        r'return api_response(\n        success=False,\n        message=f"请求处理失败: {str(e)}",\n        code=400)',
        new_content
    )
    
    new_content = re.sub(
        r'return jsonify\(\{\s*(["\']success["\']):\s*False\s*,\s*(["\']message["\']):\s*["\']请提供有效的文件ID列表["\']\s*\}\),\s*400',
        r'return api_response(\n        success=False,\n        message="请提供有效的文件ID列表",\n        code=400)',
        new_content
    )
    
    # 处理batch_delete_files函数
    new_content = re.sub(
        r'return jsonify\(\{\s*(["\']success["\']):\s*False\s*,\s*(["\']message["\']):\s*["\']请提供要删除的文件ID列表["\']\s*\}\),\s*400',
        r'return api_response(\n        success=False,\n        message="请提供要删除的文件ID列表",\n        code=400)',
        new_content
    )
    
    new_content = re.sub(
        r'return jsonify\(\{\s*(["\']success["\']):\s*True\s*,\s*(["\']message["\']):\s*f\["\']成功删除 \' \s*\+ \s*deleted_count \s*\+ \s*["\'] 个文件\["\']\s*\}\)',
        r'return api_response(\n        success=True,\n        message=f"成功删除 {deleted_count} 个文件")',
        new_content
    )
    
    # 处理/api/files端点
    new_content = re.sub(
        r'return jsonify\(\{\s*(["\']success["\']):\s*True\s*,\s*(["\']files["\']):\s*files\s*\}\)',
        r'return api_response(\n        success=True,\n        data={"files": files})',
        new_content
    )
    
    # 处理文件版本相关端点
    new_content = re.sub(
        r'return jsonify\(\{\s*(["\']success["\']):\s*True\s*,\s*(["\']versions["\']):\s*versions\s*\}\)',
        r'return api_response(\n        success=True,\n        data={"versions": versions})',
        new_content
    )
    
    new_content = re.sub(
        r'return jsonify\(\{\s*(["\']success["\']):\s*True\s*,\s*(["\']version["\']):\s*dict\(version\)\s*\}\)',
        r'return api_response(\n        success=True,\n        data={"version": dict(version)})',
        new_content
    )
    
    new_content = re.sub(
        r'return jsonify\(\{\s*(["\']success["\']):\s*False\s*,\s*(["\']message["\']):\s*["\']版本不存在["\']\s*\}\),\s*404',
        r'return api_response(\n        success=False,\n        message="版本不存在",\n        code=404)',
        new_content
    )
    
    new_content = re.sub(
        r'return jsonify\(\{\s*(["\']success["\']):\s*False\s*,\s*(["\']message["\']):\s*["\']版本不存在或无权限操作["\']\s*\}\),\s*404',
        r'return api_response(\n        success=False,\n        message="版本不存在或无权限操作",\n        code=404)',
        new_content
    )
    
    new_content = re.sub(
        r'return jsonify\(\{\s*(["\']success["\']):\s*True\s*,\s*(["\']message["\']):\s*["\']文件已恢复到指定版本["\']\s*\}\)',
        r'return api_response(\n        success=True,\n        message="文件已恢复到指定版本")',
        new_content
    )
    
    new_content = re.sub(
        r'return jsonify\(\{\s*(["\']success["\']):\s*True\s*,\s*(["\']message["\']):\s*["\']文件版本已删除["\']\s*\}\)',
        r'return api_response(\n        success=True,\n        message="文件版本已删除")',
        new_content
    )
    
    # 处理分类和标签相关端点
    new_content = re.sub(
        r'return jsonify\(\{\s*(["\']success["\']):\s*True\s*,\s*(["\']categories["\']):\s*\[(?:[^\]]+)\]\s*\}\)',
        r'return api_response(\n        success=True,\n        data={"categories": \1})',
        new_content
    )
    
    new_content = re.sub(
        r'return jsonify\(\{\s*(["\']success["\']):\s*False\s*,\s*(["\']message["\']):\s*["\']分类名称不能为空["\']\s*\}\),\s*400',
        r'return api_response(\n        success=False,\n        message="分类名称不能为空",\n        code=400)',
        new_content
    )
    
    new_content = re.sub(
        r'return jsonify\(\{\s*(["\']success["\']):\s*True\s*,\s*(["\']message["\']):\s*["\']分类创建成功["\']\s*\}\)',
        r'return api_response(\n        success=True,\n        message="分类创建成功")',
        new_content
    )
    
    new_content = re.sub(
        r'return jsonify\(\{\s*(["\']success["\']):\s*False\s*,\s*(["\']message["\']):\s*["\']分类名称已存在["\']\s*\}\),\s*400',
        r'return api_response(\n        success=False,\n        message="分类名称已存在",\n        code=400)',
        new_content
    )
    
    new_content = re.sub(
        r'return jsonify\(\{\s*(["\']success["\']):\s*True\s*,\s*(["\']message["\']):\s*["\']分类更新成功["\']\s*\}\)',
        r'return api_response(\n        success=True,\n        message="分类更新成功")',
        new_content
    )
    
    new_content = re.sub(
        r'return jsonify\(\{\s*(["\']success["\']):\s*False\s*,\s*(["\']message["\']):\s*["\']分类不存在或无权限["\']\s*\}\),\s*404',
        r'return api_response(\n        success=False,\n        message="分类不存在或无权限",\n        code=404)',
        new_content
    )
    
    new_content = re.sub(
        r'return jsonify\(\{\s*(["\']success["\']):\s*True\s*,\s*(["\']message["\']):\s*["\']分类删除成功["\']\s*\}\)',
        r'return api_response(\n        success=True,\n        message="分类删除成功")',
        new_content
    )
    
    new_content = re.sub(
        r'return jsonify\(\{\s*(["\']success["\']):\s*False\s*,\s*(["\']message["\']):\s*["\']分类ID不能为空["\']\s*\}\),\s*400',
        r'return api_response(\n        success=False,\n        message="分类ID不能为空",\n        code=400)',
        new_content
    )
    
    new_content = re.sub(
        r'return jsonify\(\{\s*(["\']success["\']):\s*True\s*,\s*(["\']message["\']):\s*["\']分类添加成功["\']\s*\}\)',
        r'return api_response(\n        success=True,\n        message="分类添加成功")',
        new_content
    )
    
    new_content = re.sub(
        r'return jsonify\(\{\s*(["\']success["\']):\s*True\s*,\s*(["\']message["\']):\s*["\']分类删除成功["\']\s*\}\)',
        r'return api_response(\n        success=True,\n        message="分类删除成功")',
        new_content
    )
    
    # 处理标签相关端点
    new_content = re.sub(
        r'return jsonify\(\{\s*(["\']success["\']):\s*True\s*,\s*(["\']tags["\']):\s*\[(?:[^\]]+)\]\s*\}\)',
        r'return api_response(\n        success=True,\n        data={"tags": \1})',
        new_content
    )
    
    new_content = re.sub(
        r'return jsonify\(\{\s*(["\']success["\']):\s*False\s*,\s*(["\']message["\']):\s*["\']标签名称不能为空["\']\s*\}\),\s*400',
        r'return api_response(\n        success=False,\n        message="标签名称不能为空",\n        code=400)',
        new_content
    )
    
    new_content = re.sub(
        r'return jsonify\(\{\s*(["\']success["\']):\s*True\s*,\s*(["\']message["\']):\s*["\']标签创建成功["\']\s*\}\)',
        r'return api_response(\n        success=True,\n        message="标签创建成功")',
        new_content
    )
    
    new_content = re.sub(
        r'return jsonify\(\{\s*(["\']success["\']):\s*False\s*,\s*(["\']message["\']):\s*["\']标签名称已存在["\']\s*\}\),\s*400',
        r'return api_response(\n        success=False,\n        message="标签名称已存在",\n        code=400)',
        new_content
    )
    
    new_content = re.sub(
        r'return jsonify\(\{\s*(["\']success["\']):\s*True\s*,\s*(["\']message["\']):\s*["\']标签更新成功["\']\s*\}\)',
        r'return api_response(\n        success=True,\n        message="标签更新成功")',
        new_content
    )
    
    new_content = re.sub(
        r'return jsonify\(\{\s*(["\']success["\']):\s*False\s*,\s*(["\']message["\']):\s*["\']标签不存在或无权限["\']\s*\}\),\s*404',
        r'return api_response(\n        success=False,\n        message="标签不存在或无权限",\n        code=404)',
        new_content
    )
    
    new_content = re.sub(
        r'return jsonify\(\{\s*(["\']success["\']):\s*True\s*,\s*(["\']message["\']):\s*["\']标签删除成功["\']\s*\}\)',
        r'return api_response(\n        success=True,\n        message="标签删除成功")',
        new_content
    )
    
    new_content = re.sub(
        r'return jsonify\(\{\s*(["\']success["\']):\s*False\s*,\s*(["\']message["\']):\s*["\']标签ID不能为空["\']\s*\}\),\s*400',
        r'return api_response(\n        success=False,\n        message="标签ID不能为空",\n        code=400)',
        new_content
    )
    
    new_content = re.sub(
        r'return jsonify\(\{\s*(["\']success["\']):\s*True\s*,\s*(["\']message["\']):\s*["\']标签添加成功["\']\s*\}\)',
        r'return api_response(\n        success=True,\n        message="标签添加成功")',
        new_content
    )
    
    new_content = re.sub(
        r'return jsonify\(\{\s*(["\']success["\']):\s*True\s*,\s*(["\']message["\']):\s*["\']标签删除成功["\']\s*\}\)',
        r'return api_response(\n        success=True,\n        message="标签删除成功")',
        new_content
    )
    
    # 处理点赞和收藏端点
    new_content = re.sub(
        r'return jsonify\(\{\s*(["\']success["\']):\s*True\s*,\s*(["\']liked["\']):\s*liked\s*,\s*(["\']count["\']):\s*count\s*\}\)',
        r'return api_response(\n        success=True,\n        data={"liked": liked, "count": count})',
        new_content
    )
    
    new_content = re.sub(
        r'return jsonify\(\{\s*(["\']success["\']):\s*True\s*,\s*(["\']favorited["\']):\s*favorited\s*,\s*(["\']count["\']):\s*count\s*\}\)',
        r'return api_response(\n        success=True,\n        data={"favorited": favorited, "count": count})',
        new_content
    )
    
    new_content = re.sub(
        r'return jsonify\(\{\s*(["\']success["\']):\s*False\s*,\s*(["\']error["\']):\s*str\(e\)\s*\}\),\s*500',
        r'return api_response(\n        success=False,\n        error={"message": str(e)},\n        code=500)',
        new_content
    )
    
    # 处理dk_status端点
    new_content = re.sub(
        r'return api_response\(\n        success=True,\n        message="DKFILE状态检查成功",\n        data=\{"ok": True, "info": info\}\)',
        r'return api_response(\n        success=True,\n        message="DKFILE状态检查成功",\n        data={"ok": True, "info": info})',
        new_content
    )
    
    new_content = re.sub(
        r'return api_response\(\n        success=False,\n        message="DKFILE状态检查失败",\n        error=\{"message": str\(e\)}\),\n        code=502',
        r'return api_response(\n        success=False,\n        message="DKFILE状态检查失败",\n        error={"message": str(e)},\n        code=502)',
        new_content
    )
    
    # 保存修改后的内容
    with open('app.py', 'w', encoding='utf-8') as f:
        f.write(new_content)
    
    print("API响应格式统一完成！")

if __name__ == '__main__':
    main()
