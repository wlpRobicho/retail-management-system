import django_filters
from .models import SalesTransaction

class SalesTransactionFilter(django_filters.FilterSet):
    start_date = django_filters.DateFilter(field_name='timestamp', lookup_expr='gte')
    end_date = django_filters.DateFilter(field_name='timestamp', lookup_expr='lte')
    cashier_id = django_filters.NumberFilter(field_name='cashier__id')

    class Meta:
        model = SalesTransaction
        fields = ['start_date', 'end_date', 'cashier_id']
