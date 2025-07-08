
from django.db import transaction
from django.utils import timezone
from django.db.models import Sum
from decimal import Decimal
from core.models import ChartOfAccount, JournalEntry, JournalEntryLine, TradingAccount, AssetLot, Asset, ClosedTradesLog
from .models import ASSET, LIABILITY, EQUITY, REVENUE, EXPENSE # وارد کردن ثابت‌ها از مدل‌ها



# --- الگوی جامع و نهایی سرفصل‌های حسابداری ---
CHART_OF_ACCOUNTS_TEMPLATE = [
    # ۱. دارایی‌ها (Assets)
    {'number': '1000', 'name': 'Assets', 'type': ASSET, 'children': [
        {'number': '1010', 'name': 'Cash - {account_name}', 'type': ASSET},
        
        # --- اضافه شده: حساب نگهداری دارایی‌های اسپات ---
        {'number': '1020', 'name': 'Spot Assets Holdings', 'type': ASSET},
        # ----------------------------------------------
        
        {'number': '1030', 'name': 'Derivative Contracts', 'type': ASSET},
        {'number': '1040', 'name': 'Initial Margin - {account_name}', 'type': ASSET},
        {'number': '1050', 'name': 'Maintenance Margin - {account_name}', 'type': ASSET},
        {'number': '1060', 'name': 'Unrealized PnL - Derivatives - {account_name}', 'type': ASSET},
    ]},
    
    # ۲. بدهی‌ها (Liabilities)
    {'number': '2000', 'name': 'Liabilities', 'type': LIABILITY},
    
    # ۳. حقوق صاحبان سهام (Equity)
    {'number': '3000', 'name': 'Equity', 'type': EQUITY, 'children': [
        # این حساب، همان حساب مربوط به "سهام‌دار" یا صاحب حساب است
        {'number': '3010', 'name': 'User Capital - {account_name}', 'type': EQUITY},
    ]},
    
    # ۴. درآمدها (Revenues)
    {'number': '4000', 'name': 'Revenues', 'type': REVENUE, 'children': [
        {'number': '4010', 'name': 'Realized PnL - Derivatives - {account_name}', 'type': REVENUE},
        {'number': '4020', 'name': 'Commissions & Fees', 'type': REVENUE},
        {'number': '4040', 'name': 'Funding Receipts - {account_name}', 'type': REVENUE},
        {'number': '4050', 'name': 'Lending Income - {account_name}', 'type': REVENUE},
        {'number': '4060', 'name': 'Staking Rewards - {account_name}', 'type': REVENUE},
    ]},
    
    # ۵. هزینه‌ها (Expenses)
    {'number': '5000', 'name': 'Expenses', 'type': EXPENSE, 'children': [
        {'number': '5010', 'name': 'Trading Fees - {account_name}', 'type': EXPENSE},
        {'number': '5020', 'name': 'Interest Expense - {account_name}', 'type': EXPENSE},
        {'number': '5040', 'name': 'Funding Payments - {account_name}', 'type': EXPENSE},
        {'number': '5050', 'name': 'Withdrawal Fees - {account_name}', 'type': EXPENSE},
        {'number': '5060', 'name': 'Platform Fees - {account_name}', 'type': EXPENSE},
    ]},
]

def _create_accounts_recursively(accounts_list, trading_account, parent_account=None):
    # این تابع کمکی بدون تغییر باقی می‌ماند
    for acc_def in accounts_list:
        new_account = ChartOfAccount.objects.create(
            trading_account=trading_account,
            parent_account=parent_account,
            account_number=acc_def['number'],
            account_name=acc_def['name'].format(account_name=trading_account.name),
            account_type=acc_def['type'],
            is_active=True
        )
        if 'children' in acc_def:
            _create_accounts_recursively(acc_def['children'], trading_account, parent_account=new_account)

def create_trading_account(user, name, account_type, account_purpose):
    """
    سرویس اصلی برای ساخت حساب معاملاتی و تمام زیرحساب‌های استاندارد آن.
    """
    with transaction.atomic():
        account = TradingAccount.objects.create(
            user=user,
            name=name,
            account_type=account_type,
            account_purpose=account_purpose
        )
        # فراخوانی تابع کمکی برای ساخت کل ساختار حسابداری برای این حساب جدید
        _create_accounts_recursively(CHART_OF_ACCOUNTS_TEMPLATE, trading_account=account)
        return account

def record_closed_trade(trading_account, asset, trade_date, net_profit_or_loss, broker_commission, trader_commission, commission_recipient):
    """
    سند حسابداری را برای یک معامله بسته شده ثبت می‌کند.
    این نسخه کامل و اصلاح شده، شامل منطق سود و زیان و کمیسیون‌های تفکیک شده است.
    """
    print("--- Service 'record_closed_trade' STARTED ---")
    
    # کل عملیات در یک تراکنش اتمی قرار می‌گیرد تا یا همه انجام شود یا هیچکدام
    with transaction.atomic():
        try:
            # ۱. اعتبارسنجی اولیه
            if asset.asset_type != Asset.DERIVATIVE:
                raise ValueError("خطا: فقط دارایی‌های مشتقه می‌توانند ثبت شوند.")

            print("Step 1: Validation passed.")

            # ۲. ایجاد لاگ معامله در دیتابیس
            trade = ClosedTradesLog.objects.create(
                trading_account=trading_account,
                asset=asset,
                trade_date=trade_date,
                net_profit_or_loss=net_profit_or_loss,
                broker_commission=broker_commission,
                trader_commission=trader_commission,
                commission_recipient=commission_recipient
            )
            print(f"Step 2: ClosedTradesLog #{trade.id} created.")

            # ۳. پیدا کردن حساب‌های اصلی مورد نیاز
            print("Step 3: Fetching required ChartOfAccount objects...")
            cash_account = ChartOfAccount.objects.get(trading_account=trading_account, account_number='1010')
            pnl_account = ChartOfAccount.objects.get(trading_account=trading_account, account_number='4010')
            fee_account = ChartOfAccount.objects.get(trading_account=trading_account, account_number='5010')
            print(" -> Found Cash, PnL, and Commission Expense accounts.")

            # ۴. ایجاد هدر سند حسابداری
            entry = JournalEntry.objects.create(
                entry_date=trade_date,
                description=f"Closed Trade: {asset.symbol} | PnL: {net_profit_or_loss}",
                posted_by=trading_account.user
            )
            print(f"Step 4: JournalEntry #{entry.id} created.")

            # ۵. ثبت آرتیکل‌های مربوط به سود/زیان خالص
            print("Step 5: Creating Journal Entry Lines for P&L...")
            if net_profit_or_loss > 0:
                # در صورت سود: بدهکار نقد، بستانکار درآمد (حساب 4010)
                JournalEntryLine.objects.create(journal_entry=entry, account=cash_account, debit_amount=net_profit_or_loss)
                JournalEntryLine.objects.create(journal_entry=entry, account=pnl_account, credit_amount=net_profit_or_loss)
            elif net_profit_or_loss < 0:
                # در صورت زیان: بدهکار درآمد (حساب 4010)، بستانکار نقد
                JournalEntryLine.objects.create(journal_entry=entry, account=pnl_account, debit_amount=abs(net_profit_or_loss))
                JournalEntryLine.objects.create(journal_entry=entry, account=cash_account, credit_amount=abs(net_profit_or_loss))

            # ۶. ثبت آرتیکل‌های مربوط به کمیسیون
            print("Step 6: Creating Journal Entry Lines for Commissions...")
            total_fees = broker_commission + trader_commission
            if total_fees  > 0:
                # هزینه کل، حساب هزینه را بدهکار می‌کند
                JournalEntryLine.objects.create(journal_entry=entry, account=fee_account, debit_amount=total_fees)                  
                # پرداخت کمیسیون بروکر، نقدینگی را کم می‌کند
                JournalEntryLine.objects.create(journal_entry=entry, account=cash_account, credit_amount=broker_commission)

                print(f" -> Broker commission paid: Credit Cash {broker_commission}")
                
                # ج) بستانکار کردن حساب بدهی به تریدر
                if trader_commission > 0:
                    liabilities_parent = ChartOfAccount.objects.get(trading_account=trading_account, account_number='2000')
                    trader_payable_account, created = ChartOfAccount.objects.get_or_create(
                        trading_account=trading_account,
                        counterparty_user=commission_recipient,
                        account_type=LIABILITY,
                        defaults={
                            'parent_account': liabilities_parent,
                            'account_name': f"Payable to: {commission_recipient.username}",
                            'account_number': f"2010-{commission_recipient.id}",
                            'is_active': True
                        }
                    )
                    JournalEntryLine.objects.create(journal_entry=entry, account=trader_payable_account, credit_amount=trader_commission)
                    print(f" -> Trader commission recorded as payable: Credit Payable Account {trader_commission}")

            print("--- Service 'record_closed_trade' FINISHED SUCCESSFULLY ---")
            return trade 

        except ChartOfAccount.DoesNotExist as e:
            # اگر هر کدام از حساب‌های اصلی پیدا نشوند، این خطا رخ می‌دهد
            print(f"--- Service 'record_closed_trade' FAILED ---")
            print(f"ERROR: A required account was not found. Details: {e}")
            # این خطا باعث می‌شود transaction.atomic کل عملیات را Rollback کند
            raise ValueError(f"حسابداری برای {trading_account.name} به درستی تنظیم نشده است. حساب مورد نیاز پیدا نشد.")
        except Exception as e:
            print(f"--- Service 'record_closed_trade' FAILED with an unexpected error ---")
            print(f"ERROR: {e}")
            raise e # خطا را دوباره ایجاد می‌کنیم تا تراکنش Rollback شود




def delete_trading_account(trading_account: TradingAccount):
    """
    Deletes a trading account and all of its related data in the correct order.
    """
    with transaction.atomic():
        # Delete related objects in the correct order to avoid ProtectedError
        AssetLot.objects.filter(trading_account=trading_account).delete()
        ClosedTradesLog.objects.filter(trading_account=trading_account).delete()
        JournalEntry.objects.filter(posted_by=trading_account.user).delete() # This might be too broad, consider a more specific filter
        ChartOfAccount.objects.filter(trading_account=trading_account).delete()
        
        # Finally, delete the trading account itself
        trading_account.delete()

def make_deposit(trading_account, amount, description, user):
    """
    This function handles the main logic for depositing funds.
    It creates a journal entry for depositing funds into a specified trading account.
    """
    with transaction.atomic():
        if not amount or float(amount) <= 0:
            raise ValueError("Amount must be a positive number.")

        try:
            cash_account = ChartOfAccount.objects.get(trading_account=trading_account, account_number='1010')
            equity_account = ChartOfAccount.objects.get(trading_account=trading_account, account_number='3010')

            entry = JournalEntry.objects.create(
                entry_date=timezone.now().date(),
                description=description,
                posted_by=user
            )

            # Debit: Cash account increases
            JournalEntryLine.objects.create(
                journal_entry=entry,
                account=cash_account,
                debit_amount=amount
            )

            # Credit: Equity account increases
            JournalEntryLine.objects.create(
                journal_entry=entry,
                account=equity_account,
                credit_amount=amount
            )
            
            return entry

        except ChartOfAccount.DoesNotExist:
            raise ValueError(f"Required accounts are not set up for {trading_account.name}.")

def calculate_unrealized_pnl(trading_account: TradingAccount, current_prices: dict) -> Decimal:
    """
    Calculates the unrealized Profit and Loss for spot assets in a given trading account.
    current_prices: A dictionary where keys are asset symbols (str) and values are their current prices (Decimal).
    """
    if not isinstance(trading_account, TradingAccount):
        raise TypeError("trading_account must be an instance of TradingAccount.")
    if not isinstance(current_prices, dict):
        raise TypeError("current_prices must be a dictionary.")

    total_unrealized_pnl = Decimal('0.00')

    # Calculate unrealized PnL for spot assets (AssetLot)
    spot_asset_lots = AssetLot.objects.filter(
        trading_account=trading_account,
        remaining_quantity__gt=0,
        asset__asset_type=Asset.SPOT
    )

    for lot in spot_asset_lots:
        asset_symbol = lot.asset.symbol
        if asset_symbol in current_prices:
            current_price = Decimal(str(current_prices[asset_symbol])) # Ensure Decimal conversion
            cost_basis = lot.remaining_quantity * lot.purchase_price_usd
            current_market_value = lot.remaining_quantity * current_price
            unrealized_pnl_for_lot = current_market_value - cost_basis
            total_unrealized_pnl += unrealized_pnl_for_lot
        else:
            # Optionally log a warning if a price is not found for an asset
            print(f"Warning: Current price not found for asset {asset_symbol} in trading account {trading_account.name}.")
            # For now, we'll assume 0 PnL if price is missing, or you might want to raise an error.
            # Depending on requirements, you might want to exclude this lot or handle it differently.

    # TODO: Implement unrealized PnL calculation for derivative open positions if applicable.
    # This would require a separate model for open derivative positions.

    return total_unrealized_pnl

def transfer_funds_between_accounts(from_trading_account: TradingAccount, to_trading_account: TradingAccount, amount: Decimal, description: str, user) -> JournalEntry:
    """
    Handles the transfer of funds between two trading accounts belonging to the same user.
    Generates the correct journal entries for the transfer.
    """
    with transaction.atomic():
        if not isinstance(from_trading_account, TradingAccount) or not isinstance(to_trading_account, TradingAccount):
            raise TypeError("from_trading_account and to_trading_account must be instances of TradingAccount.")
        if not isinstance(amount, Decimal) or amount <= 0:
            raise ValueError("Amount must be a positive Decimal.")
        if from_trading_account.user != to_trading_account.user:
            raise ValueError("Cannot transfer funds between accounts belonging to different users.")
        if from_trading_account == to_trading_account:
            raise ValueError("Cannot transfer funds to the same account.")

        try:
            # Get cash accounts for both trading accounts
            from_cash_account = ChartOfAccount.objects.get(trading_account=from_trading_account, account_number='1010')
            to_cash_account = ChartOfAccount.objects.get(trading_account=to_trading_account, account_number='1010')

            # Check if from_trading_account has sufficient funds (simplified check for cash balance)
            # This assumes '1010' is the primary cash account and its balance reflects available funds.
            # A more robust check might involve summing all cash-equivalent accounts.
            current_balance = from_cash_account.journalentryline_set.aggregate(
                balance=Sum('debit_amount') - Sum('credit_amount')
            )['balance'] or Decimal('0.00')

            if current_balance < amount:
                raise ValueError(f"Insufficient funds in {from_trading_account.name}. Available: {current_balance}, Attempted transfer: {amount}")

            # Create a single journal entry for the transfer
            entry = JournalEntry.objects.create(
                entry_date=timezone.now().date(),
                description=f"Inter-account transfer: {description}",
                posted_by=user
            )

            # Journal Entry Lines:
            # 1. Credit the 'from' account's cash account (funds leaving)
            JournalEntryLine.objects.create(
                journal_entry=entry,
                account=from_cash_account,
                credit_amount=amount
            )

            # 2. Debit the 'to' account's cash account (funds entering)
            JournalEntryLine.objects.create(
                journal_entry=entry,
                account=to_cash_account,
                debit_amount=amount
            )
            
            return entry

        except ChartOfAccount.DoesNotExist:
            raise ValueError("One or both trading accounts do not have a cash account (account number 1010) set up.")

def make_withdrawal(trading_account, amount, description, user):
    """
    This function handles the main logic for withdrawing funds.
    It creates a journal entry for withdrawing funds from a specified trading account.
    """
    with transaction.atomic():
        if not amount or float(amount) <= 0:
            raise ValueError("Amount must be a positive number.")

        try:
            cash_account = ChartOfAccount.objects.get(trading_account=trading_account, account_number='1010')
            equity_account = ChartOfAccount.objects.get(trading_account=trading_account, account_number='3010')

            # Check for sufficient funds (simplified)
            current_balance = cash_account.journalentryline_set.aggregate(
                balance=Sum('debit_amount') - Sum('credit_amount')
            )['balance'] or Decimal('0.00')

            if current_balance < amount:
                raise ValueError(f"Insufficient funds in {trading_account.name}. Available: {current_balance}, Attempted withdrawal: {amount}")

            entry = JournalEntry.objects.create(
                entry_date=timezone.now().date(),
                description=description,
                posted_by=user
            )

            # Credit: Cash account decreases
            JournalEntryLine.objects.create(
                journal_entry=entry,
                account=cash_account,
                credit_amount=amount
            )

            # Debit: Equity account decreases (or a specific withdrawal account)
            JournalEntryLine.objects.create(
                journal_entry=entry,
                account=equity_account,
                debit_amount=amount
            )
            
            return entry

        except ChartOfAccount.DoesNotExist:
            raise ValueError(f"Required accounts are not set up for {trading_account.name}.")

def deposit_spot_asset(trading_account, asset, quantity, price_usd, description, user):
    """
    Handles the deposit of a spot asset into a trading account.
    Creates an AssetLot and updates the cash account.
    """
    with transaction.atomic():
        if not isinstance(quantity, Decimal) or quantity <= 0:
            raise ValueError("Quantity must be a positive Decimal.")
        if not isinstance(price_usd, Decimal) or price_usd <= 0:
            raise ValueError("Price USD must be a positive Decimal.")
        if asset.asset_type != Asset.SPOT:
            raise ValueError("Asset must be of type SPOT for this operation.")

        # Create an AssetLot for the deposited asset
        AssetLot.objects.create(
            asset=asset,
            trading_account=trading_account,
            quantity=quantity,
            purchase_price_usd=price_usd,
            remaining_quantity=quantity # Initially, all quantity is remaining
        )

        # Create journal entry for the cash equivalent of the deposit
        try:
            cash_account = ChartOfAccount.objects.get(trading_account=trading_account, account_number='1010')
            equity_account = ChartOfAccount.objects.get(trading_account=trading_account, account_number='3010') # Or a specific asset deposit account

            total_value = quantity * price_usd

            entry = JournalEntry.objects.create(
                entry_date=timezone.now().date(),
                description=f"Deposit of {quantity} {asset.symbol} at ${price_usd}/unit: {description}",
                posted_by=user
            )

            # Debit: Cash account increases (representing the value of the asset received)
            JournalEntryLine.objects.create(
                journal_entry=entry,
                account=cash_account,
                debit_amount=total_value
            )

            # Credit: Equity account increases
            JournalEntryLine.objects.create(
                journal_entry=entry,
                account=equity_account,
                credit_amount=total_value
            )
            return entry
        except ChartOfAccount.DoesNotExist:
            raise ValueError(f"Required accounts are not set up for {trading_account.name}.")

def withdraw_spot_asset(trading_account, asset, quantity, price_usd, description, user):
    """
    Handles the withdrawal of a spot asset from a trading account.
    Reduces AssetLot quantities and updates the cash account.
    """
    with transaction.atomic():
        if not isinstance(quantity, Decimal) or quantity <= 0:
            raise ValueError("Quantity must be a positive Decimal.")
        if not isinstance(price_usd, Decimal) or price_usd <= 0:
            raise ValueError("Price USD must be a positive Decimal.")
        if asset.asset_type != Asset.SPOT:
            raise ValueError("Asset must be of type SPOT for this operation.")

        # Check if enough quantity is available across all lots
        available_quantity = AssetLot.objects.filter(
            trading_account=trading_account,
            asset=asset,
            remaining_quantity__gt=0
        ).aggregate(total=Sum('remaining_quantity'))['total'] or Decimal('0.00')

        if available_quantity < quantity:
            raise ValueError(f"Insufficient quantity of {asset.symbol} for withdrawal. Available: {available_quantity}, Attempted: {quantity}")

        # Reduce quantity from AssetLots (FIFO - First In, First Out)
        lots_to_deduct = AssetLot.objects.filter(
            trading_account=trading_account,
            asset=asset,
            remaining_quantity__gt=0
        ).order_by('purchase_date')

        remaining_to_withdraw = quantity
        for lot in lots_to_deduct:
            if remaining_to_withdraw <= 0:
                break
            
            deduct_from_lot = min(lot.remaining_quantity, remaining_to_withdraw)
            lot.remaining_quantity -= deduct_from_lot
            lot.save()
            remaining_to_withdraw -= deduct_from_lot

        # Create journal entry for the cash equivalent of the withdrawal
        try:
            cash_account = ChartOfAccount.objects.get(trading_account=trading_account, account_number='1010')
            equity_account = ChartOfAccount.objects.get(trading_account=trading_account, account_number='3010') # Or a specific asset withdrawal account

            total_value = quantity * price_usd

            entry = JournalEntry.objects.create(
                entry_date=timezone.now().date(),
                description=f"Withdrawal of {quantity} {asset.symbol} at ${price_usd}/unit: {description}",
                posted_by=user
            )

            # Credit: Cash account decreases
            JournalEntryLine.objects.create(
                journal_entry=entry,
                account=cash_account,
                credit_amount=total_value
            )

            # Debit: Equity account decreases
            JournalEntryLine.objects.create(
                journal_entry=entry,
                account=equity_account,
                debit_amount=total_value
            )
            return entry
        except ChartOfAccount.DoesNotExist:
            raise ValueError(f"Required accounts are not set up for {trading_account.name}.")

def execute_spot_buy(trading_account, asset, quantity, trade_cost, description, user):
    """
    Handles the buying of a spot asset.
    Creates an AssetLot and debits the cash account.
    """
    with transaction.atomic():
        if not isinstance(quantity, Decimal) or quantity <= 0:
            raise ValueError("Quantity must be a positive Decimal.")
        if not isinstance(trade_cost, Decimal) or trade_cost <= 0:
            raise ValueError("Trade cost must be a positive Decimal.")
        if asset.asset_type != Asset.SPOT:
            raise ValueError("Asset must be of type SPOT for this operation.")

        try:
            cash_account = ChartOfAccount.objects.get(trading_account=trading_account, account_number='1010')
            # Check for sufficient funds
            current_balance = cash_account.journalentryline_set.aggregate(
                balance=Sum('debit_amount') - Sum('credit_amount')
            )['balance'] or Decimal('0.00')

            if current_balance < trade_cost:
                raise ValueError(f"Insufficient cash in {trading_account.name} to cover trade cost. Available: {current_balance}, Required: {trade_cost}")

            # Create AssetLot for the purchased asset
            purchase_price_usd = trade_cost / quantity # Calculate per unit price
            AssetLot.objects.create(
                asset=asset,
                trading_account=trading_account,
                quantity=quantity,
                purchase_price_usd=purchase_price_usd,
                remaining_quantity=quantity
            )

            # Create journal entry for the purchase
            entry = JournalEntry.objects.create(
                entry_date=timezone.now().date(),
                description=f"Spot Buy: {quantity} {asset.symbol} for ${trade_cost}: {description}",
                posted_by=user
            )

            # Credit: Cash account decreases
            JournalEntryLine.objects.create(
                journal_entry=entry,
                account=cash_account,
                credit_amount=trade_cost
            )

            # Debit: Asset account increases (representing the value of the asset acquired)
            # Assuming a generic asset account or specific asset accounts are set up
            # For simplicity, we might debit an 'Inventory' or 'Investments' account (e.g., 1020)
            # For now, let's assume a generic asset account for purchased assets.
            # You might need to define a specific ChartOfAccount for 'Investments' or 'Digital Assets'
            # For this example, let's assume a generic asset account for purchased assets (e.g., 1020)
            asset_holding_account, created = ChartOfAccount.objects.get_or_create(
                trading_account=trading_account,
                account_number='1020', # Example account number for asset holdings
                defaults={'account_name': 'Asset Holdings', 'account_type': ChartOfAccount.ASSET}
            )
            JournalEntryLine.objects.create(
                journal_entry=entry,
                account=asset_holding_account,
                debit_amount=trade_cost
            )
            return entry

        except ChartOfAccount.DoesNotExist:
            raise ValueError(f"Required cash account (1010) not set up for {trading_account.name}.")

def execute_spot_sell(trading_account, asset, quantity, trade_cost, description, user):
    """
    Handles the selling of a spot asset.
    Reduces AssetLot quantities and credits the cash account.
    """
    with transaction.atomic():
        if not isinstance(quantity, Decimal) or quantity <= 0:
            raise ValueError("Quantity must be a positive Decimal.")
        if not isinstance(trade_cost, Decimal) or trade_cost <= 0: # trade_cost here is the proceeds from sale
            raise ValueError("Trade proceeds must be a positive Decimal.")
        if asset.asset_type != Asset.SPOT:
            raise ValueError("Asset must be of type SPOT for this operation.")

        # Check if enough quantity is available across all lots
        available_quantity = AssetLot.objects.filter(
            trading_account=trading_account,
            asset=asset,
            remaining_quantity__gt=0
        ).aggregate(total=Sum('remaining_quantity'))['total'] or Decimal('0.00')

        if available_quantity < quantity:
            raise ValueError(f"Insufficient quantity of {asset.symbol} for sale. Available: {available_quantity}, Attempted: {quantity}")

        # Reduce quantity from AssetLots (FIFO - First In, First Out)
        lots_to_deduct = AssetLot.objects.filter(
            trading_account=trading_account,
            asset=asset,
            remaining_quantity__gt=0
        ).order_by('purchase_date')

        remaining_to_sell = quantity
        total_cost_of_sold_assets = Decimal('0.00')

        for lot in lots_to_deduct:
            if remaining_to_sell <= 0:
                break
            
            deduct_from_lot = min(lot.remaining_quantity, remaining_to_sell)
            total_cost_of_sold_assets += deduct_from_lot * lot.purchase_price_usd
            lot.remaining_quantity -= deduct_from_lot
            lot.save()
            remaining_to_sell -= deduct_from_lot

        # Calculate realized PnL
        realized_pnl = trade_cost - total_cost_of_sold_assets

        # Create journal entry for the sale
        try:
            cash_account = ChartOfAccount.objects.get(trading_account=trading_account, account_number='1010')
            # Assuming a generic asset account for sold assets (e.g., 1020)
            asset_holding_account, created = ChartOfAccount.objects.get_or_create(
                trading_account=trading_account,
                account_number='1020', # Example account number for asset holdings
                defaults={'account_name': 'Asset Holdings', 'account_type': ChartOfAccount.ASSET}
            )
            # Assuming a realized PnL account (e.g., 4010 for gains, 5010 for losses)
            realized_pnl_account_number = '4010' if realized_pnl >= 0 else '5010'
            realized_pnl_account_name = 'Realized Gains' if realized_pnl >= 0 else 'Realized Losses'
            realized_pnl_account_type = ChartOfAccount.REVENUE if realized_pnl >= 0 else ChartOfAccount.EXPENSE

            realized_pnl_account, created = ChartOfAccount.objects.get_or_create(
                trading_account=trading_account,
                account_number=realized_pnl_account_number,
                defaults={'account_name': realized_pnl_account_name, 'account_type': realized_pnl_account_type}
            )

            entry = JournalEntry.objects.create(
                entry_date=timezone.now().date(),
                description=f"Spot Sell: {quantity} {asset.symbol} for ${trade_cost}. Realized PnL: ${realized_pnl}: {description}",
                posted_by=user
            )

            # Debit: Cash account increases (proceeds from sale)
            JournalEntryLine.objects.create(
                journal_entry=entry,
                account=cash_account,
                debit_amount=trade_cost
            )

            # Credit: Asset account decreases (cost of assets sold)
            JournalEntryLine.objects.create(
                journal_entry=entry,
                account=asset_holding_account,
                credit_amount=total_cost_of_sold_assets
            )

            # Handle Realized PnL
            if realized_pnl != 0:
                if realized_pnl > 0:
                    # Credit: Realized Gains account increases
                    JournalEntryLine.objects.create(
                        journal_entry=entry,
                        account=realized_pnl_account,
                        credit_amount=realized_pnl
                    )
                else:
                    # Debit: Realized Losses account increases
                    JournalEntryLine.objects.create(
                        journal_entry=entry,
                        account=realized_pnl_account,
                        debit_amount=abs(realized_pnl)
                    )
            return entry

        except ChartOfAccount.DoesNotExist:
            raise ValueError(f"Required accounts not set up for {trading_account.name}.")

def generate_income_statement(trading_account, start_date, end_date):
    """
    Generates an income statement for a given trading account within a specified date range.
    """
    income_statement_data = {
        'revenues': {},
        'expenses': {},
        'net_profit_loss': Decimal('0.00')
    }

    # Get all journal entry lines for the trading account within the date range
    # that are related to Revenue or Expense accounts.
    relevant_lines = JournalEntryLine.objects.filter(
        journal_entry__entry_date__range=[start_date, end_date],
        account__trading_account=trading_account,
        account__account_type__in=[ChartOfAccount.REVENUE, ChartOfAccount.EXPENSE]
    )

    total_revenues = Decimal('0.00')
    total_expenses = Decimal('0.00')

    for line in relevant_lines:
        account_name = line.account.account_name
        if line.account.account_type == ChartOfAccount.REVENUE:
            # Revenues increase with credits, decrease with debits
            amount = line.credit_amount - line.debit_amount
            income_statement_data['revenues'][account_name] = income_statement_data['revenues'].get(account_name, Decimal('0.00')) + amount
            total_revenues += amount
        elif line.account.account_type == ChartOfAccount.EXPENSE:
            # Expenses increase with debits, decrease with credits
            amount = line.debit_amount - line.credit_amount
            income_statement_data['expenses'][account_name] = income_statement_data['expenses'].get(account_name, Decimal('0.00')) + amount
            total_expenses += amount

    income_statement_data['net_profit_loss'] = total_revenues - total_expenses

    return income_statement_data

