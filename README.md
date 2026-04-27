# 📚 微信读书笔记导出 Skill

OpenClaw Skill - 自动导出微信读书笔记到 Markdown/Obsidian

## 快速开始

### 1. 安装依赖

```bash
pip install requests beautifulsoup4
```

### 2. 配置 Cookie

1. 浏览器登录 https://weread.qq.com
2. F12 → Application → Cookies
3. 复制 `wr_vid` 和 `wr_skey`
4. 编辑 `config/weread.json`

### 3. 导出笔记

```bash
# 导出所有书籍
python scripts/weread_export.py --all

# 导出本周新增
python scripts/weread_export.py --this-week

# 导出特定书籍
python scripts/weread_export.py --book "书名"

# 查看统计
python scripts/weread_export.py --stats
```

### 4. OpenClaw 集成

在对话中使用：
```
导出微信读书笔记
```

## 文件结构

```
openclaw-weread-skill/
├── SKILL.md              # 技能说明
├── README.md             # 本文件
├── scripts/
│   └── weread_export.py  # 主脚本
├── config/
│   └── weread.json.template  # 配置模板
└── requirements.txt      # 依赖
```

## 自动化配置

### Cron 定时任务

添加到 `~/.openclaw/cron/jobs.json`:

```json
{
  "id": "weread-weekly-export",
  "name": "微信读书笔记每周导出",
  "schedule": {
    "kind": "cron",
    "expr": "0 9 * * 0",
    "tz": "Asia/Shanghai"
  },
  "payload": {
    "kind": "agentTurn",
    "message": "导出本周微信读书笔记并同步到 Obsidian"
  }
}
```

## 特别鸣谢

本项目在调试接口兼容性与近期增量导出能力时，参考了这些实现思路：

- [blessonism/weread2flomo](https://github.com/blessonism/weread2flomo) - 提供按 `createTime` 做最近 N 天过滤与增量同步的思路
- [Dawn11111/weread2notion-pro](https://github.com/Dawn11111/weread2notion-pro) - 提供新版微信读书接口组合与 Cookie 处理参考
- [MoonstoneF/WeRead2CraftCollection](https://github.com/MoonstoneF/WeRead2CraftCollection) - 提供 `/web/review/list` 等接口参数参考
- [openclaw/skills](https://github.com/openclaw/skills) - 提供 OpenClaw skill 组织方式与 WeRead 导出脚本参考

## License

MIT
