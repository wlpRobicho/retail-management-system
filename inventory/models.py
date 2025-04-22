from django.db import models
from django.db.models import Sum, Min
from django.core.exceptions import ValidationError
from users.models import User  # Assuming you're using the same User model
from datetime import date

class Category(models.Model):
    name = models.CharField(max_length=100)

    def __str__(self):
        return self.name


class Product(models.Model):
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
        return sum(batch.quantity for batch in self.batches.all())

    def is_low_stock(self):
        return self.quantity <= self.low_stock_level

    @property
    def nearest_expiry_date(self):
        return self.batches.aggregate(nearest_expiry=Min('expiry_date'))['nearest_expiry']

    @property
    def stock_value(self):
        return self.cost_price * self.quantity

    @property
    def potential_sales_value(self):
        return self.selling_price * self.quantity

    @property
    def profit_margin(self):
        try:
            return ((self.selling_price - self.cost_price) / self.cost_price) * 100
        except ZeroDivisionError:
            return 0

    def clean(self):
        if self.cost_price < 0:
            raise ValidationError("Cost price cannot be negative.")
        if self.selling_price < 0:
            raise ValidationError("Selling price cannot be negative.")
        if self.selling_price < self.cost_price:
            raise ValidationError("Selling price cannot be lower than cost price.")

    def save(self, *args, **kwargs):
        self.full_clean()  # Ensure validation is run before saving
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.name} ({self.quantity})"


class StockUpdateLog(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    updated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    change_type = models.CharField(max_length=50)  # 'created', 'updated', 'restocked', etc.
    field_changed = models.CharField(max_length=50, null=True, blank=True)
    note = models.TextField(blank=True)
    quantity_before = models.IntegerField(null=True, blank=True)
    quantity_after = models.IntegerField(null=True, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.product.name} - {self.change_type} by {self.updated_by.name} on {self.timestamp}"


class RestockLog(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity_added = models.IntegerField()
    restocked_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.product.name} restocked by {self.restocked_by.name}"


class ProductBatch(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='batches')
    quantity = models.PositiveIntegerField()
    expiry_date = models.DateField(null=True, blank=True)  # ✅ optional
    is_expired_handled = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def clean(self):
        if self.quantity < 0:
            raise ValidationError("Batch quantity cannot be negative.")
        if self.expiry_date and self.expiry_date < date.today() and not self.is_expired_handled:
            raise ValidationError("Expiry date cannot be in the past unless marked as handled.")

    def save(self, *args, **kwargs):
        self.full_clean()  # Ensure validation is run before saving
        super().save(*args, **kwargs)

    def __str__(self):
        expiry = self.expiry_date or "No Expiry"
        return f"{self.product.name} - {self.quantity} units (Expires: {expiry})"


class LossLog(models.Model):
    LOSS_REASON_CHOICES = [
        ('expired', 'Expired'),
        ('damaged', 'Damaged'),
        ('broken', 'Broken by Customer'),
        ('other', 'Other'),
    ]

    batch = models.ForeignKey(ProductBatch, on_delete=models.CASCADE)
    quantity_lost = models.PositiveIntegerField()
    reason = models.CharField(max_length=20, choices=LOSS_REASON_CHOICES)
    logged_by = models.ForeignKey('users.User', on_delete=models.SET_NULL, null=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    @property
    def estimated_loss(self):
        return self.quantity_lost * self.batch.product.cost_price

    def clean(self):
        if self.batch.product.is_active is False:
            raise ValidationError("Cannot log loss for an inactive product.")
        if self.batch.expiry_date and self.batch.expiry_date < date.today():
            raise ValidationError("Cannot log loss for an already expired batch.")
        if self.quantity_lost < 0:
            raise ValidationError("Loss quantity cannot be negative.")
        if self.quantity_lost > self.batch.quantity:
            raise ValidationError("Loss quantity exceeds available batch quantity.")

    def __str__(self):
        return f"{self.batch.product.name} - {self.quantity_lost} lost ({self.reason})"

    def save(self, *args, **kwargs):
        self.full_clean()  # Ensure validation is run before saving
        self.batch.quantity -= self.quantity_lost
        if self.batch.quantity == 0:
            self.batch.is_expired_handled = True
        self.batch.save()
        super().save(*args, **kwargs)
