import json
import re
import requests


def search_campervans():
  # 1. 建立 Session 物件（它會自動儲存並帶上訪問首頁時產生的 Cookie）
  session = requests.Session()

  # 設定模擬瀏覽器的 Headers
  session.headers.update({
      "User-Agent": (
          "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML,"
          " like Gecko) Chrome/120.0.0.0 Safari/537.36"
      ),
      "Accept": (
          "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8"
      ),
      "Accept-Language": "zh-TW,zh;q=0.9,en-US;q=0.8,en;q=0.7",
  })

  base_url = "https://getlostinnz.co.nz/"
  api_url = "https://getlostinnz.co.nz/wp-json/getlost/v1/rcm/step2"

  print("[-] 正在訪問首頁以初始化 Session 並獲取 Cookie...")
  response = session.get(base_url)

  if response.status_code != 200:
    print(f"[!] 訪問首頁失敗，狀態碼: {response.status_code}")
    return

  print("[+] 首頁訪問成功！")

  # 2. 動態從首頁的 HTML 原始碼中用正規表達式抓取最新的 Nonce
  nonce_match = re.search(r'"nonce"\s*:\s*"([a-f0-9]+)"', response.text)

  if nonce_match:
    nonce = nonce_match.group(1)
    print(f"[+] 成功動態獲取 Nonce: {nonce}")
  else:
    print("[!] 未能抓取到 Nonce，請檢查頁面結構是否變動")
    return

  # 3. 設定 API 專屬的 Headers（將動態抓到的 nonce 帶入，Cookie 則由 session 自動管理夾帶）
  headers = {
      "Referer": base_url,
      "Origin": "https://getlostinnz.co.nz",
      "Content-Type": "application/json",
      "x-wp-nonce": nonce,
  }

  # 4. 準備查詢 Payload
  payload = {
      "pickupdate": "2026-11-10",
      "dropoffdate": "2026-11-17",
      "ageid": 9,
      "pickuplocationid": 1,
      "dropofflocationid": 1,
      "pickuptime": "10:00",
      "dropofftime": "10:00",
      "vehiclecategorytypeid": 2,
      "location_key": "christchurch",
      "gl_location": "christchurch",
  }

  print("[-] 正在發送 API 查詢請求...")
  # 這裡使用 session.post，它會自動把前面 get 首頁拿到並保存在 session 裡的 Cookie 送出去
  api_response = session.post(api_url, json=payload, headers=headers)

  print(f"[-] 回應狀態碼: {api_response.status_code}")

  try:
    data = api_response.json()
    print("[+] API 回應 JSON 結果：")
    print(json.dumps(data, indent=4, ensure_ascii=False))
  except Exception as e:
    print("[!] 解析 JSON 失敗，原始回應文字：")
    print(api_response.text)


if __name__ == "__main__":
  search_campervans()