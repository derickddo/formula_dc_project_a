import hashlib
import hmac
import json
from django.forms import ValidationError
from rest_framework import generics, status
from rest_framework.response import Response

from core import settings
from .models import Order, Customer, Payment
from .serializers import OrderSerializer, PaymentSerializer
from rest_framework.permissions import AllowAny
from rest_framework.views import APIView
from django.db import transaction
from .tasks import send_confirmation_message
import logging

logger = logging.getLogger(__name__)




class OrderCreateView(APIView):
    """
    Create a new order with items.
    """
    serializer_class = OrderSerializer
    permission_classes = [AllowAny]


    def post(self, request, *args, **kwargs):
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    
    
class OrderRetriveView(APIView):
    """
    Retrieve an order by its ID.
    """
    permission_classes = [AllowAny]

    def get(self, request, pk, *args, **kwargs):
        try:
            order = Order.objects.get(pk=pk)
            serializer = OrderSerializer(order)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Order.DoesNotExist:
            return Response({"detail": "Order not found."}, status=status.HTTP_404_NOT_FOUND)


class PaymentChargeView(generics.CreateAPIView):
    """
    Charge a payment for an order.
    """
   
    serializer_class = PaymentSerializer

    def create(self, request, *args, **kwargs):
        idempotency_key = request.headers.get("Idempotency-Key")
        if not idempotency_key:
            return Response(
                {"error": "Idempotency-Key header is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        with transaction.atomic():
            existing_payment = Payment.objects.filter(idempotency_key=idempotency_key).first()
            if existing_payment:
                # return the existing payment to enforce idempotency
                serializer = self.get_serializer(existing_payment)
                return Response(serializer.data, status=status.HTTP_200_OK)

            # normal create
            serializer = self.get_serializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            payment = serializer.save(idempotency_key=idempotency_key)

        # TODO: Call provider (e.g. MTN) here
        # simulate initiated for now
        payment.status = "Initiated"
        payment.save()

        return Response(self.get_serializer(payment).data, status=status.HTTP_201_CREATED)


class MomoWebhookView(APIView):
    """
    Handle MoMo Webhooks:
    - Verify HMAC signature
    - Ensure idempotency (same provider_transaction_id won't be processed twice)
    - Update payment & order status
    - Enqueue confirmation job
    """

    def post(self, request, *args, **kwargs):
        
        signature = request.META.get("HTTP_X_MOMO_SIGNATURE")
        # 1. Get the raw payload
        raw_payload = request.body.decode('utf-8')

        payment = ""

        # 2. Parse the raw payload into a dictionary
        try:
            payload_dict = json.loads(raw_payload)
        except json.JSONDecodeError:
            return Response({"error": "Invalid JSON payload"}, status=status.HTTP_400_BA_REQUEST)
        
        # 3. Canonicalize the payload by re-dumping it
        # This creates a consistent string for hashing, ignoring whitespace and key order
        payload_string = json.dumps(payload_dict, separators=(',', ':'), sort_keys=True)
        
        hmac_hash = hmac.new(
            settings.MOMO_WEBHOOK_SECRET.encode("utf-8"),
            payload_string.encode('utf-8'),
            hashlib.sha256,
        ).hexdigest()
      

        if not hmac.compare_digest(hmac_hash, signature or ""):
            logger.error("Invalid signature in Momo webhook payload")
            return Response({"error": "Invalid signature"}, status=status.HTTP_401_UNAUTHORIZED)

        # 2. Extract provider transaction id for idempotency
        provider_reference = request.data.get("provider_reference")
        if not provider_reference:
            logger.error("Missing provider_reference in Momo webhook payload")  
            return Response({"error": "Missing provider_reference"}, status=status.HTTP_400_BAD_REQUEST)

        # 3. Process payment atomically
        with transaction.atomic():
            # Idempotency check: payment already processed
            payment = Payment.objects.filter(provider_reference=provider_reference).first()

            if payment:
                # If a payment with this reference already exists, the transaction has
                # already been processed. Return a 200 OK to avoid retries.
                logger.info(f"Payment with reference {provider_reference} already processed.")
                return Response({"message": "Payment already processed"}, status=status.HTTP_200_OK)

            # Try locating payment by order_id
            order_id = request.data.get("order_id")
            try:
                payment = Payment.objects.select_for_update().get(order__id=order_id)

            except Payment.DoesNotExist:
                logger.info(f"Payment record not found for order {order_id}")
                return Response({"error": "Payment record not found"}, status=status.HTTP_404_NOT_FOUND)

            # Update payment status
            status_from_provider = request.data.get("status")
            if status_from_provider == "success":
                payment.status = "Success"
                payment.provider_reference = provider_reference
                payment.save()

                # Update order
                order = payment.order
                order.status = "Paid"
                order.save()

                # Enqueue async confirmation job (idempotent worker)
                logger.info(f"Enqueuing confirmation job for order {order.id}")
                send_confirmation_message.delay(order.id)
            else:
                payment.status = status_from_provider or "failed"
                payment.save()


        return Response({"message": "Payment Webhook processed successfully"}, status=status.HTTP_200_OK)