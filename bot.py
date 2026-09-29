import os
import asyncio
import discord

from discord.ext import commands
from openai import OpenAI
from google import genai

from flask import Flask
from threading import Thread


# =========================================================
# WEB SERVER - GIỮ BOT ONLINE TRÊN RENDER
# =========================================================

app = Flask(__name__)


@app.route("/")
def home():
    return "Bot Discord 3 AI đang hoạt động!"


def run_web():
    app.run(host="0.0.0.0", port=8080)


def keep_alive():
    thread = Thread(target=run_web)
    thread.daemon = True
    thread.start()


# =========================================================
# API KEYS - LẤY TỪ ENVIRONMENT VARIABLES
# =========================================================

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")


# Kiểm tra thiếu key
missing = []

if not GEMINI_API_KEY:
    missing.append("GEMINI_API_KEY")

if not OPENAI_API_KEY:
    missing.append("OPENAI_API_KEY")

if not DEEPSEEK_API_KEY:
    missing.append("DEEPSEEK_API_KEY")

if not DISCORD_TOKEN:
    missing.append("DISCORD_TOKEN")

if missing:
    raise RuntimeError(
        "Thiếu Environment Variables: " + ", ".join(missing)
    )


# =========================================================
# KHỞI TẠO 3 AI
# =========================================================

gemini_client = genai.Client(
    api_key=GEMINI_API_KEY
)

openai_client = OpenAI(
    api_key=OPENAI_API_KEY
)

deepseek_client = OpenAI(
    api_key=DEEPSEEK_API_KEY,
    base_url="https://api.deepseek.com"
)


# =========================================================
# DISCORD
# =========================================================

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(
    command_prefix="!",
    intents=intents
)


# =========================================================
# CẤU HÌNH CUỘC TRÒ CHUYỆN
# =========================================================

MAX_ROUNDS = 6

# Mỗi AI chỉ được tạo tối đa khoảng này ký tự
MAX_AI_RESPONSE = 3000

# Không cho 2 cuộc tranh luận chạy cùng lúc trong 1 channel
channel_locks = {}


# =========================================================
# GỌI GEMINI
# =========================================================

def ask_gemini(prompt):

    try:
        response = gemini_client.models.generate_content(
            model="gemini-3.8-flash",
            contents=prompt
        )

        return response.text or "Gemini không trả về nội dung."

    except Exception as e:
        return f"❌ Gemini lỗi: {e}"


# =========================================================
# GỌI CHATGPT
# =========================================================

def ask_chatgpt(prompt):

    try:
        response = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Bạn là ChatGPT, một thành viên trong cuộc "
                        "tranh luận giữa 3 AI. Hãy đọc lời của các AI "
                        "trước đó và đưa ra phản hồi tự nhiên. "
                        "Không được giả vờ là Gemini hoặc DeepSeek."
                    )
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ]
        )

        return response.choices[0].message.content or \
            "ChatGPT không trả về nội dung."

    except Exception as e:
        return f"❌ ChatGPT lỗi: {e}"


# =========================================================
# GỌI DEEPSEEK
# =========================================================

def ask_deepseek(prompt):

    try:
        response = deepseek_client.chat.completions.create(
            model="deepseek-flash",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Bạn là DeepSeek, một thành viên trong "
                        "cuộc tranh luận giữa 3 AI. Hãy đọc toàn bộ "
                        "những gì các AI trước đã nói và phản hồi "
                        "tự nhiên. Không được giả vờ là Gemini "
                        "hoặc ChatGPT."
                    )
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ]
        )

        return response.choices[0].message.content or \
            "DeepSeek không trả về nội dung."

    except Exception as e:
        return f"❌ DeepSeek lỗi: {e}"


# =========================================================
# CHIA TIN NHẮN DISCORD
# =========================================================

async def send_long_message(channel, text):

    if not text:
        return

    # Discord giới hạn khoảng 2000 ký tự/tin nhắn
    chunks = []

    while len(text) > 1900:
        cut = text.rfind("\n", 0, 1900)

        if cut < 500:
            cut = 1900

        chunks.append(text[:cut])
        text = text[cut:].lstrip()

    if text:
        chunks.append(text)

    for chunk in chunks:
        await channel.send(chunk)


# =========================================================
# TẠO CONTEXT CHO AI
# =========================================================

def build_prompt(topic, conversation):

    transcript = ""

    for name, answer in conversation:
        transcript += (
            f"\n\n===== {name} =====\n"
            f"{answer[:MAX_AI_RESPONSE]}"
        )

    return f"""
Chủ đề do người dùng đưa ra:

{topic}

Đây là cuộc trò chuyện giữa 3 AI.

Lịch sử cuộc trò chuyện:
{transcript}

Hãy tiếp tục cuộc trò chuyện.

Yêu cầu:
- Đọc lời của các AI trước.
- Có thể đồng ý hoặc phản biện.
- Nếu AI trước nói sai, hãy chỉ ra.
- Không lặp lại nguyên văn câu trả lời trước.
- Nói tự nhiên như đang trò chuyện với 2 AI khác.
- Không nói "tôi không thể trò chuyện với AI khác".
- Không cần giải thích rằng bạn là AI.
- Trả lời ngắn gọn nhưng có nội dung.
"""


# =========================================================
# LỆNH !AI
# =========================================================

@bot.command(name="ai")
async def chat_with_all(ctx, *, topic: str = None):

    if not topic:
        await ctx.send(
            "⚠️ Ông nhập chủ đề sau `!ai` nha.\n\n"
            "Ví dụ:\n"
            "`!ai Minecraft có gì hay?`"
        )
        return

    channel_id = ctx.channel.id

    # Tạo lock cho channel
    if channel_id not in channel_locks:
        channel_locks[channel_id] = asyncio.Lock()

    # Nếu đang có cuộc trò chuyện khác
    if channel_locks[channel_id].locked():
        await ctx.send(
            "⏳ Ba AI đang nói chuyện rồi ông ơi, "
            "đợi cuộc tranh luận hiện tại kết thúc đã!"
        )
        return

    async with channel_locks[channel_id]:

        await ctx.send(
            f"🧑 **Ông:** {topic}\n\n"
            f"🤖 **Bàn tròn 3 AI bắt đầu!**\n"
            f"🔄 Tối đa {MAX_ROUNDS} lượt."
        )

        conversation = []

        # =================================================
        # 6 LƯỢT
        # =================================================

        for round_number in range(MAX_ROUNDS):

            # ---------------------------------------------
            # LƯỢT 1: GEMINI
            # ---------------------------------------------

            prompt = build_prompt(
                topic,
                conversation
            )

            gemini_text = await asyncio.to_thread(
                ask_gemini,
                prompt
            )

            conversation.append(
                ("🤖 Gemini", gemini_text)
            )

            await send_long_message(
                ctx.channel,
                f"🤖 **Gemini — lượt {round_number + 1}**\n"
                f"{gemini_text[:MAX_AI_RESPONSE]}"
            )

            # ---------------------------------------------
            # CHATGPT
            # ---------------------------------------------

            prompt = build_prompt(
                topic,
                conversation
            )

            chatgpt_text = await asyncio.to_thread(
                ask_chatgpt,
                prompt
            )

            conversation.append(
                ("🧠 ChatGPT", chatgpt_text)
            )

            await send_long_message(
                ctx.channel,
                f"🧠 **ChatGPT — lượt {round_number + 1}**\n"
                f"{chatgpt_text[:MAX_AI_RESPONSE]}"
            )

            # ---------------------------------------------
            # DEEPSEEK
            # ---------------------------------------------

            prompt = build_prompt(
                topic,
                conversation
            )

            deepseek_text = await asyncio.to_thread(
                ask_deepseek,
                prompt
            )

            conversation.append(
                ("🔵 DeepSeek", deepseek_text)
            )

            await send_long_message(
                ctx.channel,
                f"🔵 **DeepSeek — lượt {round_number + 1}**\n"
                f"{deepseek_text[:MAX_AI_RESPONSE]}"
            )

            # Nghỉ nhẹ để Discord/API không bị spam
            await asyncio.sleep(1)

        await ctx.send(
            "🏁 **Cuộc trò chuyện giữa 3 AI đã kết thúc!**"
        )


# =========================================================
# BOT READY
# =========================================================

@bot.event
async def on_ready():

    print(
        f"✅ Bot đã đăng nhập: {bot.user}"
    )

    print(
        f"🌐 Đang phục vụ {len(bot.guilds)} server."
    )


# =========================================================
# START
# =========================================================

if __name__ == "__main__":

    keep_alive()

    bot.run(DISCORD_TOKEN)
