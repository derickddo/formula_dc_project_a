from rest_framework import serializers
from .models import Customer, Product, Order, OrderItem, Payment


class ProductSerializer(serializers.ModelSerializer):
    class Meta:
        model = Product
        fields = ["id", "name", "description", "price"]


class OrderItemSerializer(serializers.ModelSerializer):
    # product = serializers.PrimaryKeyRelatedField(queryset=Product.objects.all())

    class Meta:
        model = OrderItem
        fields = ["id", "product", "quantity", "unit_price"]
        read_only_fields = ["unit_price"]


class OrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True)
    customer = serializers.PrimaryKeyRelatedField(queryset=Customer.objects.all())

    class Meta:
        model = Order
        fields = [
            "id",
            "customer",
            "total_amount",
            "items",
            "created_at",
            "status",
        ]
        read_only_fields = ["status", "total_amount", "created_at", "status"]

    def create(self, validated_data):
        items_data = validated_data.pop("items")
        order = Order.objects.create(**validated_data)

        total = 0
        for item_data in items_data:
            product = item_data["product"]
            quantity = item_data["quantity"]
            unit_price = product.price
            total_price = unit_price * quantity

            OrderItem.objects.create(
                order=order,
                product=product,
                quantity=quantity,
                unit_price=unit_price,
            )
            total += total_price

        order.total_amount = total
        order.save()
        return order


class PaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payment
        fields = [
            "id",
            "order",
            "amount",
            "idempotency_key",
            "provider_reference",
            "status",
            "created_at",
        ]
        read_only_fields = ["id", "status", "provider_reference", "created_at", "idempotency_key", "amount"]

    def create(self, validated_data):
        order = validated_data["order"]
        # enforce order amount
        validated_data["amount"] = order.total_amount  

        return super().create(validated_data)



