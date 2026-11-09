# AI大模型免费资源导航

**站点名：** AI大模型免费资源导航  
**主站（canonical）：** https://aiym168.github.io/  
**仓库：** https://github.com/aiym168/aiym168.github.io  

由 GitHub Actions 每 6 小时自动抓取、中文整理、构建并推送到 GitHub Pages（零人工）。

## 功能

- 自愈：源失败保留旧数据；翻译失败回退；页面永不空
- 深度百度 SEO：首页、分类页、条目详情页、日归档、JSON-LD、sitemap 索引/xml/txt、robots、404
- 可选百度普通收录推送（`BAIDU_PUSH_TOKEN`）

## 百度站长平台（需用户操作）

1. 打开 https://ziyuan.baidu.com 登录
2. 添加站点：`https://aiym168.github.io/`
3. 完成验证（HTML 标签或文件）。把验证码写入仓库：
   - Actions Secret `VERIFY_BAIDU`，或
   - `seo_config.json` 的 `baidu_site_verification`
4. 提交 sitemap：`https://aiym168.github.io/sitemap_index.xml`
5. 在站长平台创建「普通收录」推送 token，添加为仓库 Secret `BAIDU_PUSH_TOKEN`（可选）
6. **本仓库不会代为提交百度站长**——需你自己的百度账号完成以上步骤

## 本地

```bash
python3 fetch_auto.py
python3 build.py
```

## 双引擎自治（无需人工）

| 组件 | 位置 | 计划 |
|---|---|---|
| 引擎 A | `.github/workflows/update.yml` → `engine/pipeline.sh` | 每小时 :07（UTC）+ 每 2 小时 :37 备用 |
| 看门狗 | `.github/workflows/watchdog.yml` → `engine/gh_watch.py heal` | 每 30 分钟：停用即启用、失败/超时即补跑、故障写入 Issue |
| 引擎 B | Simular 云服务器 `~/engine/engine/engine_b.sh`（systemd timer + cron） | 每小时 :25（北京时间）巡检；线上数据 > 90 分钟未更新即接管发布，并反向修复引擎 A |
| 自愈 | `selfheal.py` → `data/sources_health.json` | 数据源连续失败 3 次自动暂停、指数退避自动重试；翻译服务按健康分轮换；产出骤降 (<60%) 自动回滚 |
| 自我进化 | `discover.py`（每日）/ `prune.py`（每日） | 自动发现新的免费大模型/AI 资源并学习新关键词；HEAD 检查下线死链 |
| 状态 | `/m/status.html`、`/api/status.json` | 每次运行刷新 |
