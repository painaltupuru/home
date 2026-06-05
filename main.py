import os
import threading
import requests
from flask import Flask
import zulip

# ==========================================
# 1. Render居眠り防止用のWebサーバー設定 (Flask)
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
    
    # モデル名を最新の安定版に指定
    payload = {
        "model": "llama-3.3-70b-specdec",
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
        
        # 【ここを改造！】エラーがあればその理由をそのままチャットに返す
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
        # 【超重要・修正】os.environ.get("この中身") は、登録した名前（キー名）を書きます
        # 直接アドレスやURLを入れるとエラーになって動かなくなります
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
        print(f"メッセージを受信: {content}")

        # Groq AIに返信を考えてもらう
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