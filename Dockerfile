FROM python:3.11-slim
WORKDIR /app
RUN pip install --no-cache-dir discord.py google-generativeai openai requests flask
COPY . /app
EXPOSE 8080
CMD ["python", "bot.py"]
