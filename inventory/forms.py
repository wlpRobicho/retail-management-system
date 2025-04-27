from django import forms
from .models import Product, ProductBatch, LossLog

class ProductForm(forms.ModelForm):
    # Form for validating and managing Product model data
    class Meta:
        model = Product
        fields = '__all__'  # Include all fields from the Product model

    def clean_cost_price(self):
        # Validate that cost price is non-negative
        cost_price = self.cleaned_data.get('cost_price')
        if cost_price is None or cost_price < 0:
            raise forms.ValidationError("Cost price must be a non-negative number.")
        return cost_price

    def clean_selling_price(self):
        # Validate that selling price is non-negative
        selling_price = self.cleaned_data.get('selling_price')
        if selling_price is None or selling_price < 0:
            raise forms.ValidationError("Selling price must be a non-negative number.")
        return selling_price

    def clean(self):
        # Validate that selling price is not lower than cost price
        try:
            cleaned_data = super().clean()
            cost_price = cleaned_data.get('cost_price')
            selling_price = cleaned_data.get('selling_price')

            if cost_price and selling_price and selling_price < cost_price:
                raise forms.ValidationError("Selling price cannot be lower than cost price.")
            return cleaned_data
        except Exception as e:
            raise forms.ValidationError(f"Unexpected error during validation: {str(e)}")

class ProductBatchForm(forms.ModelForm):
    # Form for validating and managing ProductBatch model data
    class Meta:
        model = ProductBatch
        fields = '__all__'  # Include all fields from the ProductBatch model

    def __init__(self, *args, **kwargs):
        # Limit product dropdown to active products only
        super().__init__(*args, **kwargs)
        self.fields['product'].queryset = Product.objects.filter(is_active=True)

    def clean_quantity(self):
        # Validate that batch quantity is non-negative
        quantity = self.cleaned_data.get('quantity')
        if quantity is None or quantity < 0:
            raise forms.ValidationError("Batch quantity must be a non-negative number.")
        return quantity

    def clean_expiry_date(self):
        # Validate that expiry date is not in the past
        expiry_date = self.cleaned_data.get('expiry_date')
        if expiry_date and expiry_date < date.today():
            raise forms.ValidationError("Expiry date cannot be in the past.")
        return expiry_date

class LossLogForm(forms.ModelForm):
    # Form for validating and managing LossLog model data
    class Meta:
        model = LossLog
        fields = '__all__'  # Include all fields from the LossLog model

    def clean(self):
        # Validate that loss quantity is within the available batch quantity
        try:
            cleaned_data = super().clean()
            batch = cleaned_data.get('batch')
            quantity_lost = cleaned_data.get('quantity_lost')

            if batch and quantity_lost:
                if quantity_lost < 0:
                    raise forms.ValidationError("Loss quantity cannot be negative.")
                if quantity_lost > batch.quantity:
                    raise forms.ValidationError(
                        f"Loss quantity ({quantity_lost}) exceeds available quantity in batch ({batch.quantity})."
                    )
            return cleaned_data
        except Exception as e:
            raise forms.ValidationError(f"Unexpected error during validation: {str(e)}")
