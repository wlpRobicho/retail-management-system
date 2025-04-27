from rest_framework import viewsets, mixins, status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from .filters import SalesTransactionFilter
from .models import SalesTransaction
from .serializers import SalesTransactionCreateSerializer, SalesTransactionListSerializer
from rest_framework.views import APIView
from django.http import HttpResponse, FileResponse, Http404, JsonResponse
from rest_framework.decorators import action, api_view, permission_classes
from .utils import generate_receipt_pdf  # Utility function for generating PDF receipts
from .analytics import get_analytics  # Import the analytics logic
from .models import DiscountCode

# ViewSet for managing sales transactions
class SalesTransactionViewSet(mixins.CreateModelMixin,
                               mixins.ListModelMixin,
                               viewsets.GenericViewSet):
    permission_classes = [IsAuthenticated]  # Restrict access to authenticated users
    queryset = SalesTransaction.objects.select_related('cashier').prefetch_related('items__product')  # Optimize queries
    serializer_class = SalesTransactionListSerializer  # Default serializer for listing transactions
    filter_backends = [DjangoFilterBackend]  # Enable filtering
    filterset_class = SalesTransactionFilter  # Use custom filter class for filtering transactions

    def get_serializer_class(self):
        # Use a different serializer for creating transactions
        if self.action == 'create':
            return SalesTransactionCreateSerializer
        return SalesTransactionListSerializer

    def get_queryset(self):
        # Return all transactions ordered by timestamp (newest first)
        return SalesTransaction.objects.all().order_by('-timestamp')

    def perform_create(self, serializer):
        # Save the transaction using the serializer
        return serializer.save()

    def create(self, request):
        # Handle the creation of a new sales transaction
        serializer = SalesTransactionCreateSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)  # Validate the input data
        result = serializer.save()  # Save the transaction and return the custom dictionary
        return Response(result, status=status.HTTP_201_CREATED)

# APIView for downloading a receipt as a PDF
class SalesReceiptView(APIView):
    permission_classes = [IsAuthenticated]  # Restrict access to authenticated users

    def get(self, request, pk):
        try:
            # Fetch the sales transaction with related cashier, items, and batches
            sale = SalesTransaction.objects.select_related(
                'cashier'
            ).prefetch_related(
                'items__product', 'items__batch'  # Prefetch related product and batch for items
            ).get(pk=pk)
        except SalesTransaction.DoesNotExist:
            # Return a 404 error if the transaction is not found
            return JsonResponse({"error": "Transaction not found."}, status=404)

        try:
            # Generate the receipt PDF
            buffer = generate_receipt_pdf(sale)
            if not buffer:
                raise ValueError("PDF generation failed")

            # Return the PDF as a downloadable file
            buffer.seek(0)
            return FileResponse(
                buffer,
                as_attachment=True,
                filename=f"receipt_{sale.id}.pdf",
                content_type='application/pdf'
            )
        except Exception as e:
            # Handle any errors during receipt generation
            return JsonResponse({"error": f"Receipt generation failed: {str(e)}"}, status=500)

# APIView for creating a sales transaction (alternative to the ViewSet)
class SalesTransactionCreateView(APIView):
    def post(self, request, *args, **kwargs):
        # Handle the creation of a new sales transaction
        serializer = SalesTransactionCreateSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)  # Validate the input data
        transaction = serializer.save()  # Save the transaction and return the custom dictionary
        return Response(transaction, status=status.HTTP_201_CREATED)

# APIView for retrieving sales analytics
class SalesAnalyticsView(APIView):
    permission_classes = [IsAuthenticated]  # Restrict access to authenticated users

    def get(self, request):
        # Fetch analytics data using the helper function
        data = get_analytics()
        return Response(data)  # Return the analytics data as a JSON response

def calculate_cart_total(cart_items):
    # Calculate the total price of items in the cart
    total = 0
    for item in cart_items:
        batch = item.batch
        total += batch.effective_price * item.quantity  # Use effective price from the batch
    return total

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def validate_discount_code(request):
    code = request.query_params.get('code')
    if not code:
        return Response({"error": "No discount code provided."}, status=400)

    try:
        discount = DiscountCode.objects.get(code=code, is_active=True)
        return Response({
            "valid": True,
            "code": discount.code,
            "type": discount.type,
            "message": "Discount code is valid."
        })
    except DiscountCode.DoesNotExist:
        return Response({
            "valid": False,
            "message": "Invalid or already used discount code."
        }, status=404)
