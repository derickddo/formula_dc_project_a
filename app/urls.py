from django.urls import path
from .views import OrderCreateView, OrderRetriveView, PaymentChargeView, MomoWebhookView




urlpatterns = [
    path('orders/<str:pk>/', OrderRetriveView.as_view(), name='order-retrive'),
    path('orders/', OrderCreateView.as_view(), name='order-create'),
    path('payments/charge/', PaymentChargeView.as_view(), name='payment-charge'),
    path('webhooks/momo/', MomoWebhookView.as_view(), name='momo-webhook'),


]