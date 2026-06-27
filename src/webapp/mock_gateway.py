import os
import sys
import logging
import time
import pymysql
from flask import Flask, request, jsonify

# 只看錯誤日誌，保持控制台乾淨
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
)
logging.getLogger("werkzeug").setLevel(logging.ERROR)

app = Flask(__name__)

DB_CONFIG = {
    "host": "localhost",
    "port": 3306,
    "user": "root",
    "password": "root",
    "database": "my_agent_db",
    "charset": "utf8mb4",
    "cursorclass": pymysql.cursors.DictCursor,
}


@app.route("/mock-pay-page", methods=["GET"])
def mock_pay_page():
    order_id = request.args.get("order_id")
    try:
        connection = pymysql.connect(**DB_CONFIG)
        with connection.cursor() as cursor:
            sql = "SELECT o.order_id, o.total_amount, o.status FROM orders o WHERE o.order_id = %s"
            cursor.execute(sql, (order_id,))
            order_rows = cursor.fetchall()
            if not order_rows:
                return f"<h3>找不到訂單 ID: {order_id}</h3>", 404
            main_order = order_rows[0]
            if main_order["status"] == "PAID":
                return "<h3>提示：該訂單已支付完成。</h3>"
    except Exception as e:
        return f"<h3>資料庫連線異常: {str(e)}</h3>", 500
    finally:
        if "connection" in locals() and connection.open:
            connection.close()

    return f"""
    <html>
      <body style="text-align: center; padding-top: 50px; font-family: sans-serif;">
        <h2>微信支付模擬器</h2>
        <p>系統訂單 ID: {order_id} | 金額: ￥{main_order['total_amount']}</p>
        <button id="payBtn" style="padding: 10px 20px; background: #07c160; color: white; border: none; cursor: pointer;">確認模擬付款</button>
        <script>
          document.getElementById('payBtn').onclick = function() {{
            fetch('/mock-wechat-webhook', {{
              method: 'POST',
              headers: {{ 'Content-Type': 'application/json' }},
              body: JSON.stringify({{ "order_id": "{order_id}", "result_code": "SUCCESS" }})
            }}).then(() => {{ alert('付款成功！'); window.close(); }});
          }}
        </script>
      </body>
    </html>
    """


@app.route("/mock-wechat-webhook", methods=["POST"])
def mock_wechat_webhook():
    data = request.json or {}
    order_id = data.get("order_id")
    if data.get("result_code") == "SUCCESS":
        try:
            connection = pymysql.connect(**DB_CONFIG)
            with connection.cursor() as cursor:
                cursor.execute(
                    "UPDATE `orders` SET `status` = 'PAID' WHERE `order_id` = %s",
                    (order_id,),
                )
                connection.commit()
                return jsonify({"return_code": "SUCCESS"}), 200
        except Exception:
            pass
        finally:
            if "connection" in locals() and connection.open:
                connection.close()
    return jsonify({"return_code": "FAIL"}), 400


if __name__ == "__main__":
    print("🚀 微信支付模擬網關已在 http://127.0.0.1:5000 啟動...")
    app.run(host="0.0.0.0", port=5000, debug=False)
