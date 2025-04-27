import django_filters
from .models import Product, ProductBatch
from django.db import models
from django.utils import timezone
from datetime import timedelta, date
from django.db.models import Sum, F, Exists, OuterRef

class ProductFilter(django_filters.FilterSet):
    category = django_filters.NumberFilter(field_name='category__id')
    barcode = django_filters.CharFilter(lookup_expr='icontains')
    name = django_filters.CharFilter(lookup_expr='icontains')
    is_active = django_filters.BooleanFilter()

    # Range filters
    cost_price_min = django_filters.NumberFilter(field_name='cost_price', lookup_expr='gte')
    cost_price_max = django_filters.NumberFilter(field_name='cost_price', lookup_expr='lte')
    selling_price_min = django_filters.NumberFilter(field_name='selling_price', lookup_expr='gte')
    selling_price_max = django_filters.NumberFilter(field_name='selling_price', lookup_expr='lte')
    quantity_min = django_filters.NumberFilter(field_name='quantity', lookup_expr='gte')
    quantity_max = django_filters.NumberFilter(field_name='quantity', lookup_expr='lte')

    # Custom filters
    low_stock = django_filters.BooleanFilter(method='filter_low_stock')
    expiry_soon = django_filters.BooleanFilter(method='filter_expiry_soon')
    expiry_in_next_7_days = django_filters.BooleanFilter(method='filter_expiry_in_next_7_days')
    has_batch_expiring_tomorrow = django_filters.BooleanFilter(method='filter_batch_expiring_tomorrow')

    class Meta:
        model = Product
        fields = []

    def filter_low_stock(self, queryset, name, value):
        if value:
            return queryset.annotate(
                total_quantity=Sum('batches__quantity')
            ).filter(total_quantity__lte=F('low_stock_level'))
        return queryset

    def filter_expiry_soon(self, queryset, name, value):
        # Filter products with batches expiring soon (today or tomorrow)
        if value:
            tomorrow = date.today() + timedelta(days=1)
            return queryset.filter(
                Exists(ProductBatch.objects.filter(
                    product=OuterRef('pk'),
                    expiry_date__lte=tomorrow,
                    expiry_date__gte=date.today(),
                    is_expired_handled=False,
                    quantity__gt=0
                ))
            )
        return queryset

    def filter_expiry_in_next_7_days(self, queryset, name, value):
        # Filter products with batches expiring in the next 7 days
        if value:
            today = date.today()
            next_7 = today + timedelta(days=7)
            return queryset.filter(
                Exists(ProductBatch.objects.filter(
                    product=OuterRef('pk'),
                    expiry_date__range=(today, next_7),
                    is_expired_handled=False,
                    quantity__gt=0
                ))
            )
        return queryset

    def filter_batch_expiring_tomorrow(self, queryset, name, value):
        if value:
            tomorrow = date.today() + timedelta(days=1)
            return queryset.filter(Exists(ProductBatch.objects.filter(product=OuterRef('pk'), expiry_date=tomorrow)))
        return queryset

class ProductBatchFilter(django_filters.FilterSet):
    expires_tomorrow = django_filters.BooleanFilter(method='filter_expires_tomorrow')
    expires_next_7_days = django_filters.BooleanFilter(method='filter_next_7_days')

    class Meta:
        model = ProductBatch
        fields = []

    def filter_expires_tomorrow(self, queryset, name, value):
        if value:
            tomorrow = date.today() + timedelta(days=1)
            return queryset.filter(expiry_date=tomorrow)
        return queryset

    def filter_next_7_days(self, queryset, name, value):
        if value:
            today = date.today()
            next_week = today + timedelta(days=7)
            return queryset.filter(expiry_date__range=(today, next_week))
        return queryset

