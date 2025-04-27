from rest_framework import serializers
from rest_framework.exceptions import ValidationError, PermissionDenied
from .models import SalesTransaction, SalesItem, SaleLog, DiscountCode, CustomerLoyalty, LoyaltySettings  # new logging model inside the sales app
from inventory.models import Product, ProductBatch
from sales.models import CashierShift
from decimal import Decimal, ROUND_HALF_UP
from django.utils.timezone import now
from .utils import generate_receipt_pdf

# Serializer for individual sales items input
class SalesItemInputSerializer(serializers.Serializer):
    barcode = serializers.CharField(required=False, allow_blank=True)  # Optional barcode for product lookup
    product_id = serializers.IntegerField(required=False)  # Optional product ID for product lookup
    quantity = serializers.DecimalField(max_digits=10, decimal_places=2)  # Quantity of the product

    def validate(self, data):
        # Ensure either barcode or product_id is provided
        if not data.get('barcode') and not data.get('product_id'):
            raise serializers.ValidationError("Either barcode or product_id must be provided.")
        # Ensure quantity is greater than zero
        if data.get('quantity') <= 0:
            raise serializers.ValidationError("Quantity must be greater than zero.")
        return data

# Utility function to round decimal values to two decimal places
def round_decimal(val):
    return val.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

# Serializer for creating a sales transaction
class SalesTransactionCreateSerializer(serializers.Serializer):
    payment_method = serializers.ChoiceField(choices=["cash", "card"])  # Payment method (cash or card)
    amount_received = serializers.DecimalField(max_digits=10, decimal_places=2, required=False)  # Amount received (if cash)
    is_refund = serializers.BooleanField(default=False)  # Indicates if the transaction is a refund
    items = SalesItemInputSerializer(many=True)  # List of items in the transaction
    discount_code = serializers.CharField(max_length=8, required=False, allow_blank=True)  # Optional discount code
    phone_number = serializers.CharField(required=False, allow_blank=True)  # Optional phone number for loyalty tracking

    def validate(self, data):
        # Ensure amount_received is provided for cash payments
        if data['payment_method'] == 'cash' and not data.get('is_refund', False) and data.get('amount_received') is None:
            raise serializers.ValidationError("Amount received is required for cash payments.")
        return data

    def create(self, validated_data):
        from django.db import transaction as db_transaction

        cashier = self.context['request'].user

        # Ensure the cashier has an active shift before proceeding
        if not CashierShift.objects.filter(cashier=cashier, is_closed=False).exists():
            raise PermissionDenied("You must start a shift before making sales or refunds.")

        try:
            with db_transaction.atomic():
                # Initialize totals and other variables
                total_amount = Decimal('0.00')
                total_profit = Decimal('0.00')
                items_data = validated_data['items']
                sale_items = []
                warnings = []
                payment_method = validated_data['payment_method']
                amount_received = validated_data.get('amount_received')
                is_refund = validated_data.get('is_refund', False)
                change_due = Decimal('0.00')
                discount_code_str = validated_data.get("discount_code")
                discount_applied = False
                discount_obj = None

                # Validate and fetch discount code
                if discount_code_str:
                    try:
                        discount_obj = DiscountCode.objects.get(code=discount_code_str, is_active=True)
                        discount_applied = True
                    except DiscountCode.DoesNotExist:
                        raise serializers.ValidationError({
                            "discount_code": "This discount code is invalid or has already been used."
                        })

                # Create the SalesTransaction object
                sale = SalesTransaction.objects.create(
                    cashier=cashier,
                    total_amount=0,
                    total_profit=0,
                    payment_method=payment_method,
                    amount_received=amount_received,
                    change_due=change_due,
                    is_refund=is_refund
                )

                if not sale:
                    raise ValidationError("Transaction could not be created.")

                # Process each item in the transaction
                for item in items_data:
                    product = None
                    # Fetch product by barcode or product ID
                    if item.get('barcode'):
                        try:
                            product = Product.objects.get(barcode=item['barcode'], is_active=True)
                        except Product.DoesNotExist:
                            raise serializers.ValidationError(f"Product with barcode {item['barcode']} not found.")
                    elif item.get('product_id'):
                        try:
                            product = Product.objects.get(id=item['product_id'], is_active=True)
                        except Product.DoesNotExist:
                            raise serializers.ValidationError(f"Product with ID {item['product_id']} not found.")
                    else:
                        raise serializers.ValidationError("Product reference (barcode or ID) missing.")

                    if is_refund:
                        # Handle refunds by creating negative quantity SalesItems
                        batch = ProductBatch.objects.filter(product=product).order_by('-expiry_date', '-id').first()
                        if not batch:
                            raise serializers.ValidationError(f"No batch found for product: {product.name}")

                        deduct_qty = -Decimal(item['quantity'])  # Negative quantity for refunds
                        unit_price = round_decimal(product.selling_price)
                        cost_price = round_decimal(product.cost_price)
                        profit = round_decimal((unit_price - cost_price) * deduct_qty)

                        # Log the refund action
                        SaleLog.objects.create(
                            product=product,
                            batch=batch,
                            quantity=deduct_qty,
                            action="refund",
                            transaction=sale,
                            performed_by=cashier
                        )

                        # Update batch quantity and create SalesItem
                        batch.quantity += abs(deduct_qty)
                        batch.save()

                        SalesItem.objects.create(
                            transaction=sale,
                            product=product,
                            batch=batch,
                            quantity=deduct_qty,
                            unit_price=unit_price,
                            cost_price=cost_price,
                            profit=profit
                        )

                        sale_items.append({
                            "product": product.name,
                            "batch_id": batch.id,
                            "quantity": float(deduct_qty),
                            "unit_price": str(unit_price),
                            "original_price": str(unit_price),
                            "discount_applied": "0.00",
                            "profit": str(profit)
                        })

                        total_amount += unit_price * deduct_qty
                        total_profit += profit
                    else:
                        # Handle normal sales using FIFO for batches
                        batches = ProductBatch.objects.filter(
                            product=product,
                            quantity__gt=0
                        ).order_by('expiry_date', 'id')

                        quantity_needed = Decimal(item['quantity'])
                        for batch in batches:
                            if quantity_needed <= 0:
                                break

                            if batch.expiry_date and batch.expiry_date < now().date():
                                warnings.append(f"⚠️ Sold expired batch #{batch.id} for product: {product.name}")

                            deduct_qty = min(batch.quantity, abs(quantity_needed))

                            original_price = round_decimal(product.selling_price)
                            discounted_price = round_decimal(original_price * Decimal('0.90')) if discount_applied else original_price

                            cost_price = round_decimal(product.cost_price)
                            profit = round_decimal((discounted_price - cost_price) * deduct_qty)

                            # Create SalesItem and update batch quantity
                            SalesItem.objects.create(
                                transaction=sale,
                                product=product,
                                batch=batch,
                                quantity=deduct_qty,
                                unit_price=discounted_price,
                                cost_price=cost_price,
                                profit=profit
                            )

                            batch.quantity -= abs(deduct_qty)
                            batch.save()

                            # Log sale action
                            SaleLog.objects.create(
                                product=product,
                                batch=batch,
                                quantity=deduct_qty,
                                action="sold",
                                transaction=sale,
                                performed_by=cashier
                            )

                            sale_items.append({
                                "product": product.name,
                                "batch_id": batch.id,
                                "quantity": float(deduct_qty),
                                "unit_price": str(discounted_price),
                                "original_price": str(original_price),
                                "discount_applied": str(original_price - discounted_price) if discount_applied else "0.00",
                                "profit": str(profit)
                            })

                            quantity_needed -= abs(deduct_qty)
                            total_amount += discounted_price * deduct_qty
                            total_profit += profit

                        if quantity_needed > 0:
                            raise serializers.ValidationError(
                                f"Not enough stock for {product.name}. Missing: {quantity_needed} units."
                            )

                # Ensure at least one item was processed
                if not sale_items:
                    raise ValidationError("No valid items were processed in the transaction.")

                # Apply discount to total_amount
                if discount_applied:
                    discount_amount = total_amount * Decimal('0.10')
                    total_amount -= discount_amount

                # Handle cash payments and calculate change
                if payment_method == 'cash':
                    if not is_refund:
                        if amount_received < total_amount:
                            raise serializers.ValidationError("Amount received is less than total.")
                        change_due = round_decimal(amount_received - total_amount)

                # Update transaction totals and generate receipt
                sale.total_amount = round_decimal(total_amount)
                sale.total_profit = round_decimal(total_profit)
                sale.change_due = change_due
                sale.discount_code = discount_obj if discount_applied else None
                sale.save()

                # Mark the discount code as used
                if discount_obj:
                    discount_obj.is_active = False  # ❌ Disable the discount code after use
                    discount_obj.save()

                generate_receipt_pdf(sale)

                result = {}  # Initialize result dictionary for response

                # Track loyalty only for regular (non-refund) sales
                if not is_refund and validated_data.get("phone_number"):
                    phone = validated_data["phone_number"]
                    loyalty, _ = CustomerLoyalty.objects.get_or_create(phone_number=phone)
                    loyalty.total_spent += total_amount
                    loyalty.save()

                    settings = LoyaltySettings.objects.first()
                    if settings:
                        target = settings.spending_target
                        current_milestone = int(loyalty.total_spent // target)

                        if current_milestone > loyalty.rewards_earned:
                            # 🎉 Customer has passed a new reward threshold
                            code = DiscountCode.objects.create(type='loyalty')  # Set type to 'loyalty'
                            loyalty.rewards_earned = current_milestone
                            loyalty.save()

                            sale.loyalty_discount_code = code
                            sale.save()

                            result["loyalty_discount_code"] = code.code  # Include the discount code in the response

        except Exception as e:
            # Rollback and provide clean error message
            raise ValidationError(f"Transaction failed: {str(e)}")

        return {
            **result,  # Include loyalty discount code if generated
            "transaction_id": sale.id,
            "timestamp": sale.timestamp,
            "total_amount": str(sale.total_amount),
            "total_profit": str(sale.total_profit),
            "payment_method": sale.payment_method,
            "change_due": str(change_due) if payment_method == 'cash' else None,
            "discount_applied": "Yes - 10%" if discount_applied else "No",
            "discount_code_used": discount_obj.code if discount_applied else None,
            "items": sale_items,
            "warnings": warnings
        }

# Serializer for summarizing sales items
class SalesItemSummarySerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source='product.name', read_only=True)  # Display product name

    class Meta:
        model = SalesItem
        fields = ['product_name', 'batch', 'quantity', 'unit_price', 'profit']

# Serializer for listing sales transactions
class SalesTransactionListSerializer(serializers.ModelSerializer):
    cashier_name = serializers.CharField(source='cashier.name', read_only=True)  # Display cashier name
    items = SalesItemSummarySerializer(many=True, read_only=True)  # Include related sales items

    class Meta:
        model = SalesTransaction
        fields = ['id', 'timestamp', 'cashier_name', 'total_amount', 'total_profit', 'items']
