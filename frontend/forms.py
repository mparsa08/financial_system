from django import forms
from core.models import TradingAccount, Trade, Asset
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

class DirectClosedTradeForm(forms.ModelForm):
    """
    این فرم تمام اطلاعات یک معامله بسته شده را به صورت یکجا دریافت می‌کند.
    """
    class Meta:
        model = Trade
        # تمام فیلدهای لازم برای باز کردن و بستن
        fields = [
            'trading_account', 'asset', 'position_side', 'quantity', 
            'entry_price', 'exit_price', 'exit_date', 'gross_profit_or_loss',
            'broker_commission', 'trader_commission', 'commission_recipient'
        ]
        widgets = {
            'exit_date': forms.DateInput(attrs={'type': 'date'}),
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        if user:
            self.fields['trading_account'].queryset = TradingAccount.objects.filter(
                user=user, account_purpose=TradingAccount.FUTURES
            )
            self.fields['commission_recipient'].queryset = User.objects.filter(role='Trader')
        self.fields['asset'].queryset = Asset.objects.filter(asset_type=Asset.DERIVATIVE)

class CloseTradeForm(forms.Form):
    """
    این فرم اطلاعات لازم برای بستن یک معامله را از کاربر دریافت می‌کند.
    """
    gross_profit_or_loss = forms.DecimalField(label="سود یا زیان ناخالص", max_digits=10, decimal_places=2)
    broker_commission = forms.DecimalField(label="کمیسیون بروکر", initial=0.0, required=False)
    trader_commission = forms.DecimalField(label="کمیسیون تریدر", initial=0.0, required=False)
    commission_recipient = forms.ModelChoiceField(
        queryset=User.objects.filter(role='Trader'),
        label="دریافت کننده کمیسیون",
        required=False
    )
    exit_description = forms.CharField(label="توضیحات خروج", widget=forms.Textarea, required=False)
    
class OpenTradeForm(forms.ModelForm):
    """
    این فرم فقط برای دریافت اطلاعات لازم جهت باز کردن یک معامله جدید استفاده می‌شود.
    """
    class Meta:
        model = Trade
        # فقط فیلدهای مربوط به باز کردن معامله
        fields = [
            'trading_account',
            'asset',
            'position_side',
            'quantity',
            'entry_price',
        ]
        labels = {
            'trading_account': 'حساب معاملاتی',
            'asset': 'دارایی',
            'position_side': 'نوع پوزیشن (لانگ/شرکت)',
            'quantity': 'مقدار',
            'entry_price': 'قیمت ورود',
        }

    def __init__(self, *args, **kwargs):
        # کاربر را از ویو دریافت می‌کنیم تا حساب‌های معاملاتی را فیلتر کنیم
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        self.fields['quantity'].required = True
        self.fields['entry_price'].required = True
        
        # فیلتر کردن گزینه‌ها
        if user:
            self.fields['trading_account'].queryset = TradingAccount.objects.filter(
                user=user, account_purpose=TradingAccount.FUTURES
            )
        self.fields['asset'].queryset = Asset.objects.filter(asset_type=Asset.DERIVATIVE)
