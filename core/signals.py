
from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import (
    TradingAccount, 
    ClosedTradesLog, 
    ChartOfAccount, 
    JournalEntry, 
    JournalEntryLine,
    User
)
from .models import ASSET, LIABILITY, EQUITY, REVENUE, EXPENSE # وارد کردن ثابت‌ها از مدل‌ها

# @receiver(post_save, sender=User)
# def create_payable_account_for_trader(sender, instance, **kwargs):
#     """
#     نسخه اشکال‌زدایی (Debug Version)
#     """
#     # --- شروع کدهای اشکال‌زدایی ---
#     print("\n--- Signal 'create_payable_account_for_trader' FIRED ---")
#     print(f"User being processed: {instance.username}")
#     print(f"User role is: '{instance.role}'")
#     # --- پایان کدهای اشکال‌زدایی ---

#     if instance.role == 'Trader':
#         print("Condition MET: User is a 'Trader'. Proceeding...")
#         try:
#             print("Attempting to find parent account '2000'...")
#             parent_account = ChartOfAccount.objects.get(account_number='2000', trading_account__isnull=True)
#             print("Parent account '2000' FOUND successfully.")
            
#             print(f"Attempting to get_or_create payable account for user: {instance.username}")
#             account, created = ChartOfAccount.objects.get_or_create(
#                 counterparty_user=instance,
#                 account_type=LIABILITY, # مطمئن شوید LIABILITY وارد شده
#                 defaults={
#                     'parent_account': parent_account,
#                     'account_name': f"Payable to Trader: {instance.username}",
#                     'account_number': f"2010-{instance.id}",
#                     'is_active': True
#                 }
#             )

#             if created:
#                 print(f"SUCCESS: New payable account was CREATED for {instance.username}.")
#             else:
#                 print(f"INFO: Payable account for {instance.username} already existed. No new account created.")

#         except ChartOfAccount.DoesNotExist:
#             print("ERROR: Parent account '2000' with no trading_account was NOT FOUND. Please create it in the admin panel.")
#         except Exception as e:
#             print(f"An UNEXPECTED ERROR occurred: {e}")
#     else:
#         print("Condition NOT MET: User is not a 'Trader'. Signal finished.")

# # --- سیگنال شماره ۲: صدور خودکار سند حسابداری برای معاملات بسته شده ---

# @receiver(post_save, sender=ClosedTradesLog)
# def create_journal_entry_for_trade(sender, instance, created, **kwargs):
#     """
#     این سیگنال به محض ایجاد یک ClosedTradesLog جدید (created=True) فعال می‌شود.
#     یک سند حسابداری متناظر برای ثبت سود/زیان و کارمزد معامله ایجاد می‌کند.
#     این تابع فرض می‌کند که سرفصل‌های لازم توسط سیگنال شماره ۱ از قبل ایجاد شده‌اند.
#     """
#     if created:
#         trade = instance
#         trading_acc = trade.trading_account

#         # ۱. پیدا کردن سرفصل‌های حسابداری مختص این حساب معاملاتی
#         # استفاده از .get() به این دلیل است که ما مطمئن هستیم این حساب‌ها وجود دارند.
#         # اگر وجود نداشته باشند، خطا می‌دهد که برای خطایابی بهتر است.
#         try:
#             cash_account = ChartOfAccount.objects.get(trading_account=trading_acc, account_number="1010")
#             commission_expense_account = ChartOfAccount.objects.get(trading_account=trading_acc, account_number="5010")
#         except ChartOfAccount.DoesNotExist as e:
#             print(f"Error: A required account for {trading_acc.name} does not exist. {e}")
#             return # از ادامه اجرای تابع جلوگیری می‌کند

#         # ۲. ایجاد هدر سند حسابداری
#         journal_entry = JournalEntry.objects.create(
#             entry_date=trade.trade_date,
#             description=f"Automated entry for trade #{trade.id} on asset {trade.asset.symbol}",
#             posted_by=trading_acc.user
#         )

#         # ۳. ثبت آرتیکل‌های بدهکار و بستانکار بر اساس سود یا زیان
#         if trade.net_profit_or_loss >= 0:
#             # حالت سود
#             profit = trade.net_profit_or_loss
#             revenue_account = ChartOfAccount.objects.get(trading_account=trading_acc, account_number="4010")
#             # ثبت درآمد به عنوان بستانکار
#             JournalEntryLine.objects.create(
#                 journal_entry=journal_entry,
#                 account=revenue_account,
#                 credit_amount=profit,
#                 debit_amount=0
#             )
#         else:
#             # حالت زیان
#             loss = abs(trade.net_profit_or_loss)
#             loss_account = ChartOfAccount.objects.get(trading_account=trading_acc, account_number="5010")
#             # ثبت زیان به عنوان بدهکار
#             JournalEntryLine.objects.create(
#                 journal_entry=journal_entry,
#                 account=loss_account,
#                 debit_amount=loss,
#                 credit_amount=0
#             )

#         # ۴. ثبت کارمزد به عنوان هزینه (همیشه بدهکار)
#         if trade.commission_fee > 0:
#             JournalEntryLine.objects.create(
#                 journal_entry=journal_entry,
#                 account=commission_expense_account,
#                 debit_amount=trade.commission_fee,
#                 credit_amount=0
#             )

#         # ۵. ثبت اثر نهایی بر روی حساب صندوق/نقد (Cash)
#         net_cash_effect = trade.net_profit_or_loss - trade.commission_fee
#         if net_cash_effect > 0:
#             # افزایش موجودی نقد (بدهکار)
#             JournalEntryLine.objects.create(
#                 journal_entry=journal_entry,
#                 account=cash_account,
#                 debit_amount=net_cash_effect,
#                 credit_amount=0
#             )
#         else:
#             # کاهش موجودی نقد (بستانکار)
#             JournalEntryLine.objects.create(
#                 journal_entry=journal_entry,
#                 account=cash_account,
#                 credit_amount=abs(net_cash_effect),
#                 debit_amount=0
#             )
        
#         print(f"Journal entry {journal_entry.id} created for trade {trade.id}") # برای لاگ و خطایابی