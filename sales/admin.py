from django.contrib import admin
from django.urls import path
from django.template.response import TemplateResponse
from django.db.models import Sum
from django.utils.timezone import now
from django.http import HttpResponse
from django.utils.html import format_html
import csv
from .models import SalesTransaction, SalesItem, SaleLog, CashierShift, DiscountCode, CustomerLoyalty, LoyaltySettings
from .models import AnalyticsDummy
from django.shortcuts import redirect

# Inline admin for displaying SalesItem details within a SalesTransaction
class SalesItemInline(admin.TabularInline):
    model = SalesItem
    extra = 0
    readonly_fields = ['product', 'batch', 'quantity', 'unit_price', 'cost_price', 'profit']
    can_delete = False

# Admin configuration for SalesTransaction
@admin.register(SalesTransaction)
class SalesTransactionAdmin(admin.ModelAdmin):
    list_display = ['id', 'timestamp', 'cashier', 'total_amount', 'payment_method', 'discount_code', 'loyalty_discount_code', 'receipt_link']
    list_filter = ['timestamp', 'cashier', 'payment_method', 'is_refund']
    search_fields = ['id', 'cashier__name']
    readonly_fields = ['cashier', 'timestamp', 'total_amount', 'total_profit', 'payment_method', 'amount_received', 'change_due', 'is_refund', 'discount_code', 'loyalty_discount_code', 'receipt']
    inlines = [SalesItemInline]
    actions = ['export_as_csv']

    # Adds a clickable link to download the receipt PDF
    def receipt_link(self, obj):
        if obj.receipt:
            return format_html('<a href="{}" target="_blank">📄 Download</a>', obj.receipt.url)
        return "-"
    receipt_link.short_description = "Receipt PDF"

    # Action to export selected transactions as a CSV file
    @admin.action(description="Export selected transactions as CSV")
    def export_as_csv(self, request, queryset):
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="transactions.csv"'

        writer = csv.writer(response)
        writer.writerow(['ID', 'Cashier', 'Date', 'Total', 'Profit', 'Payment', 'Refund'])

        for tx in queryset:
            writer.writerow([
                tx.id,
                tx.cashier.name,
                tx.timestamp,
                tx.total_amount,
                tx.total_profit,
                tx.payment_method,
                "Yes" if tx.is_refund else "No"
            ])
        return response

# Adds a custom analytics view to the admin panel
from django.contrib import admin
from django.template.response import TemplateResponse
from .models import AnalyticsDummy  # Import it from your models

@admin.register(AnalyticsDummy)
class AnalyticsDummyAdmin(admin.ModelAdmin):
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def changelist_view(self, request, extra_context=None):
        # Redirect to your Angular analytics page
        return redirect('http://localhost:4200/analytics')

    
# Admin configuration for SalesItem
@admin.register(SalesItem)
class SalesItemAdmin(admin.ModelAdmin):
    list_display = ['transaction', 'product', 'batch', 'quantity', 'unit_price', 'profit']
    list_filter = ['product', 'batch', 'transaction__timestamp']
    readonly_fields = ['transaction', 'product', 'batch', 'quantity', 'unit_price', 'cost_price', 'profit']

# Admin configuration for SaleLog
@admin.register(SaleLog)
class SaleLogAdmin(admin.ModelAdmin):
    list_display = ('product', 'quantity', 'action', 'performed_by', 'timestamp')
    list_filter = ('action', 'timestamp', 'performed_by')
    search_fields = ('product__name',)

# Admin configuration for CashierShift
@admin.register(CashierShift)
class CashierShiftAdmin(admin.ModelAdmin):
    list_display = ['cashier', 'start_time', 'end_time', 'starting_cash', 'ending_cash_reported', 'is_closed']
    list_filter = ['is_closed', 'start_time']
    search_fields = ['cashier__name', 'cashier__userid']
    actions = ['end_shift_and_download_csv']

    # Action to end a shift and export its summary as a CSV file
    @admin.action(description="End Shift and Export CSV")
    def end_shift_and_download_csv(self, request, queryset):
        if queryset.count() != 1:
            self.message_user(request, "Please select exactly one shift to close and export.", level='error')
            return

        shift = queryset.first()
        if shift.is_closed:
            self.message_user(request, "Shift already closed.", level='warning')
            return

        # Get all sales for this shift (based on cashier and start_time)
        transactions = SalesTransaction.objects.filter(
            cashier=shift.cashier,
            timestamp__gte=shift.start_time,
            timestamp__lte=shift.end_time or now()
        )

        total_cash = sum(float(t.total_amount) for t in transactions if t.payment_method == 'cash' and t.total_amount > 0)
        total_card = sum(float(t.total_amount) for t in transactions if t.payment_method == 'card' and t.total_amount > 0)
        refund_total = sum(abs(t.total_amount) for t in transactions if t.total_amount < 0)
        total_profit = sum(float(t.total_profit) for t in transactions)

        # Close the shift
        shift.end_time = now()
        shift.is_closed = True
        shift.save()

        # Generate CSV
        response = HttpResponse(content_type='text/csv')
        filename = f"shift_summary_{shift.cashier.userid}_{shift.start_time.date()}.csv"
        response['Content-Disposition'] = f'attachment; filename="{filename}"'

        writer = csv.writer(response)
        writer.writerow(['Cashier', 'Start Time', 'End Time', 'Starting Cash', 'Reported Ending Cash'])
        writer.writerow([shift.cashier.name, shift.start_time, shift.end_time, shift.starting_cash, shift.ending_cash_reported])
        writer.writerow([])

        writer.writerow(['Total Cash Sales', 'Total Card Sales (if used)', 'Total Refunds', 'Total Profit'])
        writer.writerow([f"{total_cash:.2f}", f"{total_card:.2f}", f"{refund_total:.2f}", f"{total_profit:.2f}"])

        return response

# Admin configuration for DiscountCode
@admin.register(DiscountCode)
class DiscountCodeAdmin(admin.ModelAdmin):
    list_display = ['code', 'type', 'assigned_to', 'is_active', 'created_at']
    list_filter = ['type', 'is_active', 'created_at']  # Add filter for type
    search_fields = ['code', 'assigned_to__name']
    readonly_fields = ['code']  # You can see it but not edit

# Admin configuration for CustomerLoyalty
@admin.register(CustomerLoyalty)
class CustomerLoyaltyAdmin(admin.ModelAdmin):
    # Admin configuration for CustomerLoyalty model
    list_display = ['phone_number', 'total_spent', 'discount_given']
    search_fields = ['phone_number']

# Admin configuration for LoyaltySettings
@admin.register(LoyaltySettings)
class LoyaltySettingsAdmin(admin.ModelAdmin):
    # Admin configuration for LoyaltySettings model
    list_display = ['spending_target', 'discount_percentage']
