from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import CategoryViewSet, ProductViewSet, ProductBatchViewSet, lookup_product_by_barcode

router = DefaultRouter()
router.register(r'categories', CategoryViewSet, basename='category')
router.register(r'products', ProductViewSet, basename='product')
router.register(r'batches', ProductBatchViewSet, basename='productbatch')

urlpatterns = [
    path('', include(router.urls)),
    path('lookup/', lookup_product_by_barcode, name='lookup-product-barcode'),
]
