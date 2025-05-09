from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import SalesTransactionViewSet, SalesReceiptView, SalesAnalyticsView, validate_discount_code  # Import views for handling sales transactions, receipts, and analytics

# Initialize a DRF router for automatically generating routes for viewsets
router = DefaultRouter()
router.register(r'sales', SalesTransactionViewSet, basename='sales')  # Register the SalesTransactionViewSet

# Define URL patterns for the sales app
urlpatterns = [
    # Custom route for downloading a receipt as a PDF
    path('receipt/<int:pk>/', SalesReceiptView.as_view(), name='sales-receipt'),

    # Include routes generated by the DRF router
    path('', include(router.urls)),

    # Analytics route for sales analytics
    path('analytics/', SalesAnalyticsView.as_view(), name='sales-analytics'),

    path('discounts/validate/', validate_discount_code, name='validate-discount'),  # Add route for discount validation
]
