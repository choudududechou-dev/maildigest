# Mail Digest - 多邮箱智能日报

自动读取多个邮箱的未读邮件，通过 DeepSeek AI 智能分类并生成摘要，推送到飞书群。

## 功能

- 📬 支持 QQ邮箱 / 163 / 126 / 新浪 / Outlook（转发）等所有主流邮箱
- 🤖 DeepSeek AI 自动分类（工作/个人/账单/营销/安全等7类）+ 紧急度标注
- 📊 飞书机器人卡片消息推送日报
- 🔄 读取后自动标为已读，不重复处理
- ⏰ 支持 Windows 定时任务 + 手动触发

## 快速开始

### 1. 安装 Python

电脑需要 Python 3.9+（如未安装请去 https://python.org 下载）

### 2. 安装依赖

双击运行以下命令（或打开 CMD 粘贴）：

```
pip install requests python-dotenv
```

### 3. 准备三个东西

| 需要 | 怎么获取 |
|------|---------|
| **邮箱授权码** | 登录网页版邮箱 → 设置 → 账户 → 开启 IMAP → 生成授权码（16位） |
| **DeepSeek API Key** | 注册 https://platform.deepseek.com → API Keys → 创建 |
| **飞书 Webhook** | 飞书群 → 设置 → 群机器人 → 自定义机器人 → 复制地址 |

### 4. 配置

复制 `.env.example` 为 `.env`，填写你的信息：

```
EMAIL_ACCOUNTS=qq,netease    ← 邮箱标识，多个逗号分隔

EMAIL_QQ_ADDRESS=你的QQ号@qq.com
EMAIL_QQ_AUTH_CODE=你的授权码
EMAIL_QQ_IMAP_SERVER=imap.qq.com
EMAIL_QQ_IMAP_PORT=993

EMAIL_NETEASE_ADDRESS=你的邮箱@163.com
EMAIL_NETEASE_AUTH_CODE=你的授权码
EMAIL_NETEASE_IMAP_SERVER=imap.163.com
EMAIL_NETEASE_IMAP_PORT=993

DEEPSEEK_API_KEY=sk-你的key
FEISHU_WEBHOOK_URL=https://open.feishu.cn/open-apis/bot/v2/hook/xxx
```

> 支持任意数量邮箱，只需在 `EMAIL_ACCOUNTS` 中添加标识，然后按格式添加对应的配置项。邮件服务器地址见附表。

### 5. 运行

- **手动**：双击 `readmail.bat`
- **自动**：Windows 搜索"任务计划程序" → 创建基本任务 → 每天 9:00 执行 `python mail_digest.py`

## 邮件服务器地址

| 邮箱 | IMAP 服务器 | 端口 |
|------|-----------|------|
| QQ邮箱 | imap.qq.com | 993 |
| 163邮箱 | imap.163.com | 993 |
| 126邮箱 | imap.126.com | 993 |
| 新浪邮箱 | imap.sina.com | 993 |
| 搜狐邮箱 | imap.sohu.com | 993 |
| Outlook | 不支持直接 IMAP，请网页设置转发 |
| Gmail | imap.gmail.com | 993（需应用密码） |

## 分类说明

| 类型 | 说明 |
|------|------|
| 💼 工作 | 工作相关邮件 |
| 💰 账单通知 | 消费、订阅、扣款 |
| 🔐 安全验证 | 验证码、登录通知 |
| 👥 社交提醒 | 好友、社交平台通知 |
| 📌 个人 | 个人邮件 |
| 📢 推广营销 | 广告、促销 |
| 📋 其他 | 未分类邮件 |

紧急度：**紧急** / **普通** / **低优**
