from rest_framework import serializers
from .models import Category, Product, ProductBatch


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ['id', 'name']


class ProductSerializer(serializers.ModelSerializer):
    is_low_stock = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = [
            'id', 'name', 'category', 'barcode', 'cost_price', 'selling_price',
            'quantity', 'low_stock_level', 'is_low_stock', 'image', 'created_at',
            'updated_at', 'is_active', 'has_barcode', 'price_by_weight'
        ]
        read_only_fields = ['created_at', 'updated_at', 'is_low_stock']

    def get_is_low_stock(self, obj):
        return obj.is_low_stock()

    def validate_barcode(self, value):
        if self.instance and not self.instance.has_barcode:
            return value  # Skip validation if the product doesn't require a barcode
        if not value.isdigit():
            raise serializers.ValidationError("Barcode must contain only digits.")
        if len(value) < 8 or len(value) > 13:
            raise serializers.ValidationError("Barcode must be between 8 and 13 digits.")
        return value

    def validate_cost_price(self, value):
        if value < 0:
            raise serializers.ValidationError("Cost price must be a non-negative number.")
        return value

    def validate_selling_price(self, value):
        if value < 0:
            raise serializers.ValidationError("Selling price must be a non-negative number.")
        return value

    def validate(self, data):
        if data['cost_price'] < 0 or data['selling_price'] < 0:
            raise serializers.ValidationError("Prices must be positive.")
        if data['quantity'] < 0:
            raise serializers.ValidationError("Quantity must be zero or more.")
        if data['selling_price'] < data['cost_price']:
            raise serializers.ValidationError("Selling price cannot be lower than cost price.")
        return data


class ProductBatchSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductBatch
        fields = '__all__'

    def validate_quantity(self, value):
        if value < 0:
            raise serializers.ValidationError("Batch quantity must be a non-negative number.")
        return value

    def validate_product(self, value):
        if not value.is_active:
            raise serializers.ValidationError("Cannot create a batch for an inactive product.")
        return value

    def validate_expiry_date(self, value):
        if value and value < date.today():
            raise serializers.ValidationError("Expiry date cannot be in the past.")
        return value
