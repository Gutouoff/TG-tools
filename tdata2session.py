#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tdata -> Telethon session 转换工具
====================================
把 Telegram Desktop 便携版的 tdata 登录态转成 Telethon 的 .session 文件,
这样 tg_tool.py 就能操作这些"只有 tdata、没有 json"的账号了。

用法:
    python3.14 -X utf8 tdata2session.py <账号文件夹>
    python3.14 -X utf8 tdata2session.py --all <TG小号根目录>   # 批量转换所有无session的账号

转换结果: 在账号文件夹里生成 <文件夹名>.session + <文件夹名>.json(含 app_id/app_hash/user_id)
"""
import asyncio
import glob
import json
import os
import sys

try:
    from opentele.td import TDesktop
    from opentele.api import UseCurrentSession
except ImportError:
    print('!! 缺 opentele-ng,先装: python3.14 -m pip install opentele-ng')
    sys.exit(1)

try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

APP_ID = 2040
APP_HASH = 'b18441a1ff607e10a989891a5462e627'


def convert(account_dir):
    folder = os.path.basename(os.path.abspath(account_dir))
    tdata = os.path.join(account_dir, 'tdata')
    if not os.path.isdir(tdata):
        print(f'  [跳过] {folder}: 没有 tdata 目录')
        return False

    session_path = os.path.join(account_dir, folder + '.session')
    if os.path.isfile(session_path):
        print(f'  [跳过] {folder}: 已有 session')
        return False

    try:
        tdesk = TDesktop(tdata)
        if not tdesk.isLoaded():
            print(f'  [失败] {folder}: tdata 加载失败(可能损坏或空)')
            return False

        async def do():
            client = await tdesk.ToTelethon(session=session_path, flag=UseCurrentSession)
            await client.connect()
            try:
                if await client.is_user_authorized():
                    me = await client.get_me()
                    return me
                return None
            finally:
                await client.disconnect()

        me = asyncio.run(do())
        if me is None:
            print(f'  [失败] {folder}: 转换成功但登录态无效')
            return False

        # 写 json 配置(供 tg_tool 识别)
        cfg = {
            'phone': getattr(me, 'phone', '') or '',
            'session_file': folder + '.session',
            'app_id': APP_ID,
            'app_hash': APP_HASH,
            'device': 'PC',
            'sdk': 'Windows',
            'app_version': '6.6.4 x64',
            'user_id': str(me.id),
            'first_name': me.first_name or '',
            'last_name': me.last_name or '',
        }
        json.dump(cfg, open(os.path.join(account_dir, folder + '.json'), 'w', encoding='utf-8'),
                  ensure_ascii=False, indent=1)
        print(f'  [成功] {folder}: +{cfg["phone"]}  {me.first_name or ""} {me.last_name or ""}  uid={me.id}')
        return True
    except BaseException as e:
        print(f'  [失败] {folder}: {type(e).__name__}: {str(e)[:120]}')
        return False


def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    if '--all' in sys.argv:
        root = args[0] if args else os.getcwd()
        dirs = []
        for sub in sorted(os.listdir(root)):
            d = os.path.join(root, sub)
            if os.path.isdir(d) and os.path.isdir(os.path.join(d, 'tdata')):
                if not glob.glob(os.path.join(d, '*.session')):
                    dirs.append(d)
        print(f'找到 {len(dirs)} 个无 session 的 tdata 账号:')
        ok = 0
        for d in dirs:
            if convert(d):
                ok += 1
        print(f'\n完成: {ok}/{len(dirs)} 成功')
        return

    if not args:
        print('用法: python3.14 -X utf8 tdata2session.py <账号文件夹>')
        print('      python3.14 -X utf8 tdata2session.py --all <TG小号根目录>')
        sys.exit(1)
    convert(args[0])


if __name__ == '__main__':
    main()
