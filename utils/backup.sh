#!/bin/bash
# 檔案：utils/backup.sh
# 用法：./utils/backup.sh <要備份的檔案路徑>
# 說明：針對 PI 環境最佳化的備份輪替腳本，自動處理 bak01 -> bak02 -> bak03 的推移。

if [ -z "$1" ]; then
  echo "錯誤：未提供檔案路徑。"
  echo "用法: ./utils/backup.sh <file_path>"
  exit 1
fi

FILE_PATH="$1"
BASENAME=$(basename "$FILE_PATH")
BAK_DIR="bak"

if [ ! -f "$FILE_PATH" ]; then
  echo "錯誤：找不到檔案 $FILE_PATH，無法備份。"
  exit 1
fi

mkdir -p "$BAK_DIR"

# 備份輪替邏輯 (bak02 -> bak03, bak01 -> bak02, 原檔 -> bak01)
if [ -f "${BAK_DIR}/${BASENAME}.bak02" ]; then
  mv "${BAK_DIR}/${BASENAME}.bak02" "${BAK_DIR}/${BASENAME}.bak03"
fi

if [ -f "${BAK_DIR}/${BASENAME}.bak01" ]; then
  mv "${BAK_DIR}/${BASENAME}.bak01" "${BAK_DIR}/${BASENAME}.bak02"
fi

# 複製原檔成為第一代備份
cp "$FILE_PATH" "${BAK_DIR}/${BASENAME}.bak01"
echo "✅ 成功：$FILE_PATH 已完成備份輪替，最新備份為 ${BAK_DIR}/${BASENAME}.bak01"
