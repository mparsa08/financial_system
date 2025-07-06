from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from decimal import Decimal
from core.models import TradingAccount, ChartOfAccount, Asset, AssetLot, JournalEntry, JournalEntryLine, ASSET, LIABILITY, EQUITY, REVENUE, EXPENSE
from core.services import calculate_unrealized_pnl, transfer_funds_between_accounts, make_deposit

User = get_user_model()

class ServiceTests(TestCase):

    def setUp(self):
        self.user1 = User.objects.create_user(username='testuser1', password='password123')
        self.user2 = User.objects.create_user(username='testuser2', password='password123')

        self.trading_account1 = TradingAccount.objects.create(
            user=self.user1,
            name='User1 Crypto Account',
            account_type=TradingAccount.CRYPTO,
            account_purpose=TradingAccount.SPOT
        )
        self.trading_account2 = TradingAccount.objects.create(
            user=self.user1,
            name='User1 Forex Account',
            account_type=TradingAccount.FOREX,
            account_purpose=TradingAccount.SPOT
        )
        self.trading_account_user2 = TradingAccount.objects.create(
            user=self.user2,
            name='User2 Crypto Account',
            account_type=TradingAccount.CRYPTO,
            account_purpose=TradingAccount.SPOT
        )

        # Create essential ChartOfAccount entries for trading_account1
        self.cash_account1 = ChartOfAccount.objects.create(
            trading_account=self.trading_account1,
            account_number='1010',
            account_name='Cash',
            account_type=ChartOfAccount.ASSET
        )
        self.equity_account1 = ChartOfAccount.objects.create(
            trading_account=self.trading_account1,
            account_number='3010',
            account_name='Equity',
            account_type=ChartOfAccount.EQUITY
        )

        # Create essential ChartOfAccount entries for trading_account2
        self.cash_account2 = ChartOfAccount.objects.create(
            trading_account=self.trading_account2,
            account_number='1010',
            account_name='Cash',
            account_type=ChartOfAccount.ASSET
        )
        self.equity_account2 = ChartOfAccount.objects.create(
            trading_account=self.trading_account2,
            account_number='3010',
            account_name='Equity',
            account_type=ChartOfAccount.EQUITY
        )

        # Create essential ChartOfAccount entries for trading_account_user2
        self.cash_account_user2 = ChartOfAccount.objects.create(
            trading_account=self.trading_account_user2,
            account_number='1010',
            account_name='Cash',
            account_type=ChartOfAccount.ASSET
        )
        self.equity_account_user2 = ChartOfAccount.objects.create(
            trading_account=self.trading_account_user2,
            account_number='3010',
            account_name='Equity',
            account_type=ChartOfAccount.EQUITY
        )

        self.btc_asset = Asset.objects.create(symbol='BTC', name='Bitcoin', asset_type=Asset.SPOT)
        self.eth_asset = Asset.objects.create(symbol='ETH', name='Ethereum', asset_type=Asset.SPOT)

    def _get_account_balance(self, account):
        """Helper to get the current balance of an account."""
        balance = account.journalentryline_set.aggregate(
            total_debit=Sum('debit_amount'),
            total_credit=Sum('credit_amount')
        )
        debit = balance['total_debit'] or Decimal('0.00')
        credit = balance['total_credit'] or Decimal('0.00')
        return debit - credit

    def test_calculate_unrealized_pnl_single_lot_profit(self):
        AssetLot.objects.create(
            asset=self.btc_asset,
            trading_account=self.trading_account1,
            quantity=Decimal('1.0'),
            purchase_price_usd=Decimal('10000.00'),
            remaining_quantity=Decimal('1.0')
        )
        current_prices = {'BTC': Decimal('12000.00')}
        pnl = calculate_unrealized_pnl(self.trading_account1, current_prices)
        self.assertEqual(pnl, Decimal('2000.00'))

    def test_calculate_unrealized_pnl_single_lot_loss(self):
        AssetLot.objects.create(
            asset=self.btc_asset,
            trading_account=self.trading_account1,
            quantity=Decimal('1.0'),
            purchase_price_usd=Decimal('10000.00'),
            remaining_quantity=Decimal('1.0')
        )
        current_prices = {'BTC': Decimal('8000.00')}
        pnl = calculate_unrealized_pnl(self.trading_account1, current_prices)
        self.assertEqual(pnl, Decimal('-2000.00'))

    def test_calculate_unrealized_pnl_multiple_lots(self):
        AssetLot.objects.create(
            asset=self.btc_asset,
            trading_account=self.trading_account1,
            quantity=Decimal('1.0'),
            purchase_price_usd=Decimal('10000.00'),
            remaining_quantity=Decimal('1.0')
        )
        AssetLot.objects.create(
            asset=self.eth_asset,
            trading_account=self.trading_account1,
            quantity=Decimal('5.0'),
            purchase_price_usd=Decimal('1000.00'),
            remaining_quantity=Decimal('5.0')
        )
        current_prices = {'BTC': Decimal('12000.00'), 'ETH': Decimal('900.00')}
        pnl = calculate_unrealized_pnl(self.trading_account1, current_prices)
        # BTC: (1 * 12000) - (1 * 10000) = 2000
        # ETH: (5 * 900) - (5 * 1000) = 4500 - 5000 = -500
        # Total: 2000 - 500 = 1500
        self.assertEqual(pnl, Decimal('1500.00'))

    def test_calculate_unrealized_pnl_no_remaining_quantity(self):
        AssetLot.objects.create(
            asset=self.btc_asset,
            trading_account=self.trading_account1,
            quantity=Decimal('1.0'),
            purchase_price_usd=Decimal('10000.00'),
            remaining_quantity=Decimal('0.0')
        )
        current_prices = {'BTC': Decimal('12000.00')}
        pnl = calculate_unrealized_pnl(self.trading_account1, current_prices)
        self.assertEqual(pnl, Decimal('0.00'))

    def test_calculate_unrealized_pnl_missing_price(self):
        AssetLot.objects.create(
            asset=self.btc_asset,
            trading_account=self.trading_account1,
            quantity=Decimal('1.0'),
            purchase_price_usd=Decimal('10000.00'),
            remaining_quantity=Decimal('1.0')
        )
        current_prices = {'ETH': Decimal('100.00')} # BTC price is missing
        pnl = calculate_unrealized_pnl(self.trading_account1, current_prices)
        self.assertEqual(pnl, Decimal('0.00')) # Should be 0 if price is missing

    def test_calculate_unrealized_pnl_no_lots(self):
        current_prices = {'BTC': Decimal('12000.00')}
        pnl = calculate_unrealized_pnl(self.trading_account1, current_prices)
        self.assertEqual(pnl, Decimal('0.00'))

    def test_transfer_funds_between_accounts_success(self):
        # Initial deposit to trading_account1
        make_deposit(self.trading_account1, Decimal('1000.00'), "Initial deposit", self.user1)
        initial_balance_acc1 = self._get_account_balance(self.cash_account1)
        initial_balance_acc2 = self._get_account_balance(self.cash_account2)

        transfer_amount = Decimal('200.00')
        entry = transfer_funds_between_accounts(
            self.trading_account1, self.trading_account2, transfer_amount, "Transfer test", self.user1
        )

        self.assertIsNotNone(entry)
        self.assertEqual(JournalEntry.objects.count(), 2) # Initial deposit + transfer
        self.assertEqual(JournalEntryLine.objects.count(), 4) # 2 for deposit + 2 for transfer

        # Verify balances
        self.assertEqual(self._get_account_balance(self.cash_account1), initial_balance_acc1 - transfer_amount)
        self.assertEqual(self._get_account_balance(self.cash_account2), initial_balance_acc2 + transfer_amount)

        # Verify journal entry lines
        credit_line = JournalEntryLine.objects.get(journal_entry=entry, account=self.cash_account1)
        self.assertEqual(credit_line.credit_amount, transfer_amount)
        self.assertEqual(credit_line.debit_amount, Decimal('0.00'))

        debit_line = JournalEntryLine.objects.get(journal_entry=entry, account=self.cash_account2)
        self.assertEqual(debit_line.debit_amount, transfer_amount)
        self.assertEqual(debit_line.credit_amount, Decimal('0.00'))

    def test_transfer_funds_between_accounts_insufficient_funds(self):
        # Initial deposit to trading_account1
        make_deposit(self.trading_account1, Decimal('100.00'), "Initial deposit", self.user1)

        transfer_amount = Decimal('200.00')
        with self.assertRaisesRegex(ValueError, "Insufficient funds"): # Use assertRaisesRegex for specific message
            transfer_funds_between_accounts(
                self.trading_account1, self.trading_account2, transfer_amount, "Transfer test", self.user1
            )
        # Ensure no new journal entries were created
        self.assertEqual(JournalEntry.objects.count(), 1)
        self.assertEqual(JournalEntryLine.objects.count(), 2)

    def test_transfer_funds_between_accounts_different_users(self):
        make_deposit(self.trading_account1, Decimal('1000.00'), "Initial deposit", self.user1)
        make_deposit(self.trading_account_user2, Decimal('500.00'), "Initial deposit", self.user2)

        transfer_amount = Decimal('100.00')
        with self.assertRaisesRegex(ValueError, "Cannot transfer funds between accounts belonging to different users."):
            transfer_funds_between_between_accounts(
                self.trading_account1, self.trading_account_user2, transfer_amount, "Transfer test", self.user1
            )
        # Ensure no new journal entries were created
        self.assertEqual(JournalEntry.objects.count(), 2)
        self.assertEqual(JournalEntryLine.objects.count(), 4)

    def test_transfer_funds_between_accounts_same_account(self):
        make_deposit(self.trading_account1, Decimal('1000.00'), "Initial deposit", self.user1)

        transfer_amount = Decimal('100.00')
        with self.assertRaisesRegex(ValueError, "Cannot transfer funds to the same account."):
            transfer_funds_between_accounts(
                self.trading_account1, self.trading_account1, transfer_amount, "Transfer test", self.user1
            )
        # Ensure no new journal entries were created
        self.assertEqual(JournalEntry.objects.count(), 1)
        self.assertEqual(JournalEntryLine.objects.count(), 2)

    def test_transfer_funds_between_accounts_invalid_amount(self):
        make_deposit(self.trading_account1, Decimal('1000.00'), "Initial deposit", self.user1)

        with self.assertRaisesRegex(ValueError, "Amount must be a positive Decimal."):
            transfer_funds_between_accounts(
                self.trading_account1, self.trading_account2, Decimal('0.00'), "Zero amount", self.user1
            )
        with self.assertRaisesRegex(ValueError, "Amount must be a positive Decimal."):
            transfer_funds_between_accounts(
                self.trading_account1, self.trading_account2, Decimal('-10.00'), "Negative amount", self.user1
            )
        # Ensure no new journal entries were created
        self.assertEqual(JournalEntry.objects.count(), 1)
        self.assertEqual(JournalEntryLine.objects.count(), 2)

    def test_transfer_funds_between_accounts_missing_cash_account(self):
        # Delete cash account for trading_account1 to simulate missing setup
        self.cash_account1.delete()

        make_deposit(self.trading_account2, Decimal('1000.00'), "Initial deposit", self.user1)

        transfer_amount = Decimal('100.00')
        with self.assertRaisesRegex(ValueError, "One or both trading accounts do not have a cash account"): # Use assertRaisesRegex for specific message
            transfer_funds_between_accounts(
                self.trading_account2, self.trading_account1, transfer_amount, "Transfer test", self.user1
            )
        # Ensure no new journal entries were created beyond the initial deposit
        self.assertEqual(JournalEntry.objects.count(), 1)
        self.assertEqual(JournalEntryLine.objects.count(), 2)