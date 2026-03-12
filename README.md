# 上海电气项目知识库

供上海电气日本公司小团队内部分享 Word / Excel 文档的知识库网站。

## 功能

- 账号密码登录
- 上传 Word (.docx) / Excel (.xlsx, .xls) 文档
- 在线预览文档内容（Word 渲染为富文本，Excel 渲染为表格）
- 文档搜索
- 下载原始文件
- 管理员用户管理

## 本地运行

```bash
pip install -r requirements.txt
python app.py
```

浏览器打开 http://localhost:5000 ，默认管理员账号：admin / admin123

## Railway 部署

1. 将代码推送到 GitHub 仓库
2. 在 [Railway](https://railway.app) 创建新项目，关联 GitHub 仓库
3. 添加 Persistent Volume，挂载路径设为 `/app/uploads`
4. 设置环境变量：
   - `SECRET_KEY` — 随机字符串（用于会话加密）
   - `ADMIN_PASSWORD` — 管理员初始密码
   - `DATA_DIR` — 设为 `/app/uploads`（与 Volume 挂载路径一致）
5. 部署完成后通过 Railway 分配的域名访问

## 技术栈

- Python Flask
- SQLite
- Tailwind CSS
- mammoth（Word 转 HTML）
- openpyxl（Excel 读取）
