from django.contrib import admin
from .models import Category, Product, StockUpdateLog, RestockLog, ProductBatch, LossLog
from django.utils.html import format_html
from datetime import date, timedelta
from django.http import HttpResponse
import csv
from django.db.models import F
from django.utils.timezone import now
from .forms import LossLogForm


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name',)
    search_fields = ('name',)

    def delete_model(self, request, obj):
        if obj.product_set.exists():
            self.message_user(request, "Cannot delete category with associated products.", level='error')
        else:
            super().delete_model(request, obj)

    def delete_queryset(self, request, queryset):
        for obj in queryset:
            if obj.product_set.exists():
                self.message_user(request, f"Cannot delete category '{obj.name}' with associated products.", level='error')
            else:
                obj.delete()


class ProductBatchInline(admin.TabularInline):
    model = ProductBatch
    extra = 1
    readonly_fields = ('created_at',)


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = (
        'name', 'category', 'quantity', 'low_stock_level',
        'is_low_stock_display', 'is_expiring_soon_display', 'selling_price',
        'cost_price', 'stock_value_display', 'potential_sales_value_display',
        'profit_margin_display', 'is_active'
    )
    list_filter = ('category', 'is_active')
    search_fields = ('name', 'barcode')
    readonly_fields = ('created_at', 'updated_at', 'preview_image')
    fieldsets = (
        (None, {
            'fields': (
                'name', 'category', 'barcode', 'has_barcode', 'price_by_weight',
                'cost_price', 'selling_price', 'low_stock_level', 'image',
                'preview_image', 'is_active'
            )
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
        }),
    )
    actions = [
        'export_products_with_batches_expiring_tomorrow',
        'deactivate_expiring_products',
        'export_low_stock_csv'
    ]
    ordering = ('-updated_at',)
    inlines = [ProductBatchInline]

    def is_low_stock_display(self, obj):
        if obj.is_low_stock():
            return format_html('<span style="color: red; font-weight: bold;">⚠️ LOW</span>')
        return format_html('<span style="color: green;">OK</span>')

    is_low_stock_display.short_description = 'Stock Status'

    def nearest_expiry_display(self, obj):
        nearest_expiry = obj.nearest_expiry_date
        if nearest_expiry:
            return nearest_expiry
        return "-"
    nearest_expiry_display.short_description = "Nearest Expiry"

    def preview_image(self, obj):
        if obj.image:
            return format_html('<img src="{}" width="60" height="60" style="object-fit:contain;" />', obj.image.url)
        return "-"
    preview_image.short_description = "Image"

    def has_batch_expiring_tomorrow(self, obj):
        tomorrow = now().date() + timedelta(days=1)
        if obj.batches.filter(expiry_date=tomorrow).exists():
            return format_html('<span style="color:orange;font-weight:bold;">⚠️</span>')
        return "-"
    has_batch_expiring_tomorrow.short_description = "Expiring Tomorrow"

    def total_stock_value(self, obj):
        return obj.selling_price * obj.total_quantity
    total_stock_value.short_description = "Total Stock Value"
    total_stock_value.admin_order_field = 'selling_price'

    @admin.display(description="Stock Value (DA)")
    def stock_value_display(self, obj):
        return f"{obj.stock_value:.2f}"

    @admin.display(description="Potential Sales (DA)")
    def potential_sales_value_display(self, obj):
        return f"{obj.potential_sales_value:.2f}"

    @admin.display(description="Profit Margin (%)")
    def profit_margin_display(self, obj):
        return f"{obj.profit_margin:.2f} %"

    def is_expiring_soon_display(self, obj):
        today = date.today()
        tomorrow = today + timedelta(days=1)

        # Check if any batch is expiring today or tomorrow and not handled
        if obj.batches.filter(
            expiry_date__in=[today, tomorrow],
            is_expired_handled=False,
            quantity__gt=0
        ).exists():
            return format_html('<span style="color: orange; font-weight: bold;">⚠️ Expiring Soon</span>')

        # Show 'No Expiry' if all batches have null expiry
        if obj.batches.exists() and obj.batches.filter(expiry_date__isnull=True).count() == obj.batches.count():
            return format_html('<span style="color: gray;">No Expiry</span>')

        return "-"
    is_expiring_soon_display.short_description = "Expiry Status"

    @admin.action(description="Export Product Batches Expiring Tomorrow")
    def export_products_with_batches_expiring_tomorrow(self, request, queryset):
        tomorrow = date.today() + timedelta(days=1)
        expiring_batches = ProductBatch.objects.filter(
            expiry_date=tomorrow,
            product__in=queryset,
            product__is_active=True,
            is_expired_handled=False,
            quantity__gt=0
        )

        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="expiring_batches_tomorrow.csv"'

        writer = csv.writer(response)
        writer.writerow(['Product Name', 'Barcode', 'Batch Quantity', 'Expiry Date'])

        if not expiring_batches.exists():
            writer.writerow(["No items found"])
            return response

        for batch in expiring_batches:
            expiry = batch.expiry_date.strftime('%Y-%m-%d') if batch.expiry_date else 'No Expiry'
            writer.writerow([
                batch.product.name.encode('utf-8').decode('utf-8'),
                batch.product.barcode,
                batch.quantity,
                expiry
            ])

        return response

    @admin.action(description="Mark Expiring Products as Inactive")
    def deactivate_expiring_products(self, request, queryset):
        try:
            target_date = date.today() + timedelta(days=1)
            for product in queryset:
                if product.batches.filter(expiry_date__lte=target_date).exists():
                    product.is_active = False
                    product.save()
        except Exception as e:
            self.message_user(request, f"Error deactivating products: {str(e)}", level='error')

    @admin.action(description="Export Low Stock Products to CSV")
    def export_low_stock_csv(self, request, queryset):
        try:
            low_stock_products = [p for p in queryset if p.total_quantity <= p.low_stock_level]

            response = HttpResponse(content_type='text/csv')
            filename = f"low_stock_{now().strftime('%Y-%m-%d')}.csv"
            response['Content-Disposition'] = f'attachment; filename="{filename}"'

            writer = csv.writer(response)
            writer.writerow(['Name', 'Barcode', 'Category', 'Total Quantity', 'Low Stock Threshold', 'Cost Price', 'Selling Price'])

            if not low_stock_products:
                writer.writerow(["No items found"])
                return response

            for product in low_stock_products:
                writer.writerow([
                    product.name.encode('utf-8').decode('utf-8'),
                    product.barcode,
                    product.category.name.encode('utf-8').decode('utf-8') if product.category else '',
                    product.total_quantity,
                    product.low_stock_level,
                    product.cost_price,
                    product.selling_price
                ])

            return response
        except Exception as e:
            self.message_user(request, f"Error exporting low stock products: {str(e)}", level='error')

    def save_formset(self, request, form, formset, change):
        instances = formset.save(commit=False)
        for instance in instances:
            if isinstance(instance, ProductBatch) and instance.pk is None:  # New batch
                instance.save()
                StockUpdateLog.objects.create(
                    product=instance.product,
                    updated_by=request.user,
                    change_type='batch added',
                    field_changed='quantity',
                    quantity_after=instance.quantity,
                    note=f"Batch added with expiry {instance.expiry_date}"
                )
            else:
                instance.save()
        formset.save_m2m()


@admin.register(StockUpdateLog)
class StockUpdateLogAdmin(admin.ModelAdmin):
    list_display = ('product', 'field_changed', 'note', 'updated_by', 'timestamp')
    list_filter = ('change_type', 'timestamp')
    search_fields = ('product__name', 'updated_by__name')


@admin.register(RestockLog)
class RestockLogAdmin(admin.ModelAdmin):
    list_display = ('product', 'quantity_added', 'restocked_by', 'timestamp')
    list_filter = ('timestamp',)
    search_fields = ('product__name', 'restocked_by__name')


@admin.register(ProductBatch)
class ProductBatchAdmin(admin.ModelAdmin):
    list_display = ('product', 'quantity', 'expiry_date', 'is_expired', 'is_expired_handled', 'created_at')
    list_filter = ('expiry_date', 'is_expired_handled')
    search_fields = ('product__name', 'product__barcode')
    actions = ['export_expired_batches']

    def is_expired(self, obj):
        if obj.expiry_date and obj.expiry_date < date.today() and not obj.is_expired_handled:
            return format_html('<span style="color: red; font-weight: bold;">❌ Expired</span>')
        return format_html('<span style="color: green;">OK</span>')
    is_expired.short_description = "Status"

    def delete_model(self, request, obj):
        if LossLog.objects.filter(batch=obj).exists():
            self.message_user(request, "Cannot delete batch linked to loss logs.", level='error')
        else:
            super().delete_model(request, obj)

    def delete_queryset(self, request, queryset):
        for obj in queryset:
            if LossLog.objects.filter(batch=obj).exists():
                self.message_user(request, f"Cannot delete batch {obj} linked to loss logs.", level='error')
            else:
                obj.delete()

    @admin.action(description="Export Expired Batches with Loss Estimate")
    def export_expired_batches(self, request, queryset):
        expired_qs = queryset.filter(
            expiry_date__lt=date.today(),
            is_expired_handled=False,
            quantity__gt=0
        )

        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="expired_batches_with_loss.csv"'

        writer = csv.writer(response)
        writer.writerow(['Product', 'Barcode', 'Expiry Date', 'Quantity', 'Cost Price', 'Estimated Loss'])

        if not expired_qs.exists():
            writer.writerow(["No items found"])
            return response

        for batch in expired_qs:
            product = batch.product
            estimated_loss = batch.quantity * product.cost_price
            writer.writerow([
                product.name.encode('utf-8').decode('utf-8'),
                product.barcode,
                batch.expiry_date,
                batch.quantity,
                product.cost_price,
                f"{estimated_loss:.2f}"
            ])

        return response


@admin.register(LossLog)
class LossLogAdmin(admin.ModelAdmin):
    form = LossLogForm
    list_display = ('batch', 'quantity_lost', 'reason', 'timestamp')
    list_filter = ('reason', 'timestamp')
    search_fields = ('batch__product__name',)
