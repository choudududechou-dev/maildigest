---
name: maildigest
description: >
  多邮箱智能日报。自动读取多个邮箱未读邮件，DeepSeek AI 分类摘要，飞书卡片推送。
  Use when 用户提到邮箱日报、邮件摘要、邮件分类、邮件 Digest、未读邮件、
  IMAP 读邮件、飞书邮件推送、DeepSeek 邮件、多邮箱管理。
---

# MailDigest — 多邮箱智能日报

你是安装向导，帮用户自动读取邮件、AI 分类、推送到飞书。
**交互式引导**：检查环境 → 收集凭证 → 写入配置 → 安装依赖 → 首跑验证 → 定时任务。

## 工作流

### 第 1 步：检查环境

```bash
python --version
```

Python < 3.9 → 提示升级。OK → 下一步。

### 第 2 步：收集邮箱信息

问用户：

> 你想接入哪些邮箱？请列出邮箱类型和地址。
> 例如：QQ `123456@qq.com`，163 `abc@163.com`
>
> | 支持的邮箱 | IMAP 服务器 | 端口 |
> |-----------|-----------|------|
> | QQ邮箱 | imap.qq.com | 993 |
> | 163 | imap.163.com | 993 |
> | 126 | imap.126.com | 993 |
> | 新浪 | imap.sina.com | 993 |
> | 搜狐 | imap.sohu.com | 993 |
> | Gmail | imap.gmail.com | 993（需应用密码） |
> | Outlook | 不支持直接 IMAP，需网页设置转发 |

等用户回复后，再依次问每个邮箱的**授权码**（不是登录密码）：
> 去网页版邮箱 → 设置 → 账户 → 开启 IMAP/SMTP → 生成授权码（16位）。
> `123456@qq.com` 的授权码是什么？

### 第 3 步：收集 DeepSeek API Key

> 去 https://platform.deepseek.com 注册 → API Keys → 创建新 Key。告诉我你的 API Key。

### 第 4 步：收集飞书 Webhook（可选）

> 想让日报推送到飞书群吗？（输入 webhook 地址或回车跳过）
>
> 获取方式：飞书群 → 设置 → 群机器人 → 自定义机器人 → 复制 Webhook 地址。

### 第 5 步：写入 .env

根据用户提供的信息生成配置。给每个邮箱分配一个简短标识（如 qq、163、gmail），写入：

```
EMAIL_ACCOUNTS=<标识1>,<标识2>

EMAIL_<标识>_ADDRESS=<邮箱地址>
EMAIL_<标识>_AUTH_CODE=<授权码>
EMAIL_<标识>_IMAP_SERVER=<IMAP服务器>
EMAIL_<标识>_IMAP_PORT=993

DEEPSEEK_API_KEY=<DeepSeek Key>
FEISHU_WEBHOOK_URL=<Webhook 地址或留空>
```

Windows 用 PowerShell：
```powershell
@"内容"@ | Out-File -FilePath .env -Encoding utf8
```
macOS/Linux 用：
```bash
cat > .env << 'EOF'
内容
EOF
```

写入后确认 `ls -la .env`。

### 第 6 步：安装依赖

```bash
pip install requests python-dotenv
```

### 第 7 步：首跑验证

```bash
python mail_digest.py
```

查看输出，确认：
- 邮箱连接成功
- 邮件读取正常
- DeepSeek 分类正常
- 飞书推送成功（如配置了 webhook）

### 第 8 步：定时任务（可选）

问用户是否要设置每天自动运行：

> 要我帮你设置 Windows 定时任务吗？每天自动跑一次。
> 需要的话，告诉我你想几点跑（如 9:00）。

用户确认后，用 PowerShell 创建计划任务：
```powershell
$action = New-ScheduledTaskAction -Execute "python" -Argument "mail_digest.py" -WorkingDirectory "<项目路径>"
$trigger = New-ScheduledTaskTrigger -Daily -At "09:00"
Register-ScheduledTask -TaskName "MailDigest日报" -Action $action -Trigger $trigger -Description "每日邮件摘要推送"
```

## 排错

| 现象 | 排查 |
|------|------|
| IMAP 登录失败 | ① 确认授权码不是登录密码 ② 确认邮箱已开启 IMAP ③ 网易邮箱可能需要客户端授权密码 |
| DeepSeek API 报错 | ① 检查 Key 是否有效 ② 确认账户有余额 |
| 飞书收不到消息 | ① 检查 Webhook 地址完整 ② 确认机器人未被移除 |
| Gmail 连不上 | 需开启两步验证后生成"应用专用密码" |
| 中文乱码 | Windows 终端编码问题，不影响飞书推送 |

## 分类说明

AI 将邮件分为 7 类：💼工作 / 💰账单通知 / 🔐安全验证 / 👥社交提醒 / 📌个人 / 📢推广营销 / 📋其他
紧急度：**紧急** / **普通** / **低优**
