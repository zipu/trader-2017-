from django import forms

class EntryForm(forms.Form):
    entry_date = forms.DateTimeField(input_formats=['%Y-%m-%dT%H:%M:%S'])
    product_name = forms.CharField(max_length=50)
    position = forms.IntegerField() #포지션
    contracts = forms.IntegerField(min_value=1) #계약수
    entry_price = forms.DecimalField(max_digits=20, decimal_places=7) #진입가격
    loss_cut_in_ticks = forms.IntegerField()
    strategy = forms.IntegerField()
