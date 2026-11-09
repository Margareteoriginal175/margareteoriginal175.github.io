# AI大模型免费资源导航

**站点名：** AI大模型免费资源导航  
**主站（canonical）：** https://aiym168.github.io/  
**仓库：** https://github.com/aiym168/aiym168.github.io  

由 GitHub Actions 每 6 小时自动抓取、中文整理、构建并推送到 GitHub Pages（零人工）。

## 功能

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
