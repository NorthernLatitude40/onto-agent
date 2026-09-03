import json
import os
import subprocess


def apply_patch_and_push():
    staging_file = "pending_reviews.json"
    
    # 防呆 1：檢查暫存檔是否存在
    if not os.path.exists(staging_file):
        print(f"ℹ️ 提示: 找不到暫存檔 {staging_file}，取消執行。")
        return

    # 防呆 2：解析 JSON 檔，防止檔案格式損毀或空白導致 Crash
    try:
        with open(staging_file, "r", encoding="utf-8") as f:
            patches = json.load(f)
    except (json.JSONDecodeError, Exception) as e:
        print(f"❌ 錯誤: 無法讀取 {staging_file} (格式損毀或無效)，原因: {e}")
        return

    if not isinstance(patches, list):
        print(f"❌ 錯誤: {staging_file} 的根層級必須是 List 清單。")
        return

    applied_count = 0

    for idx, patch in enumerate(patches):
        if not isinstance(patch, dict):
            continue

        # 防呆 3：使用 .get() 提取欄位，避免 KeyError 導致整體崩潰
        status = patch.get("status")
        target_file = patch.get("target_file")
        fixed_code = patch.get("fixed_code")
        review_id = patch.get("review_id", f"unknown_{idx}")
        issue_desc = patch.get("issue_description", "No description provided")

        if status == "PENDING_REVIEW":
            # 防呆 4：驗證關鍵欄位是否存在且不為 None
            if not target_file or fixed_code is None:
                print(
                    f"⚠️ 略過無效 Patch (ID: {review_id}): 缺少 target_file 或 fixed_code 欄位。"
                )
                continue

            try:
                # 防呆 5：自動建立目標檔案的目錄層級 (以防路徑不存在)
                target_dir = os.path.dirname(target_file)
                if target_dir:
                    os.makedirs(target_dir, exist_ok=True)

                # 1. 覆蓋原有的 .py 檔案
                with open(target_file, "w", encoding="utf-8") as py_file:
                    py_file.write(fixed_code)
                print(f"✅ 已成功將修復內容寫入檔案: {target_file} (ID: {review_id})")

                # 2. 自動執行 Git 操作 (預設註解，先不提交)
                # branch_name = f"fix/{review_id}"
                # subprocess.run(["git", "checkout", "-b", branch_name], check=True)
                # subprocess.run(["git", "add", target_file], check=True)
                # subprocess.run(["git", "commit", "-m", f"fix: {issue_desc}"], check=True)
                # subprocess.run(["git", "push", "origin", branch_name], check=True)

                # 3. 更新暫存狀態
                patch["status"] = "APPLIED"
                applied_count += 1

            except Exception as e:
                print(f"❌ 寫入或套用 Patch (ID: {review_id}) 失敗: {e}")

    # 防呆 6：更新 JSON 狀態，確保異動能安全回寫
    try:
        with open(staging_file, "w", encoding="utf-8") as f:
            json.dump(patches, f, indent=2, ensure_ascii=False)
        print(f"🎉 處理完成！共成功套用 {applied_count} 個修復單。")
    except Exception as e:
        print(f"❌ 回寫 {staging_file} 失敗: {e}")


if __name__ == "__main__":
    apply_patch_and_push()