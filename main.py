import os
import threading
import requests
from flask import Flask
import zulip

# ==========================================
# 1. Render常駐用のWebサーバー (Flask)
# ==========================================
app = Flask(__name__)

@app.route('/')
def home():
    return "Zulip Bot is Running 24/7!"

def run_web_server():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

# ==========================================
# 2. AIに返信を考えてもらう関数 (Groq API)
# ==========================================
def ask_ai(user_message):
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        return "GroqのAPIキーが設定されていません。"
    
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        'Authorization': f'Bearer {api_key}',
        'Content-Type': 'application/json'
    }
    
    # 2026年最新の安定モデル
    payload = {
        "model": "llama-3.3-70b-versatile",
        "messages": [
            {
                "role": "system", 
                "content": "あなたはチャットBotの相棒です。フランクな中学生の友達のような口調で、日本語で短く返信してね。"
            },
            {
                "role": "user", 
                "content": user_message
            }
        ]
    }
    
    try:
        response = requests.post(url, headers=headers, json=payload).json()
        
        if 'choices' in response:
            return response['choices'][0]['message']['content']
        elif 'error' in response:
            return f"🛑 Groqからのエラー： {response['error']['message']}"
        else:
            return f"❓ 予想外のデータ： {response}"
            
    except Exception as e:
        return f"💥 通信自体に失敗したよ： {e}"

# ==========================================
# 3. ZulipChatのBotメイン処理
# ==========================================
class ZulipBot:
    def __init__(self):
        self.bot_email = os.environ.get("ZULIP_BOT_EMAIL")
        
        self.client = zulip.Client(
            email=self.bot_email,
            api_key=os.environ.get("ZULIP_BOT_API_KEY"),
            site=os.environ.get("ZULIP_SITE_URL")
        )

    def handle_message(self, msg):
        # 自分が送ったメッセージには反応しない
        if msg["sender_email"] == self.bot_email:
            return

        content = msg["content"].strip()
        print(f"メッセージを受信しました: {content}")
        
        # すべてのメッセージをAIに渡す（天気などの条件分岐を完全に削除）
        reply = ask_ai(content)

        request = {
            "type": msg["type"],
            "to": msg["display_recipient"] if msg["type"] == "stream" else [msg["sender_email"]],
            "topic": msg.get("subject", ""),
            "content": reply
        }
        self.client.send_message(request)

    def start(self):
        print("Zulip Botイベントループ開始...")
        self.client.call_on_each_message(self.handle_message)

def run_zulip_bot():
    bot = ZulipBot()
    bot.start()

# ==========================================
# 4. メイン実行部分
# ==========================================
if __name__ == "__main__":
    bot_thread = threading.Thread(target=run_zulip_bot)
    bot_thread.daemon = True
    bot_thread.start()

    run_web_server()