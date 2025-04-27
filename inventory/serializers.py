from rest_framework import serializers
from django.db import transaction
from .models import Category, Product, ProductBatch, StockUpdateLog

class CategorySerializer(serializers.ModelSerializer):
    # Serializer for the Category model
    class Meta:
        model = Category
        fields = ['id', 'name']

class ProductSerializer(serializers.ModelSerializer):
    # Serializer for the Product model
    is_low_stock = serializers.SerializerMethodField()  # Computed field to check low stock status

    class Meta:
        model = Product
        fields = [
            'id', 'name', 'category', 'barcode', 'cost_price', 'selling_price',
            'quantity', 'low_stock_level', 'is_low_stock', 'image', 'created_at',
            'updated_at', 'is_active', 'has_barcode', 'price_by_weight'
        ]
        read_only_fields = ['created_at', 'updated_at', 'is_low_stock']  # Fields that cannot be modified

    def get_is_low_stock(self, obj):
        # Compute whether the product is low on stock
        return obj.is_low_stock()

    def validate_barcode(self, value):
        # Validate the barcode field
        if self.instance and not self.instance.has_barcode:
            return value  # Skip validation if the product doesn't require a barcode
        if value is None:
            raise serializers.ValidationError("Barcode is required.")
        if not value.isdigit():
            raise serializers.ValidationError("Barcode must contain only digits.")
        if len(value) < 8 or len(value) > 13:
            raise serializers.ValidationError("Barcode must be between 8 and 13 digits.")
        return value

    def validate_cost_price(self, value):
        # Ensure cost price is non-negative
        if value < 0:
            raise serializers.ValidationError("Cost price must be a non-negative number.")
        return value

    def validate_selling_price(self, value):
        # Ensure selling price is non-negative
        if value < 0:
            raise serializers.ValidationError("Selling price must be a non-negative number.")
        return value

    def validate(self, data):
        # Validate cost price and selling price relationships
        if data['cost_price'] < 0 or data['selling_price'] < 0:
            raise serializers.ValidationError("Prices must be positive.")
        if data['quantity'] < 0:
            raise serializers.ValidationError("Quantity must be zero or more.")
        if data['selling_price'] < data['cost_price']:
            raise serializers.ValidationError("Selling price cannot be lower than cost price.")
        return data

class ProductBatchSerializer(serializers.ModelSerializer):
    # Serializer for the ProductBatch model
    effective_price = serializers.ReadOnlyField()  # Expose the calculated effective price

    class Meta:
        model = ProductBatch
        fields = '__all__'  # Include all fields, including discount fields and effective_price

    def validate_quantity(self, value):
        # Ensure batch quantity is non-negative
        if value < 0:
            raise serializers.ValidationError("Batch quantity must be a non-negative number.")
        return value

    def validate_product(self, value):
        # Ensure the product is active before creating a batch
        if not value.is_active:
            raise serializers.ValidationError("Cannot create a batch for an inactive product.")
        return value

    def validate_expiry_date(self, value):
        # Ensure expiry date is not in the past
        if value and value < date.today():
            raise serializers.ValidationError("Expiry date cannot be in the past.")
        return value

    @transaction.atomic
    def create(self, validated_data):
        # Create a batch and log the creation in a transaction
        batch = super().create(validated_data)
        StockUpdateLog.objects.create(
            product=batch.product,
            updated_by=self.context['request'].user,  # Log the user who created the batch
            change_type='batch added',
            field_changed='quantity',
            quantity_after=batch.quantity,
            note=f"Batch created with expiry {batch.expiry_date}"
        )
        return batch
