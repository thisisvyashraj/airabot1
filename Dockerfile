# Use an official Python runtime
FROM python:3.10-slim

# Create a user to avoid running as root (Hugging Face requirement)
RUN useradd -m -u 1000 user
USER user
ENV PATH="/home/user/.local/bin:$PATH"

WORKDIR /app

# Copy requirements and install
COPY --chown=user requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of your code
COPY --chown=user . .

# Hugging Face routes traffic to port 7860
EXPOSE 7860

# Run the bot
CMD ["python", "aira_bot.py"]
