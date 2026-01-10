#!/usr/bin/env python3
# 检查app.py中的函数和SQL注入问题

with open('app.py', 'r', encoding='utf-8') as f:
    content = f.read()

# 检查文件行数
lines = content.split('\n')
print(f"文件行数: {len(lines)}")

# 查找所有函数定义
import re
functions = re.findall(r'def\s+\w+\s*\(', content)
print("\n所有函数:")
for func in functions:
    print(func)

# 查找可能存在SQL注入的查询
potential_vulnerabilities = []
for i, line in enumerate(lines):
    if 'execute(' in line and ('f"' in line or '"%s' in line or '.format(' in line):
        potential_vulnerabilities.append((i+1, line.strip()))

if potential_vulnerabilities:
    print("\n可能存在SQL注入的查询:")
    for line_num, line in potential_vulnerabilities:
        print(f"行 {line_num}: {line}")
else:
    print("\n未发现明显的SQL注入问题")

# 检查get_file_by_id函数
if 'def get_file_by_id' in content:
    print("\nget_file_by_id函数存在")
else:
    print("\nget_file_by_id函数不存在")
