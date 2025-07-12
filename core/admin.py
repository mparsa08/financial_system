from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.translation import gettext_lazy as _
from .models import User, Currency, ChartOfAccount, JournalEntry, JournalEntryLine, TradingAccount, Asset, AssetLot  , Trade
from django import forms
from django.shortcuts import render
from django.http import HttpResponseRedirect
from .services import make_deposit

# یک فرم ساده برای دریافت مبلغ
class DepositForm(forms.Form):
    amount = forms.DecimalField(label="مبلغ واریز", max_digits=10, decimal_places=2)
    description = forms.CharField(label="توضیحات", required=False)

class CustomUserAdmin(BaseUserAdmin):
    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        (_('Personal info'), {'fields': ('first_name', 'last_name', 'email')}),
        (_('Permissions'), {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        (_('Important dates'), {'fields': ('last_login', 'date_joined')}),
        (_('Role'), {'fields': ('role',)}),
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('username', 'password1', 'password2', 'role'),
        }),
    )


# ثبت مدل‌ها برای پنل مدیریت
admin.site.register(User, CustomUserAdmin)
admin.site.register(Currency)
admin.site.register(ChartOfAccount)
admin.site.register(JournalEntry)
admin.site.register(JournalEntryLine)



@admin.register(Trade)
class TradeAdmin(admin.ModelAdmin):
    # فیلدهایی که در لیست نمایش داده می‌شوند
    list_display = (
        'id', 
        'status', 
        'position_side', 
        'asset', 
        'trading_account', 
        'entry_date', 
        'exit_date', 
        'gross_profit_or_loss'
    )
    # فیلترهایی که در سایدبار نمایش داده می‌شوند
    list_filter = ('status', 'position_side', 'trading_account', 'asset')
    # فیلدهایی که قابل جستجو هستند
    search_fields = ('asset__name', 'trading_account__name')
    
    # فیلدهایی که در فرم ویرایش، فقط خواندنی هستند تا از خطای انسانی جلوگیری شود
    # این فیلدها باید فقط از طریق سرویس close_trade پر شوند
    readonly_fields = (
        'exit_price', 
        'exit_date', 
        'gross_profit_or_loss', 
        'broker_commission',
        'trader_commission',
        'commission_recipient'
    )

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        """
        این متد گزینه‌های دراپ‌داون 'asset' را فیلتر می‌کند.
        """
        if db_field.name == "asset":
            # فقط دارایی‌های از نوع مشتقه را نمایش بده
            kwargs["queryset"] = Asset.objects.filter(asset_type=Asset.DERIVATIVE)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


@admin.register(Asset)
class AssetAdmin(admin.ModelAdmin):
    list_display = ('name', 'symbol', 'asset_type')
    list_filter = ('asset_type',)

@admin.register(TradingAccount)
class TradingAccountAdmin(admin.ModelAdmin):
    list_display = ('name', 'user', 'account_type')
    # اضافه کردن اکشن سفارشی
    actions = ['make_deposit_action']

    def make_deposit_action(self, request, queryset):
        # اگر کاربر فرم را ارسال کرده
        if 'apply' in request.POST:
            form = DepositForm(request.POST)
            if form.is_valid():
                amount = form.cleaned_data['amount']
                description = form.cleaned_data['description']
                # برای هر حساب معاملاتی انتخاب شده، واریز را انجام بده
                for account in queryset:
                    try:
                        make_deposit(
                            trading_account=account,
                            amount=amount,
                            description=description or 'Capital Deposit via Admin',
                            user=request.user
                        )
                    except ValueError as e:
                        self.message_user(request, f"خطا در واریز به حساب {account.name}: {e}", level='error')
                self.message_user(request, "واریز وجه برای حساب‌های انتخاب شده با موفقیت انجام شد.", level='success')
                return HttpResponseRedirect(request.get_full_path())
        # اگر کاربر اکشن را تازه انتخاب کرده، فرم را به او نشان بده
        else:
            form = DepositForm()

        return render(request, 'admin/deposit_action_form.html', {
            'title': 'واریز وجه',
            'accounts': queryset,
            'form': form,
            'path': request.get_full_path()
        })
    make_deposit_action.short_description = "واریز وجه به حساب‌های انتخاب شده"


@admin.register(AssetLot)
class AssetLotAdmin(admin.ModelAdmin):
    list_display = ('asset', 'trading_account', 'quantity', 'purchase_price_usd', 'remaining_quantity', 'purchase_date')
    list_filter = ('trading_account', 'asset')
    readonly_fields = ('purchase_date',) # فیلدهای خودکار را فقط خواندنی می‌کنیم
    search_fields = ('asset__name', 'trading_account__name')