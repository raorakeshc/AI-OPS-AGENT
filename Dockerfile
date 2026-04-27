# Use an official Python runtime as a parent image
FROM python:3.11-slim

# Set the working directory in the container
WORKDIR /app

# Copy requirements first to leverage Docker cache
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application
COPY src/ /app/src/
COPY data/ /app/data/

# Define environment variable placeholder (should be passed at runtime)
ENV GOOGLE_API_KEY=""

# Run the agent when the container launches
CMD ["python", "-m", "src.agent"]
