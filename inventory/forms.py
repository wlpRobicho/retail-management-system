from django import forms
from .models import Product, ProductBatch, LossLog

class ProductForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = '__all__'

    def clean_cost_price(self):
        cost_price = self.cleaned_data.get('cost_price')
        if cost_price is None or cost_price < 0:
            raise forms.ValidationError("Cost price must be a non-negative number.")
        return cost_price

    def clean_selling_price(self):
        selling_price = self.cleaned_data.get('selling_price')
        if selling_price is None or selling_price < 0:
            raise forms.ValidationError("Selling price must be a non-negative number.")
        return selling_price

    def clean(self):
        cleaned_data = super().clean()
        cost_price = cleaned_data.get('cost_price')
        selling_price = cleaned_data.get('selling_price')

        if cost_price and selling_price and selling_price < cost_price:
            raise forms.ValidationError("Selling price cannot be lower than cost price.")
        return cleaned_data


class ProductBatchForm(forms.ModelForm):
    class Meta:
        model = ProductBatch
        fields = '__all__'

    def clean_quantity(self):
        quantity = self.cleaned_data.get('quantity')
        if quantity is None or quantity < 0:
            raise forms.ValidationError("Batch quantity must be a non-negative number.")
        return quantity

    def clean_expiry_date(self):
        expiry_date = self.cleaned_data.get('expiry_date')
        if expiry_date and expiry_date < date.today():
            raise forms.ValidationError("Expiry date cannot be in the past.")
        return expiry_date


class LossLogForm(forms.ModelForm):
    class Meta:
        model = LossLog
        fields = '__all__'

    def clean(self):
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
