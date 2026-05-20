#!/bin/bash
# 每日自动备份关键代码目录
BACKUP_DIR="/home/ubuntu/backups/PPTTalK/$(date +%Y%m%d_%H%M%S)"
PROJECT="/home/ubuntu/workspace/PPTTalK"

mkdir -p "$BACKUP_DIR"

cp -r "$PROJECT/frontend-new/src" "$BACKUP_DIR/frontend-src" 2>/dev/null
cp -r "$PROJECT/wav2lip_workspce/lx/测试/services" "$BACKUP_DIR/services-测试" 2>/dev/null
cp -r "$PROJECT/wav2lip_workspce/lx/测试/api" "$BACKUP_DIR/api-测试" 2>/dev/null
cp -r "$PROJECT/digital_human_interface/routers" "$BACKUP_DIR/routers-gateway" 2>/dev/null
cp -r "$PROJECT/digital_human_interface/services" "$BACKUP_DIR/services-gateway" 2>/dev/null

# 保留最近 7 天的备份
find /home/ubuntu/backups/PPTTalK/ -maxdepth 1 -type d -mtime +7 -exec rm -rf {} \;

echo "[$(date)] Backup completed: $BACKUP_DIR"
