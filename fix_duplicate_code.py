#!/usr/bin/env python3
# 修复app.py中的重复代码和SQL注入问题

with open('app.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# 删除从第651行开始的重复代码块（行号从1开始）
new_lines = lines[:650]  # 保留前650行

# 修复SQL注入问题：将file_ids_str替换为参数化查询
fixed_lines = []
in_get_all_files = False
for line in new_lines:
    fixed_lines.append(line)
    
    # 检测进入get_all_files函数
    if 'def get_all_files' in line:
        in_get_all_files = True
    
    # 检测离开get_all_files函数
    if in_get_all_files and line.strip() == '    finally:' and 'conn.close()' in new_lines[new_lines.index(line)+1]:
        in_get_all_files = False
    
    # 在get_all_files函数内修复SQL注入问题
    if in_get_all_files:
        if 'file_ids_str =' in line:
            # 跳过原有的file_ids_str赋值
            continue
        if 'likes_query =' in line or 'favorites_query =' in line or 'categories_query =' in line or 'tags_query =' in line:
            # 替换为参数化查询
            prev_line = fixed_lines[-2]
            if 'file_ids =' in prev_line:
                # 添加参数化查询的占位符
                fixed_lines.append('        placeholders = ",".join(["?"] * len(file_ids))\n')
            # 替换字符串插值为参数化查询
            if 'likes_query =' in line:
                fixed_lines[-1] = '        likes_query = f"SELECT file_id, COUNT(*) as count FROM likes WHERE file_id IN ({placeholders}) GROUP BY file_id"\n'
            elif 'favorites_query =' in line:
                fixed_lines[-1] = '        favorites_query = f"SELECT file_id, COUNT(*) as count FROM favorites WHERE file_id IN ({placeholders}) GROUP BY file_id"\n'
            elif 'categories_query =' in line:
                # 处理多行字符串
                fixed_lines[-1] = '        categories_query = f"""\n'
                # 读取后续行直到结束
                i = new_lines.index(line) + 1
                while i < len(new_lines) and '"""' not in new_lines[i]:
                    if '{file_ids_str}' in new_lines[i]:
                        fixed_lines.append(new_lines[i].replace('{file_ids_str}', '{placeholders}'))
                    else:
                        fixed_lines.append(new_lines[i])
                    i += 1
                # 添加结束引号
                fixed_lines.append(new_lines[i])
            elif 'tags_query =' in line:
                # 处理多行字符串
                fixed_lines[-1] = '        tags_query = f"""\n'
                # 读取后续行直到结束
                i = new_lines.index(line) + 1
                while i < len(new_lines) and '"""' not in new_lines[i]:
                    if '{file_ids_str}' in new_lines[i]:
                        fixed_lines.append(new_lines[i].replace('{file_ids_str}', '{placeholders}'))
                    else:
                        fixed_lines.append(new_lines[i])
                    i += 1
                # 添加结束引号
                fixed_lines.append(new_lines[i])

# 写入修复后的文件
with open('app.py', 'w', encoding='utf-8') as f:
    f.writelines(fixed_lines)

print("修复完成！")
