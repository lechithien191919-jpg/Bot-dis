import os
import discord
from discord.ext import commands
import google.generativeai as genai
from openai import OpenAI
from flask import Flask
from threading import Thread

# --- PHẦN GIẢ LẬP WEB ĐỂ RENDER GIỮ BOT ONLINE 24/7 ---
app = Flask('')

@app.route('/')
def home():
    return "Bot Discord đang hoạt động 24/7!"

def run_web():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = Thread(target=run_web)
    t.start()
# -----------------------------------------------

# --- CÁC API KEYS VÀ TOKEN ---
# (Khuyên dùng: Sau này ông có thể chuyển chúng sang Environment Variables trên Render để bảo mật tốt hơn)
GEMINI_API_KEY = "AQ.Ab8RN6J16njX47RbTp1jFS3_kNXf7lGJy2a_q_yeM2hRZmRPYQ"
OPENAI_API_KEY = "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"
DEEPSEEK_API_KEY = "sk-e4afb1859cab44279f8e0ef3d3b3876c"
DISCORD_TOKEN = "MTU1Mzc2MTczMzIwODcwMzA5MA.Gyzcqi.Cx1jzoz73DXFNeZubCpRss9IUMyIRxIYjJp2ps"

# Khởi tạo các AI client
genai.configure(api_key=GEMINI_API_KEY)
gemini_model = genai.GenerativeModel('gemini-1.5-flash')
openai_client = OpenAI(api_key=OPENAI_API_KEY)
deepseek_client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url="https://api.deepseek.com")

# Cấu hình Discord Bot Intents
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print(f'Bot đã đăng nhập thành công với tên: {bot.user}')

@bot.command(name="ai")
async def chat_with_all(ctx, *, prompt: str = None):
    # Kiểm tra nếu người dùng gõ mỗi lệnh !ai mà không có nội dung
    if not prompt:
        await ctx.send("⚠️ Ông ơi, nhớ nhập nội dung câu hỏi sau lệnh `!ai` nhé. Ví dụ: `!ai Python là gì?`")
        return

    await ctx.send(f"🤖 **Câu hỏi từ {ctx.author.mention}:** *{prompt}*\nĐang triệu hồi bộ ba AI vào bàn tròn...")

    # Gọi Gemini
    try:
        gemini_res = gemini_model.generate_content(prompt)
        gemini_text = gemini_res.text
    except Exception as e:
        gemini_text = f"Lỗi Gemini: {e}"

    # Gọi ChatGPT (OpenAI)
    try:
        chatgpt_res = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}]
        )
        chatgpt_text = chatgpt_res.choices[0].message.content
    except Exception as e:
        chatgpt_text = f"Lỗi ChatGPT: {e}"

    # Gọi DeepSeek
    try:
        deepseek_res = deepseek_client.chat.completions.create(
            model="deepseek-chat",
            messages=[{"role": "user", "content": prompt}]
        )
        deepseek_text = deepseek_res.choices[0].message.content
    except Exception as e:
        deepseek_text = f"Lỗi DeepSeek: {e}"

    # Gửi kết quả lần lượt lên Discord (cắt ngắn dưới 1900 ký tự để không bị quá giới hạn của Discord)
    await ctx.send(f"✨ **Gemini:**\n{gemini_text[:1900]}")
    await ctx.send(f"🟢 **ChatGPT:**\n{chatgpt_text[:1900]}")
    await ctx.send(f"🔵 **DeepSeek:**\n{deepseek_text[:1900]}")

# Khởi động web giả lập Flask rồi chạy bot Discord
if __name__ == "__main__":
    keep_alive()
    bot.run(DISCORD_TOKEN)
    
