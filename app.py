"""
Postgres Handler.
- Consumes messages from the RabbitMQ queue to insert SMS data into a Postgres database.
"""

import os
import threading
import logging
import json
from datetime import datetime, timezone
import time
import psycopg
import pika
import pika.exceptions
import pytz
from flask import Flask
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()
APP_PORT = os.getenv("APP_PORT", "3000")
RABBITMQ_HOST = os.getenv("RABBITMQ_HOST", "wbor-rabbitmq")
RABBITMQ_USER = os.getenv("RABBITMQ_USER", "guest")
RABBITMQ_PASS = os.getenv("RABBITMQ_PASS", "guest")
POSTGRES_QUEUE = os.getenv("POSTGRES_QUEUE", "postgres")
POSTGRES_HOST = os.getenv("POSTGRES_HOST", "wbor-postgres")
POSTGRES_DB = os.getenv("POSTGRES_DB")
POSTGRES_USER = os.getenv("POSTGRES_USER", "postgres")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD")
POSTGRES_TABLE = os.getenv("POSTGRES_TABLE")

# Logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# Define a handler to output to the console
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.DEBUG)


class EasternTimeFormatter(logging.Formatter):
    """Custom log formatter to display timestamps in Eastern Time"""

    def formatTime(self, record, datefmt=None):
        # Convert UTC to Eastern Time
        eastern = pytz.timezone("America/New_York")
        utc_dt = datetime.fromtimestamp(record.created, tz=timezone.utc)
        eastern_dt = utc_dt.astimezone(eastern)
        # Use ISO 8601 format
        return eastern_dt.isoformat()


formatter = EasternTimeFormatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)
logging.getLogger("werkzeug").setLevel(logging.INFO)

app = Flask(__name__)


def connect_to_postgres():
    """Establish a connection to the Postgres database."""
    try:
        conn = psycopg.connect(
            host=POSTGRES_HOST,
            dbname=POSTGRES_DB,
            user=POSTGRES_USER,
            password=POSTGRES_PASSWORD,
        )
        logger.info("Connected to Postgres database.")
        return conn
    except psycopg.Error as e:
        logger.error("Error connecting to Postgres: %s", e)
        return None


def callback(ch, method, _properties, body):
    """Callback function to process messages from the RabbitMQ queue."""
    logger.info("Callback triggered.")
    try:
        message = json.loads(body)
        logger.debug("Received message: %s", message)

        # Process and insert SMS data into Postgres
        logger.debug("Processing message from %s", message.get("From"))

        conn = connect_to_postgres()
        if conn:
            try:
                with conn.cursor() as cursor:
                    # Prepare additional columns and values for From(LocationType) if they exist
                    location_columns = []
                    location_values = []
                    for loc_type in ["FromCity", "FromState", "FromCountry", "FromZip"]:
                        if message.get(loc_type):
                            location_columns.append(f'"{loc_type}"')
                            location_values.append(message.get(loc_type))

                    # Prepare additional columns and values for media items
                    media_columns = []
                    media_values = []
                    for i in range(10):
                        media_type_key = f"MediaContentType{i}"
                        media_url_key = f"MediaUrl{i}"

                        if message.get(media_type_key):
                            media_columns.append(f'"MediaContentType{i}"')
                            media_values.append(message.get(media_type_key))

                        if message.get(media_url_key):
                            media_columns.append(f'"MediaUrl{i}"')
                            media_values.append(message.get(media_url_key))

                    # Combine static columns with dynamic columns
                    columns = (
                        [
                            '"MessageSid"',
                            '"AccountSid"',
                            '"MessagingServiceSid"',
                            '"From"',
                            '"To"',
                            '"Body"',
                            '"NumSegments"',
                            '"NumMedia"',
                            '"ApiVersion"',
                        ]
                        + location_columns
                        + media_columns
                    )
                    values = (
                        [
                            message.get("MessageSid"),
                            message.get("AccountSid"),
                            message.get("MessagingServiceSid"),
                            message.get("From"),
                            message.get("To"),
                            message.get("Body"),
                            message.get("NumSegments"),
                            message.get("NumMedia"),
                            message.get("ApiVersion"),
                        ]
                        + location_values
                        + media_values
                    )

                    # Check if the number of columns matches the number of values
                    if len(columns) != len(values):
                        raise ValueError(
                            "Mismatch between columns and values: "
                            f"{len(columns)} columns, {len(values)} values"
                        )

                    # Build the query with dynamic columns
                    query = f"""
                        INSERT INTO {POSTGRES_TABLE} ({', '.join(columns)})
                        VALUES ({', '.join(['%s'] * len(values))})
                    """
                    cursor.execute(query, values)

                conn.commit()
                logger.info("Inserted message into Postgres.")
                ch.basic_ack(delivery_tag=method.delivery_tag)
            except psycopg.errors.DatabaseError as db_error:
                logger.error("Database error during insertion: %s", db_error)
            finally:
                conn.close()
        else:
            logger.error("No database connection available.")
    except (json.JSONDecodeError, KeyError) as e:
        logger.error("Failed to process message: %s", e)


def consume_messages():
    """Consume messages from the RabbitMQ queue."""
    while True:
        logger.debug("Attempting to connect to RabbitMQ...")
        credentials = pika.PlainCredentials(RABBITMQ_USER, RABBITMQ_PASS)
        parameters = pika.ConnectionParameters(
            host=RABBITMQ_HOST, credentials=credentials
        )
        try:
            connection = pika.BlockingConnection(parameters)
            channel = connection.channel()

            # Declare the dead-letter exchange and queue
            channel.exchange_declare(
                exchange="dead_letter_exchange", exchange_type="direct"
            )
            channel.queue_declare(queue="dead_letter_queue", durable=True)
            channel.queue_bind(
                exchange="dead_letter_exchange", queue="dead_letter_queue"
            )

            channel.queue_declare(
                queue=POSTGRES_QUEUE,
                durable=True,
                arguments={
                    "x-message-ttl": 60000,  # TTL of 60 seconds
                    "x-dead-letter-exchange": "dead_letter_exchange",
                },
            )
            channel.basic_consume(
                queue=POSTGRES_QUEUE, on_message_callback=callback, auto_ack=False
            )  # auto_ack=False to ensure messages are not lost if the consumer crashes
            logger.info("Now ready to consume messages.")
            channel.start_consuming()
        except pika.exceptions.AMQPConnectionError as e:
            logger.error("Failed to connect to RabbitMQ: %s", e)
            logger.debug("Retrying in 5 seconds...")
            time.sleep(5)


def retry_dead_messages():
    """Retry messages from the dead-letter queue."""
    while True:
        logger.debug("Attempting to connect to RabbitMQ for retry...")
        credentials = pika.PlainCredentials(RABBITMQ_USER, RABBITMQ_PASS)
        parameters = pika.ConnectionParameters(
            host=RABBITMQ_HOST, credentials=credentials
        )
        try:
            connection = pika.BlockingConnection(parameters)
            channel = connection.channel()

            # Consume messages from the dead-letter queue
            def retry_callback(ch, method, properties, body):
                logger.info("Retrying message from dead-letter queue.")
                ch.basic_publish(exchange="", routing_key=POSTGRES_QUEUE, body=body)
                ch.basic_ack(delivery_tag=method.delivery_tag)

            channel.basic_consume(
                queue="dead_letter_queue",
                on_message_callback=retry_callback,
                auto_ack=False,
            )
            logger.info("Now ready to retry messages from dead-letter queue.")
            channel.start_consuming()
        except pika.exceptions.AMQPConnectionError as e:
            logger.error("Failed to connect to RabbitMQ for retry: %s", e)
            logger.debug("Retrying in 5 seconds...")
            time.sleep(5)


@app.route("/")
def hello_world():
    """Serve a simple static Hello World page at the root"""
    return "<h1>wbor-postgres-driver is online!</h1>"


if __name__ == "__main__":
    logger.info("Starting Flask app and RabbitMQ consumer...")

    main_consumer_thread = threading.Thread(target=consume_messages)
    main_consumer_thread.start()

    # Start the retry consumer in a separate thread
    retry_consumer_thread = threading.Thread(target=retry_dead_messages)
    retry_consumer_thread.start()

    app.run(host="0.0.0.0", port=APP_PORT)