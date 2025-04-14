FROM python:3.11-slim
ARG APP_VERSION="indev"
ENV APP_VERSION=${APP_VERSION}
WORKDIR /app

COPY src/main.py .
COPY requirements.txt .

RUN pip install -r requirements.txt

CMD ["python", "main.py", "monitor"]
