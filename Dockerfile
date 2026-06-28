# Use a lightweight python image
FROM python:3.13-slim

# Set the working directory
WORKDIR /app

# Copy requirements and install them first to leverage Docker layer caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of your application code
COPY . .

# Run your bot
CMD ["python", "aira_bot.py"]
