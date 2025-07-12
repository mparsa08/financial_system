from django import forms
from core.models import Trade, TradingAccount, Asset, User
from django.contrib.auth.forms import UserCreationForm

class TradingAccountForm(forms.ModelForm):
    class Meta:
        model = TradingAccount
        fields = ['name', 'account_type', 'account_purpose']

class OpenTradeForm(forms.ModelForm):
    class Meta:
        model = Trade
        fields = ['trading_account', 'asset', 'position_side', 'quantity', 'entry_price']

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        if user:
            self.fields['trading_account'].queryset = TradingAccount.objects.filter(user=user)
            self.fields['asset'].queryset = Asset.objects.filter(asset_type=Asset.DERIVATIVE)

class CloseTradeForm(forms.Form):
    gross_profit_or_loss = forms.DecimalField(max_digits=10, decimal_places=2)
    broker_commission = forms.DecimalField(max_digits=10, decimal_places=2, required=False)
    trader_commission = forms.DecimalField(max_digits=10, decimal_places=2, required=False)
    commission_recipient = forms.ModelChoiceField(queryset=User.objects.filter(role='Trader'), required=False)
    exit_description = forms.CharField(widget=forms.Textarea, required=False)

class DirectClosedTradeForm(forms.ModelForm):
    class Meta:
        model = Trade
        fields = [
            'trading_account', 'asset', 'position_side', 'quantity',
            'entry_price', 'exit_price', 'exit_date', 'gross_profit_or_loss',
            'broker_commission', 'trader_commission', 'commission_recipient'
        ]
        widgets = {
            'exit_date': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        if user:
            self.fields['trading_account'].queryset = TradingAccount.objects.filter(user=user)
            self.fields['asset'].queryset = Asset.objects.filter(asset_type=Asset.DERIVATIVE)
            self.fields['commission_recipient'].queryset = User.objects.filter(role='Trader')

class CustomUserCreationForm(UserCreationForm):
    class Meta(UserCreationForm.Meta):
        model = User
        fields = UserCreationForm.Meta.fields + ('email', 'role',)
