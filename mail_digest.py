#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Mail Digest - 邮件智能分类摘要
读取邮箱全部未读邮件 → DeepSeek AI 分类摘要 → 飞书机器人推送
"""

import imaplib
import email
import json
import os
import re
import sys
import html as html_mod
from email.header import decode_header
from email.utils import parsedate_to_datetime
from datetime import datetime

# 网易邮箱需要 ID 命令声明客户端身份
imaplib.Commands['ID'] = ('AUTH',)

import requests
from dotenv import load_dotenv


# ============================================================
#  Windows 终端编码修复
# ============================================================
if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass


# ============================================================
#  配置加载
# ============================================================

def load_config():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    env_path = os.path.join(script_dir, '.env')

    if not os.path.exists(env_path):
        die(f"找不到配置文件: {env_path}\n请复制 .env.example 为 .env 并填入配置")

    load_dotenv(env_path)

    cfg = {
        'deepseek_key':   os.getenv('DEEPSEEK_API_KEY'),
        'deepseek_model': os.getenv('DEEPSEEK_MODEL', 'deepseek-chat'),
        'feishu_webhook': os.getenv('FEISHU_WEBHOOK_URL', ''),
        'debug':          os.getenv('DEBUG', 'false').lower() == 'true',
        'accounts':       [],
    }

    if not cfg['deepseek_key']:
        die(".env 缺少 DEEPSEEK_API_KEY")

    account_list = os.getenv('EMAIL_ACCOUNTS', '')
    if account_list:
        names = [n.strip() for n in account_list.split(',') if n.strip()]
        for name in names:
            prefix = f'EMAIL_{name.upper()}_'
            addr     = os.getenv(f'{prefix}ADDRESS')
            server   = os.getenv(f'{prefix}IMAP_SERVER', 'imap.qq.com')
            port     = int(os.getenv(f'{prefix}IMAP_PORT', '993'))
            password = os.getenv(f'{prefix}PASSWORD') or os.getenv(f'{prefix}AUTH_CODE')

            if addr and password:
                cfg['accounts'].append({
                    'name':     name,
                    'address':  addr,
                    'password': password,
                    'server':   server,
                    'port':     port,
                })
                log('INFO', f'已配置账户: {name} ({addr})')
            else:
                log('WARN', f'账户 {name} 配置不完整，跳过')
    else:
        die('请在 .env 中设置 EMAIL_ACCOUNTS=qq 等')

    if not cfg['accounts']:
        die('没有配置任何邮箱账户')

    return cfg


# ============================================================
#  工具函数
# ============================================================

def die(msg):
    print(f"[FATAL] {msg}")
    sys.exit(1)


def log(level, msg):
    print(f"[{level}] {msg}")


def clean_text(text):
    if not text:
        return ""
    text = html_mod.unescape(str(text))
    text = re.sub(r'<[^>]+>', '', text)
    text = re.sub(r'\s+', ' ', text)
    return text.strip()[:800]


def decode_mime(text):
    if not text:
        return ""
    parts = decode_header(text)
    result = []
    for part, charset in parts:
        if isinstance(part, bytes):
            try:
                result.append(part.decode(charset or 'utf-8', errors='replace'))
            except Exception:
                result.append(part.decode('utf-8', errors='replace'))
        else:
            result.append(str(part))
    return ''.join(result)


def extract_body(msg):
    text_parts = []
    html_parts = []

    if msg.is_multipart():
        for part in msg.walk():
            if 'attachment' in str(part.get('Content-Disposition', '')).lower():
                continue
            ct = part.get_content_type()
            try:
                payload = part.get_payload(decode=True)
                if payload is None:
                    continue
                charset = part.get_content_charset() or 'utf-8'
                decoded = payload.decode(charset, errors='replace')
                if ct == 'text/plain':
                    text_parts.append(decoded)
                elif ct == 'text/html':
                    html_parts.append(decoded)
            except Exception:
                continue
    else:
        ct = msg.get_content_type()
        try:
            payload = msg.get_payload(decode=True)
            if payload:
                charset = msg.get_content_charset() or 'utf-8'
                decoded = payload.decode(charset, errors='replace')
                if ct == 'text/plain':
                    text_parts.append(decoded)
                elif ct == 'text/html':
                    html_parts.append(decoded)
        except Exception:
            pass

    raw = '\n'.join(text_parts) if text_parts else '\n'.join(html_parts)
    return clean_text(raw)


# ============================================================
#  IMAP 邮件读取
# ============================================================

def connect_imap(account):
    try:
        conn = imaplib.IMAP4_SSL(account['server'], account['port'])
        conn.login(account['address'], account['password'])
        # 网易邮箱需要身份声明
        if '163.com' in account['server'] or '126.com' in account['server'] or 'yeah.net' in account['server']:
            try:
                conn._simple_command('ID', '("name" "MailDigest" "version" "1.0")')
            except Exception:
                pass
        status, data = conn.select('INBOX')
        if status != 'OK':
            log('ERROR', f'{account["name"]} 无法选择收件箱: {data}')
            try:
                conn.logout()
            except Exception:
                pass
            return None
        return conn
    except imaplib.IMAP4.error as e:
        log('ERROR', f'{account["name"]} IMAP 登录失败: {e}')
        return None


def fetch_all_unread(conn, label):
    """获取全部未读邮件，逐封标记为已读"""
    status, msgs = conn.search(None, 'UNSEEN')
    if status != 'OK':
        log('ERROR', f'{label} 搜索未读邮件失败')
        return []

    ids = msgs[0].split()
    if not ids:
        return []

    log('INFO', f'{label}: 发现 {len(ids)} 封未读邮件，正在读取...')

    emails = []
    for eid in ids:
        try:
            status, data = conn.fetch(eid, '(RFC822)')
            if status != 'OK':
                continue

            raw = data[0][1]
            msg = email.message_from_bytes(raw)

            subject = decode_mime(msg.get('Subject', '(无主题)'))
            sender  = decode_mime(msg.get('From', '(未知)'))
            date_str = msg.get('Date', '')

            try:
                dt = parsedate_to_datetime(date_str)
                date_fmt = dt.strftime('%m-%d %H:%M')
            except Exception:
                date_fmt = date_str[:16] if date_str else '?'

            body = extract_body(msg)

            emails.append({
                'id':      f'{label}:{eid.decode()}',
                'subject': subject,
                'sender':  sender,
                'date':    date_fmt,
                'body':    body,
                'source':  label,
            })

            # 标记为已读，避免下次重复获取
            try:
                conn.store(eid, '+FLAGS', '\\Seen')
            except Exception:
                pass

        except Exception as e:
            log('WARN', f'{label} 解析邮件失败: {e}')

    return emails


# ============================================================
#  DeepSeek AI 分类 & 摘要
# ============================================================

SYSTEM_PROMPT = """你是一个专业的邮件分类助手。用户会给你一批未读邮件的 JSON 列表，请逐封分析并输出分类结果。

**分类规则**
- category（类型）：工作 / 个人 / 账单通知 / 推广营销 / 社交提醒 / 安全验证 / 其他
- urgency（紧急度）：紧急 / 普通 / 低优
- summary（摘要）：2-3 句中文，提炼核心信息。保留关键数字、日期、名称。

**输出格式**：严格返回以下 JSON，不要包含任何额外文字：
```json
{
  "emails": [
    {
      "id": "原始id",
      "category": "工作",
      "urgency": "紧急",
      "summary": "老板要求今天18:00前提交Q2报告，附件包含数据模板。"
    }
  ],
  "summary": "共 N 封未读邮件，其中紧急 X 封。涉及工作报告、账单提醒、社交通知等。"
}
```"""


def classify(cfg, emails):
    if not emails:
        return None

    items = [{
        'id':      e['id'],
        'subject': e['subject'],
        'sender':  e['sender'],
        'date':    e['date'],
        'body':    e['body'][:500],
    } for e in emails]

    user_msg = f"请分析以下 {len(items)} 封未读邮件：\n```json\n{json.dumps(items, ensure_ascii=False, indent=2)}\n```"

    headers = {
        'Authorization': f"Bearer {cfg['deepseek_key']}",
        'Content-Type':  'application/json',
    }

    payload = {
        'model':       cfg['deepseek_model'],
        'messages': [
            {'role': 'system', 'content': SYSTEM_PROMPT},
            {'role': 'user',   'content': user_msg},
        ],
        'temperature': 0.3,
        'max_tokens':  8192,
    }

    if cfg['debug']:
        log('DEBUG', f'发送 {len(items)} 封邮件到 DeepSeek...')

    try:
        r = requests.post(
            'https://api.deepseek.com/v1/chat/completions',
            headers=headers, json=payload, timeout=300,
        )
        r.raise_for_status()
        content = r.json()['choices'][0]['message']['content']

        m = re.search(r'```json\s*([\s\S]*?)\s*```', content)
        raw_json = m.group(1) if m else content
        result = json.loads(raw_json)

        # 合并原始邮件字段
        lookup = {e['id']: e for e in emails}
        for em in result.get('emails', []):
            orig = lookup.get(em.get('id'), {})
            if not em.get('subject'):
                em['subject'] = orig.get('subject', '')
            if not em.get('sender'):
                em['sender'] = orig.get('sender', '')
            em['source'] = orig.get('source', '')

        return result

    except json.JSONDecodeError as e:
        log('ERROR', f'DeepSeek 返回非 JSON: {e}')
        return fallback_classify(emails)
    except requests.RequestException as e:
        log('ERROR', f'DeepSeek API 请求失败: {e}')
        return fallback_classify(emails)


def fallback_classify(emails):
    patterns = [
        ('安全验证', ['验证码', '验证', '安全', '登录', '密码', '认证']),
        ('账单通知', ['账单', '还款', '扣款', '消费', '支付', '订单']),
        ('推广营销', ['优惠', '促销', '折扣', '会员', '订阅', '广告', 'unsubscribe']),
    ]
    result = []
    for e in emails:
        body = (e.get('subject', '') + ' ' + e.get('body', '')).lower()
        cat = '其他'
        for c, keywords in patterns:
            if any(kw in body for kw in keywords):
                cat = c
                break
        result.append({
            'id': e['id'], 'category': cat, 'urgency': '普通',
            'subject': e.get('subject', ''), 'sender': e.get('sender', ''),
            'date': e.get('date', ''), 'summary': e.get('subject', ''),
            'source': e.get('source', ''),
        })
    return {'emails': result, 'summary': f'共 {len(emails)} 封未读邮件（AI 不可用，使用规则分类）'}


# ============================================================
#  飞书推送
# ============================================================

URGENCY_DISPLAY = {'紧急': '!!', '普通': '  ', '低优': '--'}

def build_card(classified, total, source_summary):
    if not classified:
        return None

    emails = classified.get('emails', [])

    groups = {}
    for em in emails:
        groups.setdefault(em.get('category', '其他'), []).append(em)

    now = datetime.now().strftime('%Y-%m-%d %H:%M')
    urgent_count = sum(1 for em in emails if em.get('urgency') == '紧急')

    lines = [
        f"📬 **邮件日报** — {now}",
        "",
        f"📊 **{total}** 封 · 🔴紧急 **{urgent_count}** 封",
    ]
    if source_summary:
        lines.append(f"📨 {source_summary}")
    lines.append("")

    if classified.get('summary'):
        lines.append(f"💡 {classified['summary']}")
        lines.append("")

    icons = {
        '工作': '💼', '账单通知': '💰', '安全验证': '🔐',
        '社交提醒': '👥', '个人': '📌', '推广营销': '📢', '其他': '📋',
    }

    order = ['工作', '账单通知', '安全验证', '社交提醒', '个人', '推广营销', '其他']

    for cat in order:
        items = groups.get(cat)
        if not items:
            continue
        lines.append(f"**{icons.get(cat, '📋')} {cat}**（{len(items)}封）")
        lines.append("")
        for em in items:
            u = em.get('urgency', '普通')
            s = em.get('subject', '')
            summary = em.get('summary', '')
            lines.append(f"【{u}】**{s}**")
            lines.append(f"　└ {summary}")
            lines.append("")

    lines.append("---")
    lines.append("🤖 Mail Digest 自动生成")

    return {
        'msg_type': 'interactive',
        'card': {
            'header': {
                'title':    {'tag': 'plain_text', 'content': f'📬 邮件日报 · {now}'},
                'template': 'blue',
            },
            'elements': [{'tag': 'markdown', 'content': '\n'.join(lines)}],
        },
    }


def send_feishu(card, webhook):
    if not webhook:
        log('INFO', '未配置飞书 Webhook，跳过推送')
        return

    try:
        r = requests.post(webhook, json=card, timeout=30)
        data = r.json()
        if data.get('code') == 0:
            log('OK', '飞书推送成功')
        else:
            log('ERROR', f'飞书推送失败: {data}')
    except Exception as e:
        log('ERROR', f'飞书推送异常: {e}')


# ============================================================
#  主流程
# ============================================================

def main():
    print('=' * 50)
    print('  Mail Digest — 邮件智能分类摘要')
    print('=' * 50)

    cfg = load_config()

    all_emails = []
    source_counts = []

    for account in cfg['accounts']:
        label = account['name']
        log('INFO', f'连接 {label} ({account["address"]}) ...')
        conn = connect_imap(account)
        if conn is None:
            log('WARN', f'跳过 {label}')
            continue

        emails = fetch_all_unread(conn, label)
        conn.logout()

        log('OK', f'{label}: {len(emails)} 封未读 → 已全部标为已读')
        source_counts.append(f'{label}({len(emails)})')
        all_emails.extend(emails)

    if not all_emails:
        log('OK', '没有未读邮件')
        return

    total = len(all_emails)
    source_str = '，'.join(source_counts)
    log('OK', f'共计 {total} 封未读 ({source_str})')

    # AI 分类
    log('AI', 'DeepSeek 智能分析中...')
    classified = classify(cfg, all_emails)

    # 终端输出
    print('\n' + '=' * 50)
    print(f'  分类结果（{source_str}）')
    print('=' * 50)
    for em in classified.get('emails', []):
        urgency = em.get('urgency', '普通')
        tag = URGENCY_DISPLAY.get(urgency, '  ')
        print(f"  [{tag}] [{em.get('category','其他')}] {em.get('subject','')}")
        print(f"       {em.get('summary','')}")
    print(f"\n  {classified.get('summary','')}")
    print('=' * 50)

    # 飞书推送
    card = build_card(classified, total, source_str)
    send_feishu(card, cfg['feishu_webhook'])

    log('OK', '处理完毕')


if __name__ == '__main__':
    main()
