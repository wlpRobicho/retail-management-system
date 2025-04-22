from django.db import models
from inventory.models import Product, ProductBatch
from users.models import User
from django.utils.timezone import now
import random
import string

# Utility function to generate random discount codes
def generate_discount_code(length=8):
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=length))

# Represents a sales transaction (sale or refund)
class SalesTransaction(models.Model):
    PAYMENT_METHODS = (
        ('cash', 'Cash'),
        ('card', 'Card'),
        ('refund', 'Refund'),
    )

    cashier = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)  # The cashier handling the transaction
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)  # Total amount of the transaction
    total_profit = models.DecimalField(max_digits=10, decimal_places=2)  # Total profit from the transaction
    payment_method = models.CharField(max_length=10, choices=PAYMENT_METHODS, default='cash')  # Payment method used
    change_due = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)  # Change to return (if cash)
    timestamp = models.DateTimeField(default=now)  # Timestamp of the transaction
    amount_received = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)  # Amount received (if cash)
    is_refund = models.BooleanField(default=False)  # Indicates if the transaction is a refund
    discount_code = models.ForeignKey('DiscountCode', on_delete=models.SET_NULL, null=True, blank=True)  # Discount code applied
    receipt = models.FileField(upload_to='receipts/', null=True, blank=True)  # PDF receipt file

    def __str__(self):
        # String representation includes ID, date, total amount, and payment method
        return f"#{self.id} | {self.timestamp.strftime('%Y-%m-%d')} | {self.total_amount} DA | {self.payment_method.capitalize()}"

    def save(self, *args, **kwargs):
        # Ensure total_amount and total_profit are not null
        if self.total_amount is None:
            self.total_amount = 0
        if self.total_profit is None:
            self.total_profit = 0
        super().save(*args, **kwargs)

# Represents an individual item in a sales transaction
class SalesItem(models.Model):
    transaction = models.ForeignKey(SalesTransaction, related_name='items', on_delete=models.CASCADE)  # Linked transaction
    product = models.ForeignKey(Product, on_delete=models.CASCADE)  # Product being sold
    batch = models.ForeignKey(ProductBatch, on_delete=models.CASCADE)  # Batch of the product
    quantity = models.DecimalField(max_digits=10, decimal_places=2)  # Quantity sold
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)  # Price per unit
    cost_price = models.DecimalField(max_digits=10, decimal_places=2)  # Cost price per unit
    profit = models.DecimalField(max_digits=10, decimal_places=2)  # Profit from this item

    def __str__(self):
        # String representation includes quantity, product name, unit price, and batch ID
        return f"{self.quantity} x {self.product.name} (DA {self.unit_price}) from Batch {self.batch.id}"

# Logs actions performed on sales (e.g., sold, refunded)
class SaleLog(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE)  # Product involved in the action
    batch = models.ForeignKey(ProductBatch, on_delete=models.SET_NULL, null=True)  # Batch involved in the action
    quantity = models.DecimalField(max_digits=10, decimal_places=2)  # Quantity involved in the action
    action = models.CharField(max_length=100, default='sold')  # Action type (e.g., sold, refund)
    transaction = models.ForeignKey(SalesTransaction, on_delete=models.CASCADE)  # Linked transaction
    performed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)  # User who performed the action
    timestamp = models.DateTimeField(auto_now_add=True)  # Timestamp of the action

    def __str__(self):
        # String representation includes quantity, product name, transaction ID, and user
        return f"{self.quantity} x {self.product.name} in Sale #{self.transaction.id} by {self.performed_by.name}"

# Represents a cashier's shift
class CashierShift(models.Model):
    cashier = models.ForeignKey(User, on_delete=models.CASCADE)  # Cashier assigned to the shift
    start_time = models.DateTimeField(auto_now_add=True)  # Start time of the shift
    end_time = models.DateTimeField(null=True, blank=True)  # End time of the shift
    starting_cash = models.DecimalField(max_digits=10, decimal_places=2)  # Starting cash for the shift
    ending_cash_reported = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)  # Reported ending cash
    is_closed = models.BooleanField(default=False)  # Indicates if the shift is closed

    def __str__(self):
        # String representation includes cashier name, date, and shift status
        status = "Closed" if self.is_closed else "Open"
        return f"Shift for {self.cashier.name} on {self.start_time.strftime('%Y-%m-%d')} ({status})"

# Represents a discount code
class DiscountCode(models.Model):
    code = models.CharField(max_length=8, unique=True, editable=False)  # Unique discount code
    assigned_to = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)  # User assigned to the code
    is_active = models.BooleanField(default=True)  # Indicates if the code is active
    created_at = models.DateTimeField(auto_now_add=True)  # Timestamp when the code was created

    def save(self, *args, **kwargs):
        # Generate a random code if not already set
        if not self.code:
            self.code = generate_discount_code()
        super().save(*args, **kwargs)

    def __str__(self):
        # String representation includes code, assigned user, and active status
        return f"{self.code} - {'Unassigned' if not self.assigned_to else self.assigned_to.name} (Active: {self.is_active})"
