from rest_framework import viewsets, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from .models import Category, Product, StockUpdateLog, RestockLog, ProductBatch
from .serializers import CategorySerializer, ProductSerializer, ProductBatchSerializer
from django.db.models import F, Sum, Min, FloatField
from django_filters.rest_framework import DjangoFilterBackend
from .filters import ProductFilter, ProductBatchFilter
from django.http import HttpResponse
import csv
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import PermissionDenied, APIException
from datetime import date, timedelta
from django.utils.timezone import now

class IsManager(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.position == 'manager'


class CategoryViewSet(viewsets.ModelViewSet):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [IsAuthenticated(), IsManager()]
        return [IsAuthenticated()]

    def create(self, request, *args, **kwargs):
        try:
            is_many = isinstance(request.data, list)
            serializer = self.get_serializer(data=request.data, many=is_many)
            serializer.is_valid(raise_exception=True)
            self.perform_create(serializer)
            return Response(serializer.data, status=201)
        except Exception as e:
            raise APIException(f"Error creating category: {str(e)}")


class ProductViewSet(viewsets.ModelViewSet):
    serializer_class = ProductSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_class = ProductFilter

    def get_queryset(self):
        return Product.objects.filter(is_active=True).order_by('-updated_at')

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [IsAuthenticated(), IsManager()]
        return [IsAuthenticated()]

    def create(self, request, *args, **kwargs):
        try:
            serializer = self.get_serializer(data=request.data)
            serializer.is_valid(raise_exception=True)

            # Validate cost price, selling price, and quantity
            if serializer.validated_data['cost_price'] < 0:
                raise APIException("Cost price cannot be negative.")
            if serializer.validated_data['selling_price'] < 0:
                raise APIException("Selling price cannot be negative.")
            if serializer.validated_data['selling_price'] < serializer.validated_data['cost_price']:
                raise APIException("Selling price cannot be lower than cost price.")

            # Check for duplicate barcodes
            barcodes = [item['barcode'] for item in serializer.validated_data]
            if Product.objects.filter(barcode__in=barcodes).exists():
                raise APIException("A product with the same barcode already exists.")

            products = serializer.save()

            if not isinstance(products, list):
                products = [products]

            for product in products:
                StockUpdateLog.objects.create(
                    product=product,
                    updated_by=self.request.user,
                    change_type='created',
                    quantity_before=0,
                    quantity_after=product.quantity,
                )

            return Response(self.get_serializer(products, many=True).data, status=201)
        except Exception as e:
            raise APIException(f"Error creating product: {str(e)}")

    def perform_create(self, serializer):
        if not self.request.user.is_authenticated:
            raise PermissionDenied("Authentication required to create a product.")
        try:
            product = serializer.save()
            StockUpdateLog.objects.create(
                product=product,
                updated_by=self.request.user,
                change_type='created',
                quantity_before=0,
                quantity_after=product.quantity,
            )
        except Exception as e:
            raise PermissionDenied(f"Error during product creation: {str(e)}")

    def perform_update(self, serializer):
        product = self.get_object()
        old_values = {
            'category': product.category,
            'cost_price': product.cost_price,
            'selling_price': product.selling_price,
            'has_barcode': product.has_barcode,
            'price_by_weight': product.price_by_weight,
        }

        new_instance = serializer.save()
        user = self.request.user

        # Check for changes
        for field, old_value in old_values.items():
            new_value = getattr(new_instance, field)
            if old_value != new_value:
                StockUpdateLog.objects.create(
                    product=new_instance,
                    updated_by=user,
                    change_type="product updated",
                    field_changed=field,
                    note=f"{field} changed from {old_value} to {new_value}",
                )

        # Quantity logic still applies
        old_quantity = product.quantity
        if old_quantity != new_instance.quantity:
            StockUpdateLog.objects.create(
                product=new_instance,
                updated_by=self.request.user,
                change_type='manual update',
                quantity_before=old_quantity,
                quantity_after=new_instance.quantity,
            )

    def perform_destroy(self, instance):
        try:
            instance.is_active = False  # soft delete
            instance.save()
            StockUpdateLog.objects.create(
                product=instance,
                updated_by=self.request.user,
                change_type='deleted',
                quantity_before=instance.quantity,
                quantity_after=0,
            )
        except Exception as e:
            raise APIException(f"Error deleting product: {str(e)}")

    @action(detail=False, methods=['get'])
    def low_stock(self, request):
        try:
            low_stock_items = Product.objects.annotate(
                total_quantity=Sum('batches__quantity')
            ).filter(total_quantity__lte=F('low_stock_level'))
            serializer = self.get_serializer(low_stock_items, many=True)
            return Response(serializer.data)
        except Exception as e:
            raise APIException(f"Error fetching low stock products: {str(e)}")

    @action(detail=False, methods=['get'])
    def reorder_soon(self, request):
        try:
            soon = Product.objects.filter(
                quantity__gt=F('low_stock_level'),
                quantity__lte=F('low_stock_level') + 3,
                is_active=True
            )
            serializer = self.get_serializer(soon, many=True)
            return Response(serializer.data)
        except Exception as e:
            return Response({'error': str(e)}, status=400)

    @action(detail=False, methods=['get'])
    def export_csv(self, request):
        try:
            products = self.get_queryset()

            response = HttpResponse(content_type='text/csv')
            response['Content-Disposition'] = 'attachment; filename="inventory.csv"'

            writer = csv.writer(response)
            writer.writerow(['Name', 'Barcode', 'Category', 'Cost Price', 'Selling Price', 'Quantity', 'Expiry Date'])

            for p in products:
                writer.writerow([
                    p.name,
                    p.barcode,
                    p.category.name if p.category else '',
                    p.cost_price,
                    p.selling_price,
                    p.quantity,
                    p.expiry_date or ''
                ])

            return response
        except Exception as e:
            raise APIException(f"Error exporting inventory CSV: {str(e)}")

    @action(detail=False, methods=['get'])
    def export_expiring_tomorrow(self, request):
        tomorrow = date.today() + timedelta(days=1)
        products = Product.objects.filter(batches__expiry_date=tomorrow).distinct()

        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="products_expiring_tomorrow.csv"'

        writer = csv.writer(response)
        writer.writerow(['Name', 'Barcode', 'Category', 'Batch Quantity', 'Nearest Expiry Date'])

        for product in products:
            writer.writerow([
                product.name,
                product.barcode,
                product.category.name if product.category else '',
                product.total_quantity,
                product.nearest_expiry_date
            ])

        return response

    @action(detail=False, methods=['get'])
    def total_stock_value(self, request):
        try:
            total_value = Product.objects.annotate(
                total_quantity=Sum('batches__quantity')
            ).aggregate(
                total_stock_value=Sum(F('selling_price') * F('total_quantity'), output_field=FloatField())
            )['total_stock_value']

            return Response({'total_stock_value': total_value or 0}, status=200)
        except Exception as e:
            raise APIException(f"Error calculating total stock value: {str(e)}")

    @action(detail=False, methods=['get'])
    def dashboard_summary(self, request):
        try:
            today = now().date()
            tomorrow = today + timedelta(days=1)
            next_7_days = today + timedelta(days=7)

            products = Product.objects.filter(is_active=True)
            total_products = products.count()

            # Inventory value
            total_inventory_value = sum([
                batch.product.cost_price * batch.quantity
                for batch in ProductBatch.objects.select_related('product').all()
            ])

            # Low stock count
            low_stock_count = products.filter(
                batches__quantity__lte=F('low_stock_level')
            ).distinct().count()

            # Expiring soon count
            expiring_soon_count = ProductBatch.objects.filter(
                expiry_date__range=(today, next_7_days)
            ).count()

            return Response({
                "total_products": total_products,
                "total_inventory_value": total_inventory_value,
                "low_stock_products": low_stock_count,
                "expiring_soon_batches": expiring_soon_count,
            }, status=200)
        except Exception as e:
            raise APIException(f"Error fetching dashboard summary: {str(e)}")


class ProductBatchViewSet(viewsets.ModelViewSet):
    queryset = ProductBatch.objects.select_related('product').all()
    serializer_class = ProductBatchSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_class = ProductBatchFilter

    def create(self, request, *args, **kwargs):
        try:
            serializer = self.get_serializer(data=request.data)
            serializer.is_valid(raise_exception=True)

            # Validate batch quantity
            if serializer.validated_data['quantity'] < 0:
                raise APIException("Batch quantity cannot be negative.")

            # Check if the product is inactive
            product = serializer.validated_data['product']
            if not product.is_active:
                raise APIException("Cannot create a batch for an inactive product.")

            batch = serializer.save()
            return Response(self.get_serializer(batch).data, status=201)
        except Exception as e:
            raise APIException(f"Error creating batch: {str(e)}")

    @action(detail=False, methods=['get'])
    def export_expiring_tomorrow(self, request):
        try:
            tomorrow = date.today() + timedelta(days=1)
            batches = ProductBatch.objects.filter(expiry_date=tomorrow).exclude(expiry_date__isnull=True)

            response = HttpResponse(content_type='text/csv')
            response['Content-Disposition'] = 'attachment; filename="expiring_batches_tomorrow.csv"'

            writer = csv.writer(response)
            writer.writerow(['Product Name', 'Barcode', 'Category', 'Batch Quantity', 'Expiry Date'])

            for batch in batches:
                writer.writerow([
                    batch.product.name,
                    batch.product.barcode,
                    batch.product.category.name if batch.product.category else '',
                    batch.quantity,
                    batch.expiry_date or "No Expiry",
                ])

            return response
        except Exception as e:
            raise APIException(f"Error exporting expiring batches CSV: {str(e)}")
