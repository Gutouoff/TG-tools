import time
import json
import urllib.request

import server

server.ROOT = r'D:\Desktop\TG小号'  # 模拟 frozen 的账号根目录
port, token = server.start_server()
time.sleep(3)

# 带 token 请求 /api/accounts
req = urllib.request.Request(f'http://127.0.0.1:{port}/api/accounts',
                             headers={'X-TG-Token': token})
try:
    r = urllib.request.urlopen(req, timeout=15)
    data = json.loads(r.read().decode('utf-8'))
    print('账号数:', len(data) if isinstance(data, list) else '非列表!', type(data).__name__)
    if isinstance(data, list) and data:
        print('第一个:', data[0].get('name'), data[0].get('username'), data[0].get('avatar'))
except Exception as e:
    print('请求失败:', e)

# 请求 index.html(带 token query)
r2 = urllib.request.urlopen(f'http://127.0.0.1:{port}/?token={token}', timeout=10)
html = r2.read().decode('utf-8')
print('index 含 script:', '/assets/' in html)
print('DONE')
