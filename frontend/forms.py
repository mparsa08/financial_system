from django import forms
from core.models import TradingAccount, ClosedTradesLog, Asset
from django.contrib.auth import get_user_model

User = get_user_model()

class TradingAccountForm(forms.ModelForm):
    class Meta:
        model = TradingAccount
        fields = ['name', 'account_type', 'account_purpose']
        labels = {
            'name': 'نام حساب',
            'account_type': 'نوع بازار (کریپتو/فارکس)',
            'account_purpose': 'هدف حساب (اسپات/فیوچرز)',
        }
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'account_type': forms.Select(attrs={'class': 'form-control'}),
            'account_purpose': forms.Select(attrs={'class': 'form-control'}),
        }

class ClosedTradeForm(forms.ModelForm):
    class Meta:
        model = ClosedTradesLog
        fields = [
            'trading_account',
            'asset',
            'trade_date',
            'net_profit_or_loss',
            'broker_commission',
            'trader_commission',
            'commission_recipient',
        ]
        widgets = {
            'trading_account': forms.Select(attrs={'class': 'form-control'}),
            'asset': forms.Select(attrs={'class': 'form-control'}),
            'trade_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'net_profit_or_loss': forms.NumberInput(attrs={'class': 'form-control'}),
            'broker_commission': forms.NumberInput(attrs={'class': 'form-control'}),
            'trader_commission': forms.NumberInput(attrs={'class': 'form-control'}),
            'commission_recipient': forms.Select(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['asset'].queryset = Asset.objects.filter(asset_type=Asset.DERIVATIVE)
        self.fields['trading_account'].queryset = TradingAccount.objects.filter(account_purpose=TradingAccount.FUTURES)
        self.fields['commission_recipient'].queryset = User.objects.filter(role='Trader')
