from django.contrib import admin
from .models import Category, Product, StockUpdateLog, RestockLog, ProductBatch, LossLog
from django.utils.html import format_html
from datetime import date, timedelta
from django.http import HttpResponse
import csv
from django.db.models import F
from django.utils.timezone import now
from .forms import LossLogForm
from django.contrib.admin.utils import NestedObjects
from django.contrib.admin.options import get_deleted_objects
from django.db import router
from django.shortcuts import render
from django.utils.html import escape


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    # Admin configuration for Category model
    list_display = ('name',)
    search_fields = ('name',)

    def delete_model(self, request, obj):
        # Prevent deletion of categories with associated products
        if obj.product_set.exists():
            self.message_user(request, "Cannot delete category with associated products.", level='error')
        else:
            super().delete_model(request, obj)

    def delete_queryset(self, request, queryset):
        # Prevent deletion of multiple categories with associated products
        for obj in queryset:
            if obj.product_set.exists():
                self.message_user(request, f"Cannot delete category '{obj.name}' with associated products.", level='error')
            else:
                obj.delete()


class ProductBatchInline(admin.TabularInline):
    # Inline for displaying ProductBatch in ProductAdmin
    model = ProductBatch
    extra = 1  # Number of empty forms to display
    readonly_fields = ('created_at',)  # Make created_at field read-only
    can_delete = False  # Disable delete functionality in inline
    show_change_link = True  # Add link to edit the batch


def get_deleted_objects_safe(objs, request, admin_site):
    # Safely collect objects to be deleted, handling broken __str__ methods
    collector = NestedObjects(using=router.db_for_write(objs[0]._meta.model))
    collector.collect(objs)

    def safe_format_callback(obj):
        # Safely format object representation, avoiding crashes from broken __str__
        try:
            return str(obj)
        except Exception:
            return f"<Unrenderable object: {obj.__class__.__name__}>"

    return collector.nested(safe_format_callback), collector.model_count, collector


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    # Admin configuration for Product model
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
        # Display stock status with visual indicators
        if obj.is_low_stock():
            return format_html('<span style="color: red; font-weight: bold;">⚠️ LOW</span>')
        return format_html('<span style="color: green;">OK</span>')

    is_low_stock_display.short_description = 'Stock Status'

    def nearest_expiry_display(self, obj):
        # Display the nearest expiry date for the product
        nearest_expiry = obj.nearest_expiry_date
        if nearest_expiry:
            return nearest_expiry
        return "-"
    nearest_expiry_display.short_description = "Nearest Expiry"

    def preview_image(self, obj):
        # Display a preview of the product image
        if obj.image:
            return format_html('<img src="{}" width="60" height="60" style="object-fit:contain;" />', obj.image.url)
        return "-"
    preview_image.short_description = "Image"

    def has_batch_expiring_tomorrow(self, obj):
        # Check if the product has a batch expiring tomorrow
        tomorrow = now().date() + timedelta(days=1)
        if obj.batches.filter(expiry_date=tomorrow).exists():
            return format_html('<span style="color:orange;font-weight:bold;">⚠️</span>')
        return "-"
    has_batch_expiring_tomorrow.short_description = "Expiring Tomorrow"

    def total_stock_value(self, obj):
        # Calculate the total stock value for the product
        return obj.selling_price * obj.total_quantity
    total_stock_value.short_description = "Total Stock Value"
    total_stock_value.admin_order_field = 'selling_price'

    @admin.display(description="Stock Value (DA)")
    def stock_value_display(self, obj):
        # Display the stock value in DA
        return f"{obj.stock_value:.2f}"

    @admin.display(description="Potential Sales (DA)")
    def potential_sales_value_display(self, obj):
        # Display the potential sales value in DA
        return f"{obj.potential_sales_value:.2f}"

    @admin.display(description="Profit Margin (%)")
    def profit_margin_display(self, obj):
        # Display the profit margin percentage
        return f"{obj.profit_margin:.2f} %"

    def is_expiring_soon_display(self, obj):
        # Display expiry status with visual indicators
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
        # Export product batches expiring tomorrow to a CSV file
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
        # Mark products with batches expiring soon as inactive
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
        # Export products with low stock to a CSV file
        try:
            low_stock_products = [p for p in queryset if p.quantity <= p.low_stock_level]

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
                    product.quantity,
                    product.low_stock_level,
                    product.cost_price,
                    product.selling_price
                ])

            return response
        except Exception as e:
            self.message_user(request, f"Error exporting low stock products: {str(e)}", level='error')

    def save_formset(self, request, form, formset, change):
        # Improved error handling for batch saving
        instances = formset.save(commit=False)
        for instance in instances:
            try:
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
            except Exception as e:
                self.message_user(request, f"⚠️ Error saving batch: {str(e)}", level='error')
        formset.save_m2m()

    def delete_view(self, request, object_id, extra_context=None):
        # Override delete_view to use the safe version
        obj = self.get_object(request, object_id)
        if obj is None:
            return self._get_obj_does_not_exist_redirect(request, self.model._meta, object_id)

        using = router.db_for_write(self.model)
        deleted_objects, model_count, collector = get_deleted_objects_safe([obj], request, self.admin_site)

        extra_context = extra_context or {}
        extra_context.update({
            'deleted_objects': deleted_objects,
            'model_count': model_count,
            'perms_lacking': collector.perms_needed,
            'protected': collector.protected,
            'object': obj,
            'object_name': str(obj),
        })

        return super().delete_view(request, object_id, extra_context=extra_context)

    def has_delete_permission(self, request, obj=None):
        # Disable delete if the product has any batches
        if obj and obj.batches.exists():
            return False
        return super().has_delete_permission(request, obj)


@admin.register(StockUpdateLog)
class StockUpdateLogAdmin(admin.ModelAdmin):
    # Admin configuration for StockUpdateLog model
    list_display = ('product', 'field_changed', 'note', 'updated_by', 'timestamp')
    list_filter = ('change_type', 'timestamp')
    search_fields = ('product__name', 'updated_by__name')


@admin.register(RestockLog)
class RestockLogAdmin(admin.ModelAdmin):
    # Admin configuration for RestockLog model
    list_display = ('product', 'quantity_added', 'restocked_by', 'timestamp')
    list_filter = ('timestamp',)
    search_fields = ('product__name', 'restocked_by__name')


@admin.register(ProductBatch)
class ProductBatchAdmin(admin.ModelAdmin):
    # Admin configuration for ProductBatch model
    list_display = ('product', 'quantity', 'expiry_date', 'is_expired', 'is_expired_handled', 'discount_percent', 'effective_price', 'created_at')
    list_filter = ('expiry_date', 'is_expired_handled', 'discount_percent')
    search_fields = ('product__name', 'product__barcode')
    fields = ('product', 'quantity', 'expiry_date', 'is_expired_handled', 'discount_percent', 'discount_start', 'discount_end', 'created_at')
    readonly_fields = ('created_at', 'effective_price')

    def effective_price(self, obj):
        # Display the effective price in the admin panel
        return f"{obj.effective_price:.2f} DA"
    effective_price.short_description = "Effective Price"

    def is_expired(self, obj):
        # Check if the batch is expired
        if obj.expiry_date and obj.expiry_date < date.today() and not obj.is_expired_handled:
            return format_html('<span style="color: red; font-weight: bold;">❌ Expired</span>')
        return format_html('<span style="color: green;">OK</span>')
    is_expired.short_description = "Status"

    def delete_model(self, request, obj):
        # Prevent deletion of batches linked to loss logs
        if LossLog.objects.filter(batch=obj).exists():
            self.message_user(request, "Cannot delete batch linked to loss logs.", level='error')
        else:
            super().delete_model(request, obj)

    def delete_queryset(self, request, queryset):
        # Prevent deletion of multiple batches linked to loss logs
        for obj in queryset:
            if LossLog.objects.filter(batch=obj).exists():
                self.message_user(request, f"Cannot delete batch {obj} linked to loss logs.", level='error')
            else:
                obj.delete()

    @admin.action(description="Export Expired Batches with Loss Estimate")
    def export_expired_batches(self, request, queryset):
        # Export expired batches with loss estimate to a CSV file
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
    # Admin configuration for LossLog model
    form = LossLogForm
    list_display = ('batch', 'quantity_lost', 'reason', 'timestamp')
    list_filter = ('reason', 'timestamp')
    search_fields = ('batch__product__name',)
    readonly_fields = ('timestamp',)  # Make timestamp non-editable
