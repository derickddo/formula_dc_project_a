from django.db import transaction
from celery import shared_task
from .models import Order
import logging


logger = logging.getLogger(__name__)

@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_confirmation_message(self, order_id):
    try:
        with transaction.atomic():
            order = Order.objects.select_for_update().get(id=order_id)

            if order.confirmation_sent:
                logger.info(f"Message for order {order_id} already sent. Skipping.")
                return

            # Simulate sending a message
            logger.info(f"SEND_MSG to {order.customer.phone_number} for order {order_id}")
            provider_message_id = "mock_provider_id"

            # Mark as sent
            order.confirmation_sent = True
            order.save(update_fields=["confirmation_sent"])

        logger.info(f"Message sent successfully. Provider ID: {provider_message_id}")

    except Order.DoesNotExist:
        logger.error(f"Order with ID {order_id} not found.")
        raise
