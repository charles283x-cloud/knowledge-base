# Google Drive 同步配置指南

本指南说明如何在腾讯云服务器上配置 Google Drive → 知识库的定时同步。

## 1. 安装 rclone

```bash
sudo apt update
sudo apt install -y rclone
```

验证安装：

```bash
rclone version
```

## 2. 配置 Google Drive 远程

因为服务器没有浏览器，需要在**本地电脑**辅助授权。

### 步骤 A：在本地电脑上获取授权令牌

1. 在本地电脑安装 rclone（[下载页面](https://rclone.org/downloads/)）
2. 运行以下命令：

```bash
rclone authorize "drive"
```

3. 浏览器会弹出 Google 登录页面，登录你的 Google 账号并授权
4. 授权成功后，终端会显示一段 JSON 格式的 token，形如：

```json
{"access_token":"ya29.xxx","token_type":"Bearer","refresh_token":"1//xxx","expiry":"2026-..."}
```

5. **复制整段 token**

### 步骤 B：在服务器上配置 rclone

SSH 登录服务器后运行：

```bash
rclone config
```

按提示操作：

1. 输入 `n` 创建新远程
2. 名称输入 `gdrive`
3. 类型选择 `drive`（Google Drive）—— 输入对应编号
4. `client_id` 和 `client_secret` 直接回车（留空使用默认）
5. `scope` 选择 `1`（完全访问权限）
6. `service_account_file` 直接回车
7. 自动配置选 `n`（因为是远程服务器）
8. 粘贴**步骤 A 中获取的 token**
9. 确认配置，输入 `y`

验证配置是否成功：

```bash
rclone lsd gdrive:
```

应该能看到你 Google Drive 根目录下的文件夹列表。

## 3. 验证同步文件夹路径

确认目标文件夹可以访问：

```bash
rclone ls "gdrive:1、日本储能项目" --max-depth 1
```

如果能看到文件列表，说明路径正确。

## 4. 部署同步脚本

同步脚本 `sync_gdrive.py` 已包含在项目代码中。确保项目代码已更新：

```bash
cd /opt/knowledge-base
git pull origin main
pip3 install -r requirements.txt
```

手动测试同步：

```bash
cd /opt/knowledge-base
sudo -u www-data DATA_DIR=/var/data/knowledge-base python3 sync_gdrive.py
```

> 如果用户权限不是 www-data，换成实际运行 Flask 的用户。

## 5. 配置定时任务（Cron）

创建 cron 任务，每小时自动同步：

```bash
sudo crontab -e
```

添加以下行：

```cron
0 * * * * cd /opt/knowledge-base && DATA_DIR=/var/data/knowledge-base /usr/bin/python3 sync_gdrive.py >> /var/data/knowledge-base/sync_cron.log 2>&1
```

> 含义：每小时第 0 分钟执行同步。

如需更频繁（如每 30 分钟）：

```cron
*/30 * * * * cd /opt/knowledge-base && DATA_DIR=/var/data/knowledge-base /usr/bin/python3 sync_gdrive.py >> /var/data/knowledge-base/sync_cron.log 2>&1
```

## 6. 同步范围说明

当前配置同步以下 Google Drive 文件夹：

| Google Drive 路径 | 知识库文件夹 |
|---|---|
| `My Drive/1、日本储能项目` | `1、日本储能项目` |

如需修改同步范围，编辑 `sync_gdrive.py` 中的 `GDRIVE_FOLDERS` 列表：

```python
GDRIVE_FOLDERS = [
    '1、日本储能项目',
    # 在这里添加更多文件夹...
]
```

## 7. 日志查看

同步日志位于：

```
/var/data/knowledge-base/sync.log      # 脚本日志
/var/data/knowledge-base/sync_cron.log  # cron 输出
```

查看最近日志：

```bash
tail -50 /var/data/knowledge-base/sync.log
```

## 8. 注意事项

- **单向同步**：Google Drive → 服务器，不会反向上传
- **文件类型**：只导入 .docx .xlsx .xls .pdf .pptx .ppt 文件
- **子文件夹**：会自动在知识库中创建对应的文件夹层级
- **去重机制**：按文件名 + 文件夹 + 文件大小判断，相同文件不会重复导入
- **更新检测**：如果 Google Drive 上的文件大小发生变化，会自动重新导入
- **同步账号**：导入的文档显示上传者为 `gdrive-sync`
