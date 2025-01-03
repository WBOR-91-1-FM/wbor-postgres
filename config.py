"""
App configuration file. Load environment variables from .env file.
"""

import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Application configuration
APP_PORT = os.getenv("APP_PORT", "3000")

# RabbitMQ configuration
RABBITMQ_HOST = os.getenv("RABBITMQ_HOST", "rabbitmq")
RABBITMQ_USER = os.getenv("RABBITMQ_USER", "guest")
RABBITMQ_PASS = os.getenv("RABBITMQ_PASS", "guest")
RABBITMQ_EXCHANGE = os.getenv("RABBITMQ_EXCHANGE", "source_exchange")
RABBITMQ_DL_EXCHANGE = os.getenv("RABBITMQ_DL_EXCHANGE", "dead_letter_exchange")
MAX_RETRIES = int(os.getenv("MAX_RETRIES", "5"))
RABBITMQ_DL_QUEUE = os.getenv("RABBITMQ_DL_QUEUE", "dead_letter_queue")
POSTGRES_QUEUE = os.getenv("POSTGRES_QUEUE", "postgres")

# Postgres configuration
POSTGRES_HOST = os.getenv("POSTGRES_HOST", "wbor-postgres")
POSTGRES_DB = os.getenv("POSTGRES_DB")
POSTGRES_USER = os.getenv("POSTGRES_USER", "postgres")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD")

# Table names
MESSAGES_TABLE = os.getenv("MESSAGES_TABLE", "messages")
SENT_MESSAGES_TABLE = os.getenv("SENT_MESSAGES_TABLE", "sent_sms")
GROUPME_TABLE = os.getenv("GROUPME_TABLE", "groupme")
GROUPME_CALLBACK_TABLE = os.getenv("GROUPME_CALLBACK_TABLE", "groupme_callbacks")
