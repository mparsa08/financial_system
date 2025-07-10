from django.db import models
from django.contrib.auth.models import AbstractUser
from django.db.models import Sum
from django.core.exceptions import ValidationError
from django.conf import settings
from django.utils import timezone
from django.utils.translation import gettext_lazy as _, get_language



ASSET = 'Asset'
LIABILITY = 'Liability'
EQUITY = 'Equity'
REVENUE = 'Revenue'    # <-- اینجا تعریف شده
EXPENSE = 'Expense'    # <-- و اینجا هم تعریف شده

ACCOUNT_TYPES = [
    (ASSET, 'Asset'),
    (LIABILITY, 'Liability'),
    (EQUITY, 'Equity'),
    (REVENUE, 'Revenue'),
    (EXPENSE, 'Expense'),
]

# مدل کاربران
class User(AbstractUser):
    USER_ROLES = [
        ('Admin', 'Admin'),
        ('Accountant', 'Accountant'),
        ('Trader', 'Trader'),
    ]
    # فیلدهای username, password, first_name, last_name, email و ... از AbstractUser ارث‌بری می‌شوند.
    # نیازی به تعریف مجدد آن‌ها نیست.
    role = models.CharField(max_length=50, choices=USER_ROLES, default='Trader')
    # full_name را می‌توانید با first_name و last_name جایگزین کنید.

    def __str__(self):
        return self.username

# مدل ارزها
class Currency(models.Model):
    code = models.CharField(max_length=10)
    name = models.CharField(max_length=50)

    def __str__(self):
        return self.code

# مدل سرفصل‌های حسابداری
class ChartOfAccount(models.Model):

    account_number = models.CharField(max_length=50)
    account_name = models.CharField(max_length=255)
    account_name_fa = models.CharField(_('Persian Account Name'), max_length=255, blank=True, null=True)
    account_type = models.CharField(max_length=50, choices=ACCOUNT_TYPES)
    parent_account = models.ForeignKey('self', null=True, blank=True, on_delete=models.SET_NULL)
    is_active = models.BooleanField(default=True)

    # فیلد جدید که سرفصل را به یک حساب معاملاتی متصل می‌کند
    trading_account = models.ForeignKey(
        'TradingAccount', 
        on_delete=models.CASCADE, 
        null=True,  # اجازه می‌دهد برخی حساب‌ها عمومی باشند (به هیچ حساب معاملاتی خاصی تعلق ندارند)
        blank=True,
        related_name='chart_of_accounts'
    )

    counterparty_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='gl_accounts',
        help_text="Connects this account to a specific user as a counterparty"
    )
    @property
    def display_name(self):
        if get_language() == "fa" and self.account_name_fa:
            return self.account_name_fa
        return self.account_name

    def __str__(self):
        # نام را کمی بهتر می‌کنیم تا مشخص باشد برای کدام حساب معاملاتی است
        if self.trading_account:
            return f"{self.account_name} ({self.trading_account.name})"
        return self.account_name

# مدل اسناد حسابداری
class JournalEntry(models.Model):
    entry_date = models.DateField()
    description = models.TextField()
    posted_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)

    def clean(self):
        # این متد قبل از ذخیره در Django Admin و ModelForms صدا زده می‌شود
        super().clean()
        if self.pk: # فقط برای سندهایی که قبلا ساخته شده و آرتیکل دارند
            lines = self.journalentryline_set.all()
            total_debit = lines.aggregate(total=Sum('debit_amount'))['total'] or 0
            total_credit = lines.aggregate(total=Sum('credit_amount'))['total'] or 0
            if total_debit != total_credit:
                raise ValidationError(f"سند حسابداری نامتوازن است! بدهکار: {total_debit}, بستانکار: {total_credit}")

    def save(self, *args, **kwargs):
        # برای اطمینان، می‌توانید این منطق را در save هم پیاده کنید.
        super().save(*args, **kwargs)
        # self.clean() # فراخوانی clean در اینجا هم می‌تواند مفید باشد
    
    def __str__(self):
        return f"Entry {self.id} on {self.entry_date}"

class JournalEntryLine(models.Model):
    journal_entry = models.ForeignKey(JournalEntry, on_delete=models.CASCADE)
    account = models.ForeignKey(ChartOfAccount, on_delete=models.PROTECT)
    debit_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    credit_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    def __str__(self):
        return f"Line {self.id} in Entry {self.journal_entry.id}"

# مدل حساب‌های معاملاتی
class TradingAccount(models.Model):
    CRYPTO = 'Crypto'
    FOREX = 'Forex'

    ACCOUNT_TYPES = [
        (CRYPTO, 'Crypto'),
        (FOREX, 'Forex'),
    ]
    
    account_type = models.CharField(max_length=50, choices=ACCOUNT_TYPES)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    name = models.CharField(max_length=100) # مثلا "Binance Account" یا "Interactive Brokers"

    # --- فیلد جدید ---
    SPOT = 'SPOT'
    FUTURES = 'FUTURES'
    ACCOUNT_PURPOSE_CHOICES = [
        (SPOT, 'Spot Trading'),
        (FUTURES, 'Futures Trading'),
    ]
    account_purpose = models.CharField(
        max_length=50,
        choices=ACCOUNT_PURPOSE_CHOICES,
        help_text="مشخص می‌کند که این حساب برای چه نوع معاملاتی استفاده می‌شود."
    )

    def __str__(self):
        return f"{self.name} ({self.get_account_type_display()} - {self.get_account_purpose_display()})"

# مدل دارایی‌ها و قراردادها
class Asset(models.Model):
    SPOT = 'SPOT'
    DERIVATIVE = 'DERIVATIVE'
    ASSET_TYPE_CHOICES = [
        (SPOT, 'Spot'),
        (DERIVATIVE, 'Derivative'),
    ]

    symbol = models.CharField(max_length=50)
    name = models.CharField(max_length=255)
    asset_type = models.CharField(max_length=50, choices=ASSET_TYPE_CHOICES)

    def __str__(self):
        return f"{self.name} ({self.get_asset_type_display()})"

# مدل موجودی کیف پول دارایی‌های اسپات

class AssetLot(models.Model):
    """
    این مدل هر دسته خرید (Lot) از یک دارایی اسپات را به صورت مجزا
    با قیمت تمام شده و مقدار باقی‌مانده آن ردیابی می‌کند.
    """
    asset = models.ForeignKey(Asset, on_delete=models.PROTECT, related_name="lots")
    trading_account = models.ForeignKey(TradingAccount, on_delete=models.CASCADE, related_name="lots")
    
    quantity = models.DecimalField(max_digits=20, decimal_places=8, help_text="مقدار اولیه خریداری شده در این دسته")
    purchase_price_usd = models.DecimalField(max_digits=20, decimal_places=8, help_text="قیمت هر واحد به دلار در لحظه خرید")
    purchase_date = models.DateTimeField(auto_now_add=True)
    
    remaining_quantity = models.DecimalField(max_digits=20, decimal_places=8, help_text="مقدار باقی‌مانده از این دسته که هنوز فروخته نشده")

    class Meta:
        ordering = ['purchase_date'] # برای اجرای صحیح FIFO

    def __str__(self):
        return f"{self.remaining_quantity}/{self.quantity} of {self.asset.symbol} bought at ${self.purchase_price_usd:.2f}"

    def save(self, *args, **kwargs):
        # هنگام ساخت یک دسته جدید، مقدار باقی‌مانده برابر با مقدار کل است
        if not self.pk:
            self.remaining_quantity = self.quantity
        super().save(*args, **kwargs)

# مدل معاملات مشتقه (Futures/CFD)
class Trade(models.Model):
    """
    یک مدل واحد برای نگهداری تمام اطلاعات یک معامله، از باز شدن تا بسته شدن.
    """
    # --- وضعیت‌های ممکن برای یک معامله ---
    OPEN = 'OPEN'
    CLOSED = 'CLOSED'
    STATUS_CHOICES = [
        (OPEN, 'Open'),
        (CLOSED, 'Closed'),
    ]

    # --- طرف معامله ---
    LONG = 'LONG'
    SHORT = 'SHORT'
    SIDE_CHOICES = [
        (LONG, 'Long'),
        (SHORT, 'Short'),
    ]
    
    # --- بخش اطلاعات اصلی ---
    trading_account = models.ForeignKey(TradingAccount, on_delete=models.CASCADE, related_name="trades")
    asset = models.ForeignKey(Asset, on_delete=models.PROTECT, limit_choices_to={'asset_type': Asset.DERIVATIVE})
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=OPEN)
    
    # --- بخش اطلاعات باز کردن معامله ---
    position_side = models.CharField(max_length=10, choices=SIDE_CHOICES)
    entry_price = models.DecimalField(max_digits=20, decimal_places=8, null=True, blank=True)
    quantity = models.DecimalField(max_digits=20, decimal_places=8, null=True, blank=True)
    entry_date = models.DateTimeField(default=timezone.now, null=True, blank=True)
    
    # --- بخش اطلاعات بستن معامله (در ابتدا خالی هستند) ---
    exit_price = models.DecimalField(max_digits=20, decimal_places=8, null=True, blank=True)
    exit_date = models.DateTimeField(null=True, blank=True)
    exit_description = models.TextField(blank=True, null=True, help_text="توضیحات مربوط به بستن معامله")

    # --- بخش اطلاعات مالی (در ابتدا خالی هستند) ---
    gross_profit_or_loss = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    broker_commission = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    trader_commission = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    commission_recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='commissioned_trades'
    )

    def __str__(self):
        return f"[{self.status}] {self.position_side} {self.quantity} {self.asset.symbol}"