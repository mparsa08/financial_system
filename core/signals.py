"""
این ماژول شامل سیگنال‌های جنگو برای خودکارسازی فرآیندهای کسب‌وکار است.
"""

from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import (
    TradingAccount, 
    ClosedTradesLog, 
    ChartOfAccount, 
    JournalEntry, 
    JournalEntryLine
)

# --- سیگنال شماره ۱: ساخت خودکار سرفصل‌های حسابداری ---

# این الگو، نقشه راه ساخت سرفصل‌های استاندارد برای هر حساب معاملاتی جدید است.
# الگوی حساب‌ها برای یک حساب معاملاتی فیوچرز
FUTURES_ACCOUNT_TEMPLATE = [
    {'account_number': '1010', 'account_name': 'Cash', 'account_type': 'Asset'},
    {'account_number': '3010', 'account_name': 'Owner Equity/Capital', 'account_type': 'Equity'},
    {'account_number': '4010', 'account_name': 'Trading Revenue', 'account_type': 'Revenue'},
    {'account_number': '5010', 'account_name': 'Trading Loss', 'account_type': 'Expense'},
    {'account_number': '5020', 'account_name': 'Commission Expense', 'account_type': 'Expense'},
]

# الگوی حساب‌ها برای یک حساب معاملاتی اسپات
SPOT_ACCOUNT_TEMPLATE = [
    {'account_number': '1010', 'account_name': 'Cash', 'account_type': 'Asset'},
    {'account_number': '1020', 'account_name': 'Spot Assets Holdings', 'account_type': 'Asset'},
    {'account_number': '3010', 'account_name': 'Owner Equity/Capital', 'account_type': 'Equity'},
    # توجه کنید که حساب‌های سود و زیان فیوچرز در اینجا وجود ندارند
]


# @receiver(post_save, sender=TradingAccount)
# def create_chart_of_accounts_for_trading_account(sender, instance, created, **kwargs):
#     """
#     این سیگنال حالا هوشمند است و بر اساس هدف حساب (account_purpose)،
#     الگوی سرفصل‌های مناسب را انتخاب و ایجاد می‌کند.
#     """
#     if created:
#         template_to_use = None
#         # انتخاب الگو بر اساس هدف حساب
#         if instance.account_purpose == TradingAccount.FUTURES:
#             template_to_use = FUTURES_ACCOUNT_TEMPLATE
#         elif instance.account_purpose == TradingAccount.SPOT:
#             template_to_use = SPOT_ACCOUNT_TEMPLATE

#         # اگر الگوی مناسبی انتخاب شده بود، سرفصل‌ها را بساز
#         if template_to_use:
#             for acc_template in template_to_use:
#                 ChartOfAccount.objects.create(
#                     trading_account=instance,
#                     account_number=acc_template['account_number'],
#                     account_name=f"{acc_template['account_name']} - {instance.name}",
#                     account_type=acc_template['account_type']
#                 )
#             print(f"'{instance.account_purpose}' chart of accounts created for {instance.name}")


# --- سیگنال شماره ۲: صدور خودکار سند حسابداری برای معاملات بسته شده ---

@receiver(post_save, sender=ClosedTradesLog)
def create_journal_entry_for_trade(sender, instance, created, **kwargs):
    """
    این سیگنال به محض ایجاد یک ClosedTradesLog جدید (created=True) فعال می‌شود.
    یک سند حسابداری متناظر برای ثبت سود/زیان و کارمزد معامله ایجاد می‌کند.
    این تابع فرض می‌کند که سرفصل‌های لازم توسط سیگنال شماره ۱ از قبل ایجاد شده‌اند.
    """
    if created:
        trade = instance
        trading_acc = trade.trading_account

        # ۱. پیدا کردن سرفصل‌های حسابداری مختص این حساب معاملاتی
        # استفاده از .get() به این دلیل است که ما مطمئن هستیم این حساب‌ها وجود دارند.
        # اگر وجود نداشته باشند، خطا می‌دهد که برای خطایابی بهتر است.
        try:
            cash_account = ChartOfAccount.objects.get(trading_account=trading_acc, account_number="1010")
            commission_expense_account = ChartOfAccount.objects.get(trading_account=trading_acc, account_number="5020")
        except ChartOfAccount.DoesNotExist as e:
            print(f"Error: A required account for {trading_acc.name} does not exist. {e}")
            return # از ادامه اجرای تابع جلوگیری می‌کند

        # ۲. ایجاد هدر سند حسابداری
        journal_entry = JournalEntry.objects.create(
            entry_date=trade.trade_date,
            description=f"Automated entry for trade #{trade.id} on asset {trade.asset.symbol}",
            posted_by=trading_acc.user
        )

        # ۳. ثبت آرتیکل‌های بدهکار و بستانکار بر اساس سود یا زیان
        if trade.net_profit_or_loss >= 0:
            # حالت سود
            profit = trade.net_profit_or_loss
            revenue_account = ChartOfAccount.objects.get(trading_account=trading_acc, account_number="4010")
            # ثبت درآمد به عنوان بستانکار
            JournalEntryLine.objects.create(
                journal_entry=journal_entry,
                account=revenue_account,
                credit_amount=profit,
                debit_amount=0
            )
        else:
            # حالت زیان
            loss = abs(trade.net_profit_or_loss)
            loss_account = ChartOfAccount.objects.get(trading_account=trading_acc, account_number="5010")
            # ثبت زیان به عنوان بدهکار
            JournalEntryLine.objects.create(
                journal_entry=journal_entry,
                account=loss_account,
                debit_amount=loss,
                credit_amount=0
            )

        # ۴. ثبت کارمزد به عنوان هزینه (همیشه بدهکار)
        if trade.commission_fee > 0:
            JournalEntryLine.objects.create(
                journal_entry=journal_entry,
                account=commission_expense_account,
                debit_amount=trade.commission_fee,
                credit_amount=0
            )

        # ۵. ثبت اثر نهایی بر روی حساب صندوق/نقد (Cash)
        net_cash_effect = trade.net_profit_or_loss - trade.commission_fee
        if net_cash_effect > 0:
            # افزایش موجودی نقد (بدهکار)
            JournalEntryLine.objects.create(
                journal_entry=journal_entry,
                account=cash_account,
                debit_amount=net_cash_effect,
                credit_amount=0
            )
        else:
            # کاهش موجودی نقد (بستانکار)
            JournalEntryLine.objects.create(
                journal_entry=journal_entry,
                account=cash_account,
                credit_amount=abs(net_cash_effect),
                debit_amount=0
            )
        
        print(f"Journal entry {journal_entry.id} created for trade {trade.id}") # برای لاگ و خطایابی