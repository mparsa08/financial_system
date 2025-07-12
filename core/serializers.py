from rest_framework import serializers
from .models import User, Currency, ChartOfAccount, JournalEntry, JournalEntryLine, TradingAccount, Asset, AssetLot, Trade
from django.db.models import Sum


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = '__all__'

class CurrencySerializer(serializers.ModelSerializer):
    class Meta:
        model = Currency
        fields = ['id', 'code', 'name']

class ChartOfAccountSerializer(serializers.ModelSerializer):
    class Meta:
        model = ChartOfAccount
        fields = ['id', 'account_number', 'account_name', 'account_type', 'parent_account', 'is_active']

class JournalEntrySerializer(serializers.ModelSerializer):
    class Meta:
        model = JournalEntry
        fields = ['id', 'entry_date', 'description', 'posted_by']

class JournalEntryLineSerializer(serializers.ModelSerializer):
    class Meta:
        model = JournalEntryLine
        fields = ['id', 'journal_entry', 'account', 'debit_amount', 'credit_amount']

class TradingAccountSerializer(serializers.ModelSerializer):
    class Meta:
        model = TradingAccount
        fields = ['id', 'name', 'user', 'account_type', 'account_purpose']

class AssetSerializer(serializers.ModelSerializer):
    class Meta:
        model = Asset
        fields = ['id', 'symbol', 'name', 'asset_type', 'trading_account']

class AssetLotSerializer(serializers.ModelSerializer):
    class Meta:
        model = AssetLot
        fields = '__all__' # یا فیلدهای مورد نظر شما

    def validate(self, data):
        """
        این متد برای اعتبارسنجی در سطح کل آبجکت استفاده می‌شود.
        ما بررسی می‌کنیم که رابطه بین فیلدها منطقی باشد.
        """
        # 'asset' را از دیکشنری داده‌های معتبر شده استخراج می‌کنیم
        asset = data.get('asset')

        # اگر دارایی انتخاب شده بود و نوع آن SPOT نبود، خطا ایجاد کن
        if asset and asset.asset_type != Asset.SPOT:
            # این خطا یک پاسخ 400 Bad Request به کاربر API برمی‌گرداند
            raise serializers.ValidationError({
                "asset": "این دارایی از نوع SPOT نیست و نمی‌تواند در کیف پول قرار بگیرد."
            })
        
        # در صورت موفقیت‌آمیز بودن تمام اعتبارسنجی‌ها، حتماً داده‌ها را برگردان
        return data

class TradeSerializer(serializers.ModelSerializer):
    """
    سریالایزر برای مدل یکپارچه Trade.
    هم برای نمایش و هم برای ایجاد (باز کردن) معاملات استفاده می‌شود.
    """
    # نمایش اطلاعات مربوط به آبجکت‌های متصل برای خوانایی بهتر در API
    asset_details = serializers.StringRelatedField(source='asset', read_only=True)
    trading_account_details = serializers.StringRelatedField(source='trading_account', read_only=True)

    class Meta:
        model = Trade
        # تمام فیلدها را در بر می‌گیرد
        fields = '__all__'
        # فیلدهایی که هنگام باز کردن معامله نیازی به ارسال آنها نیست
        # این فیلدها هنگام بستن معامله پر می‌شوند
        read_only_fields = (
            'status', 'exit_price', 'exit_date', 'gross_profit_or_loss',
            'broker_commission', 'trader_commission', 'commission_recipient'
        )


# یک سریالایزر ساده برای نمایش موجودی کیف پول اسپات
class AssetLotBalanceSerializer(serializers.ModelSerializer):
    asset_name = serializers.CharField(source='asset.name')
    asset_symbol = serializers.CharField(source='asset.symbol')

    class Meta:
        model = AssetLot
        fields = ['asset_name', 'asset_symbol', 'quantity']


class TradingAccountDetailSerializer(serializers.ModelSerializer):
    """
    سریالایزری برای نمایش جزئیات کامل یک حساب معاملاتی به همراه موجودی‌ها.
    """
    account_balances = serializers.SerializerMethodField()

    class Meta:
        model = TradingAccount
        fields = ['id', 'name', 'account_type', 'account_purpose', 'user', 'account_balances']

    def get_account_balances(self, obj):
        """
        این متد موجودی‌های نقد و اسپات را محاسبه و برمی‌گرداند.
        'obj' در اینجا یک نمونه (instance) از مدل TradingAccount است.
        """
        # --- محاسبه موجودی نقد از روی سرفصل حسابداری ---
        cash_balance = 0
        try:
            cash_account = ChartOfAccount.objects.get(trading_account=obj, account_number='1010')
            # جمع کل بدهکارها و بستانکارهای حساب نقد
            balance_agg = JournalEntryLine.objects.filter(account=cash_account).aggregate(
                total_debit=Sum('debit_amount'),
                total_credit=Sum('credit_amount')
            )
            total_debit = balance_agg['total_debit'] or 0
            total_credit = balance_agg['total_credit'] or 0
            cash_balance = total_debit - total_credit
        except ChartOfAccount.DoesNotExist:
            cash_balance = 0

        # --- دریافت موجودی دارایی‌های اسپات از کیف پول ---
        spot_assets_qs = AssetLot.objects.filter(
            trading_account=obj,
            remaining_quantity__gt=0
        ).values(
            'asset__symbol', 'asset__name'
        ).annotate(
            total_quantity=Sum('remaining_quantity')
        ).order_by('asset__symbol')

        spot_assets_data = list(spot_assets_qs)

        return {
            'cash_balance': cash_balance,
            'spot_assets': spot_assets_data
        }
