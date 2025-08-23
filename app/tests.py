import uuid
import pytest
import hmac
import hashlib
import json
from decimal import Decimal
from uuid import uuid4

from django.urls import reverse
from django.conf import settings
from unittest.mock import patch

# Assumes models and the view are in a file named `your_app_name/models.py`
# and `your_app_name/views.py`.
from app.models import Order, Payment, Customer, Product

# We'll use this view to test the endpoint
from app.views import MomoWebhookView


# Fixture to prepare the database with a user, order, and payment
# The `db` fixture from `pytest-django` ensures a clean, transactional database for each test.
@pytest.fixture
def setup_test_data(db):
    """
    Creates a customer, product, an order, and a pending payment for testing.
    """
    customer = Customer.objects.create(username="testuser")
    product = Product.objects.create(name="Test Product", price=Decimal("50.00"))
    order = Order.objects.create(customer=customer, total_amount=Decimal("100.00"))
    # The webhook view will look up the payment by order ID
    payment = Payment.objects.create(
        order=order,
        amount=Decimal("100.00"),
        idempotency_key=str(uuid4()), # Use a unique UUID for the idempotency key
        status="INITIATED"
    )
    return {
        "order": order,
        "payment": payment,
        "product": product,
        "customer": customer,
    }

# Fixture to generate the canonical payload and HMAC signature
@pytest.fixture
def generate_webhook_payload(setup_test_data):
    """
    Returns a dictionary with the canonical payload and HMAC signature.
    This encapsulates the logic for creating a valid webhook payload.
    """
    order = setup_test_data["order"]
    # The provider reference should be unique to the transaction
    provider_reference = "MO-TXN-12345"

    # This is the payload that the webhook provider will send.
    # We must use the string representation of the UUID
    payload_dict = {
        "order_id": str(order.id),
        "provider_reference": provider_reference,
        "status": "success",
        "amount": "100.00", # String representation of Decimal is often used in webhooks
    }

    # The canonical payload string for hashing, sorting keys is critical
    payload_string = json.dumps(payload_dict, separators=(',', ':'), sort_keys=True)
    
    # Calculate the HMAC signature using your secret key
    signature = hmac.new(
        settings.MOMO_WEBHOOK_SECRET.encode("utf-8"),
        payload_string.encode('utf-8'),
        hashlib.sha256,
    ).hexdigest()

    return {
        "payload_dict": payload_dict,
        "signature": signature,
        "provider_reference": provider_reference,
    }


# The `client` fixture is provided by `pytest-django` and acts as a test web client
def test_happy_path_success(client, setup_test_data, generate_webhook_payload):
    """
    Tests the "happy path" where a valid webhook successfully updates a
    pending payment and its associated order to a "SUCCESS" state.
    """
    # Use a mock to verify that the confirmation message task is called
    with patch("app.views.send_confirmation_message.delay") as mock_task:
        # Get the payload and signature from the fixture
        payload = generate_webhook_payload["payload_dict"]
        signature = generate_webhook_payload["signature"]
        
        webhook_url = reverse("momo-webhook")
        
        # Send the POST request to the webhook endpoint
        response = client.post(
            webhook_url,
            data=payload,
            content_type="application/json",
            HTTP_X_MOMO_SIGNATURE=signature
        )

        # 1. Assert the HTTP response is 200 OK
        assert response.status_code == 200

        # 2. Refresh the payment and order objects from the database
        payment = Payment.objects.get(id=setup_test_data["payment"].id)
        order = Order.objects.get(id=setup_test_data["order"].id)
        
        # 3. Assert the database was updated correctly
        assert payment.status == "Success"
        assert payment.provider_reference == generate_webhook_payload["provider_reference"]
        assert order.status == "Paid"
        
        # 4. Assert that the confirmation task was enqueued
        mock_task.assert_called_once_with(order.id)


def test_webhook_replay_idempotency(client, setup_test_data, generate_webhook_payload):
    """
    Tests the idempotency of the webhook view by sending the same
    payload twice. The second request should not cause any duplicate effects.
    """
    # Use a mock to verify that the task is NOT called on the second request
    with patch("app.views.send_confirmation_message.delay") as mock_task:
        payload = generate_webhook_payload["payload_dict"]
        signature = generate_webhook_payload["signature"]
        webhook_url = reverse("momo-webhook")

        # First webhook call (simulates the initial transaction)
        first_response = client.post(
            webhook_url,
            data=payload,
            content_type="application/json",
            HTTP_X_MOMO_SIGNATURE=signature
        )
        assert first_response.status_code == 200
        mock_task.assert_called_once() # Verify the task was called on the first run

        # Second webhook call with the EXACT SAME payload
        second_response = client.post(
            webhook_url,
            data=payload,
            content_type="application/json",
            HTTP_X_MOMO_SIGNATURE=signature
        )
        
        # 1. Assert the second response is also 200 OK
        assert second_response.status_code == 200
        
        # 2. Assert no duplicate records were created
        assert Order.objects.count() == 1
        assert Payment.objects.count() == 1
        
        # 3. Assert the state of the objects did not change
        payment = Payment.objects.get(id=setup_test_data["payment"].id)
        order = Order.objects.get(id=setup_test_data["order"].id)
        assert payment.status == "Success"
        assert order.status == "Paid"

        # 4. Assert the task was NOT called again
        mock_task.assert_called_once() # The call count is still 1
