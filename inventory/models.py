from django.db import models
from django.db.models import Sum, Min
from django.core.exceptions import ValidationError
from users.models import User  # Assuming you're using the same User model
from datetime import date
from decimal import Decimal

class Category(models.Model):
    # Represents a product category
    name = models.CharField(max_length=100)

    def __str__(self):
        # String representation of the category
        return self.name

    class Meta:
        verbose_name = "Category"
        verbose_name_plural = "Categories"  # Display name in admin panel


class Product(models.Model):
    # Represents a product in the inventory
    name = models.CharField(max_length=100)
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, blank=True)
    has_barcode = models.BooleanField(default=True)
    price_by_weight = models.BooleanField(default=False)  # If false, priced by unit
    barcode = models.CharField(max_length=100, blank=True, null=True, unique=True)
    cost_price = models.DecimalField(max_digits=10, decimal_places=2)
    selling_price = models.DecimalField(max_digits=10, decimal_places=2)
    low_stock_level = models.IntegerField(default=5)
    image = models.ImageField(upload_to='product_images/', null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    @property
    def quantity(self):
        # Calculate total quantity from related batches
        return sum(batch.quantity for batch in self.batches.all())

    def is_low_stock(self):
        # Check if the product is low on stock
        return self.quantity <= self.low_stock_level

    @property
    def nearest_expiry_date(self):
        # Get the nearest expiry date from related batches
        return self.batches.aggregate(nearest_expiry=Min('expiry_date'))['nearest_expiry']

    @property
    def stock_value(self):
        # Calculate the total stock value
        return self.cost_price * self.quantity

    @property
    def potential_sales_value(self):
        # Calculate the potential sales value
        return self.selling_price * self.quantity

    @property
    def profit_margin(self):
        # Calculate the profit margin as a percentage
        try:
            return ((self.selling_price - self.cost_price) / self.cost_price) * 100
        except ZeroDivisionError:
            return 0

    def clean(self):
        # Validate cost price and selling price
        if self.cost_price < 0:
            raise ValidationError("Cost price cannot be negative.")
        if self.selling_price < 0:
            raise ValidationError("Selling price cannot be negative.")
        if self.selling_price < self.cost_price:
            raise ValidationError("Selling price cannot be lower than cost price.")

    def save(self, *args, **kwargs):
        # Ensure validation is run before saving
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        # String representation of the product
        return f"{self.name} ({self.quantity})"

    class Meta:
        verbose_name = "Product"
        verbose_name_plural = "Products"
        ordering = ['-updated_at']  # Order by most recently updated


class StockUpdateLog(models.Model):
    # Logs updates to product stock
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    updated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    change_type = models.CharField(max_length=50)  # 'created', 'updated', 'restocked', etc.
    field_changed = models.CharField(max_length=50, null=True, blank=True)
    note = models.TextField(blank=True)
    quantity_before = models.IntegerField(null=True, blank=True)
    quantity_after = models.IntegerField(null=True, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        # Safely handle cases where product or updated_by is None
        product_name = self.product.name if self.product else "Unknown product"
        updated_by_name = self.updated_by.name if self.updated_by else "Unknown user"
        return f"{product_name} - {self.change_type} by {updated_by_name} on {self.timestamp}"


class RestockLog(models.Model):
    # Logs restocking actions for products
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity_added = models.IntegerField()
    restocked_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        # Safely handle cases where product or restocked_by is None
        product_name = self.product.name if self.product else "Unknown product"
        restocked_by_name = self.restocked_by.name if self.restocked_by else "Unknown user"
        return f"{product_name} restocked by {restocked_by_name}"


class ProductBatch(models.Model):
    # Represents a batch of a product
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='batches')
    quantity = models.PositiveIntegerField()
    expiry_date = models.DateField(null=True, blank=True)  # Optional expiry date
    is_expired_handled = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    discount_percent = models.PositiveIntegerField(default=0)  # Discount percentage (e.g., 10 for 10%)
    discount_start = models.DateField(null=True, blank=True)  # Start date for the discount
    discount_end = models.DateField(null=True, blank=True)  # End date for the discount

    @property
    def effective_price(self):
        # Calculate the effective price based on the discount
        today = date.today()
        if self.discount_percent > 0 and self.discount_start and self.discount_end:
            if self.discount_start <= today <= self.discount_end:
                discount_factor = Decimal(100 - self.discount_percent) / Decimal(100)
                return self.product.selling_price * discount_factor
        return self.product.selling_price

    def clean(self):
        # Validate batch quantity, expiry date, and discount logic
        if self.quantity < 0:
            raise ValidationError("Batch quantity cannot be negative.")
        if self.expiry_date and self.expiry_date < date.today() and not self.is_expired_handled:
            raise ValidationError("Expiry date cannot be in the past unless marked as handled.")
        if self.discount_percent < 0 or self.discount_percent > 100:
            raise ValidationError("Discount percent must be between 0 and 100.")
        if self.discount_start and self.discount_end and self.discount_start > self.discount_end:
            raise ValidationError("Discount start date cannot be after the end date.")

    def save(self, *args, **kwargs):
        # Ensure validation is run before saving
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        # String representation of the batch
        expiry = self.expiry_date or "No Expiry"
        return f"{self.product.name} - {self.quantity} units (Expires: {expiry})"

    class Meta:
        verbose_name = "Product Batch"
        verbose_name_plural = "Product Batches"
        ordering = ['expiry_date']  # Order by expiry date


class LossLog(models.Model):
    # Logs losses for product batches
    LOSS_REASON_CHOICES = [
        ('expired', 'Expired'),
        ('damaged', 'Damaged'),
        ('broken', 'Broken by Customer'),
        ('other', 'Other'),
    ]

    batch = models.ForeignKey(ProductBatch, on_delete=models.CASCADE)
    quantity_lost = models.PositiveIntegerField(default=0)  # Default to 0 for safety
    reason = models.CharField(max_length=20, choices=LOSS_REASON_CHOICES)
    logged_by = models.ForeignKey('users.User', on_delete=models.SET_NULL, null=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    @property
    def estimated_loss(self):
        # Calculate the estimated financial loss
        return self.quantity_lost * self.batch.product.cost_price

    def clean(self):
        # Validate loss quantity and batch status
        if self.batch.product.is_active is False:
            raise ValidationError("Cannot log loss for an inactive product.")
        if self.batch.expiry_date and self.batch.expiry_date < date.today():
            raise ValidationError("Cannot log loss for an already expired batch.")
        if self.quantity_lost < 0:
            raise ValidationError("Loss quantity cannot be negative.")
        if self.quantity_lost > self.batch.quantity:
            raise ValidationError("Loss quantity exceeds available batch quantity.")

    def save(self, *args, **kwargs):
        # Safely handle batch updates during save
        self.full_clean()
        if self.batch and self.quantity_lost <= self.batch.quantity:
            self.batch.quantity -= self.quantity_lost
            if self.batch.quantity == 0:
                self.batch.is_expired_handled = True
            self.batch.save()
        super().save(*args, **kwargs)

    def __str__(self):
        # String representation of the loss log
        return f"{self.batch.product.name} - {self.quantity_lost} lost ({self.reason})"

    class Meta:
        verbose_name = "Loss Log"
        verbose_name_plural = "Loss Logs"
        ordering = ['-timestamp']  # Order by most recent logs


class SalesItem(models.Model):
    # Represents an item in a sales transaction
    # ...existing fields...

    def __str__(self):
        # Safely handle cases where product, transaction, or cashier is None
        product_name = self.product.name if self.product else "Unknown product"
        transaction_id = self.transaction.id if self.transaction else "?"
        performed_by = getattr(self.transaction, 'cashier', None)
        performed_by_name = performed_by.name if performed_by else "Unknown"
        return f"{self.quantity} x {product_name} in Sale #{transaction_id} by {performed_by_name}"
