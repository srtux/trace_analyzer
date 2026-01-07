# Use an official Python runtime as a parent image
FROM python:3.11-slim

# Set the working directory in the container
WORKDIR /app

# Copy the requirements file and install dependencies
COPY trace_analyzer/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code
COPY . .

# Expose the port the app runs on (ADK default is 8080)
EXPOSE 8080

# Define the command to run the application
CMD ["adk", "run", "trace_analyzer.agent:root_agent", "--port", "8080", "--host", "0.0.0.0"]
