from django.contrib.auth.models import User
from django.db.models.aggregates import Sum
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse_lazy
from django.views.generic import CreateView, TemplateView, View, ListView, UpdateView, DeleteView, FormView
from core.models import (
    TradingAccount,
    Asset,
    JournalEntry,
    JournalEntryLine,
    Trade,
    ChartOfAccount,
    Currency,
    AssetLot,
    ASSET, LIABILITY, EQUITY, EXPENSE
)
from core.services import (
    open_trade,
    close_trade,
    create_trading_account,
    generate_income_statement,
    make_deposit,
    make_withdrawal,
    deposit_spot_asset,
    withdraw_spot_asset,
    execute_spot_buy,
    execute_spot_sell,
    calculate_unrealized_pnl,
    transfer_funds_between_accounts,
    record_direct_closed_trade,
    record_expense
)
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponseRedirect
from datetime import datetime
from .forms import OpenTradeForm, TradingAccountForm, CloseTradeForm, DirectClosedTradeForm, CustomUserCreationForm, ExpenseForm
from django.contrib.auth import get_user_model
from django.utils import timezone

class RegisterView(CreateView):
    form_class = CustomUserCreationForm
    template_name = 'register.html'
    success_url = reverse_lazy('login')

    def form_valid(self, form):
        user = form.save()
        login(self.request, user)
        messages.success(self.request, f'Welcome, {user.username}!')
        return redirect(self.success_url)



User = get_user_model()


class DirectClosedTradeView(LoginRequiredMixin, CreateView):
    """
    این ویو صفحه ثبت مستقیم یک معامله بسته شده را مدیریت می‌کند.
    """
    model = Trade
    form_class = DirectClosedTradeForm
    template_name = 'direct_add_trade.html' # یک تمپلیت جدید برای این فرم
    success_url = reverse_lazy('transaction_history') # کاربر را به صفحه تاریخچه معاملات هدایت می‌کند

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def form_valid(self, form):
        data = form.cleaned_data
        try:
            # فراخوانی سرویس جدید
            created_trade = record_direct_closed_trade(
                trading_account=data['trading_account'],
                asset=data['asset'],
                position_side=data['position_side'],
                quantity=data['quantity'],
                entry_price=data['entry_price'],
                exit_price=data['exit_price'],
                exit_date=data['exit_date'],
                gross_pnl=data['gross_profit_or_loss'],
                broker_commission=data['broker_commission'],
                trader_commission=data['trader_commission'],
                commission_recipient=data['commission_recipient'],
                exit_description="Directly recorded closed trade."
            )

            self.object = created_trade

            messages.success(self.request, "معامله بسته شده با موفقیت ثبت شد.")
        except ValueError as e:
            messages.error(self.request, f"خطا در ثبت معامله: {e}")
            return self.form_invalid(form)
            
        return HttpResponseRedirect(self.get_success_url())
        
class CloseTradeView(LoginRequiredMixin, FormView):
    """
    این ویو فرآیند بستن یک معامله باز را مدیریت می‌کند.
    """
    template_name = 'close_trade.html'
    form_class = CloseTradeForm
    success_url = reverse_lazy('open_trades_list')

    def get_context_data(self, **kwargs):
        # معامله‌ای که قرار است بسته شود را به تمپلیت ارسال می‌کنیم
        context = super().get_context_data(**kwargs)
        context['trade'] = get_object_or_404(Trade, pk=self.kwargs['pk'], trading_account__user=self.request.user)
        return context

    def form_valid(self, form):
        trade_to_close = get_object_or_404(Trade, pk=self.kwargs['pk'])
        data = form.cleaned_data
        
        try:
            # فراخوانی سرویس بستن معامله
            close_trade(
                trade_to_close=trade_to_close,
                gross_profit_or_loss=data['gross_profit_or_loss'],
                broker_commission=data['broker_commission'],
                trader_commission=data['trader_commission'],
                commission_recipient=data['commission_recipient'],
                exit_description=data['exit_description']
            )
            messages.success(self.request, f"معامله #{trade_to_close.id} با موفقیت بسته شد.")
        except ValueError as e:
            messages.error(self.request, f"خطا در بستن معامله: {e}")
            return self.form_invalid(form)
            
        return HttpResponseRedirect(self.get_success_url())


class OpenTradesListView(LoginRequiredMixin, ListView):
    """
    This view displays a list of all open derivative trades for the logged-in user.
    """
    model = Trade
    template_name = 'open_trades_list.html'  # The template that will display the list
    context_object_name = 'open_trades'  # The name of the variable in the template

    def get_queryset(self):
        """
        Override this method to filter trades for the current user and only show OPEN ones.
        """
        user_trading_accounts = TradingAccount.objects.filter(user=self.request.user)
        return Trade.objects.filter(
            trading_account__in=user_trading_accounts,
            status=Trade.OPEN
        ).order_by('-entry_date')

class OpenTradeView(LoginRequiredMixin, CreateView):
    """
    این ویو صفحه باز کردن یک معامله مشتقه جدید را مدیریت می‌کند.
    """
    model = Trade
    form_class = OpenTradeForm
    template_name = 'add_trade.html' # می‌توانید از همان تمپلیت قبلی استفاده کنید
    success_url = reverse_lazy('open_trades_list') # کاربر را به لیست معاملات باز هدایت می‌کند

    def get_form_kwargs(self):
        """
        کاربر لاگین کرده را به فرم پاس می‌دهد تا دراپ‌داون‌ها فیلتر شوند.
        """
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def form_valid(self, form):
        """
        این متد بازنویسی شده تا تابع سرویس 'open_trade' را فراخوانی کند.
        """
        try:
            data = form.cleaned_data
            
            # 🚀 فراخوانی سرویس برای باز کردن معامله 🚀
            self.object = open_trade(
                trading_account=data['trading_account'],
                asset=data['asset'],
                side=data['position_side'],
                quantity=data['quantity'],
                entry_price=data['entry_price']
            )
            
            messages.success(self.request, f"معامله {self.object.asset.symbol} با موفقیت باز شد.")

        except ValueError as e:
            form.add_error(None, str(e))
            return self.form_invalid(form)
            
        return HttpResponseRedirect(self.get_success_url())
class DashboardView(LoginRequiredMixin, TemplateView):
    template_name = 'index.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user

        # Get user's trading accounts
        trading_accounts = TradingAccount.objects.filter(user=user)
        context['trading_accounts'] = trading_accounts

        # Get ChartOfAccount instances linked to these trading accounts
        user_chart_of_accounts = ChartOfAccount.objects.filter(trading_account__in=trading_accounts)

        # Get the last 5 journal entry lines related to these accounts
        recent_transactions = JournalEntryLine.objects.filter(
            account__in=user_chart_of_accounts
        ).order_by('-journal_entry__entry_date', '-journal_entry__id').select_related('journal_entry', 'account')[:5]
        
        context['recent_transactions'] = recent_transactions

        return context

class FundManagementView(LoginRequiredMixin, TemplateView):
    template_name = 'funds.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['trading_accounts'] = TradingAccount.objects.filter(user=self.request.user)
        return context

class DepositView(View):
    def get(self, request, *args, **kwargs):
        return redirect('fund_management')

    def post(self, request, *args, **kwargs):
        trading_account_id = request.POST.get('trading_account_id')
        amount = request.POST.get('amount')
        description = request.POST.get('description', 'Capital Deposit via UI')

        try:
            trading_account = TradingAccount.objects.get(id=trading_account_id, user=request.user)
            make_deposit(
                trading_account=trading_account,
                amount=float(amount),
                description=description,
                user=request.user
            )
            messages.success(request, 'Deposit successful!')
            return redirect('dashboard')
        except TradingAccount.DoesNotExist:
            messages.error(request, 'Trading account not found.')
        except ValueError as e:
            messages.error(request, f'Deposit failed: {e}')
        except Exception as e:
            messages.error(request, f'An unexpected error occurred: {e}')
        
        return redirect('fund_management')

from decimal import Decimal

class WithdrawView(View):
    def get(self, request, *args, **kwargs):
        return redirect('fund_management')

    def post(self, request, *args, **kwargs):
        trading_account_id = request.POST.get('trading_account_id')
        amount = request.POST.get('amount')
        description = request.POST.get('description', 'Capital Withdrawal via UI')

        try:
            trading_account = TradingAccount.objects.get(id=trading_account_id, user=request.user)
            make_withdrawal(
                trading_account=trading_account,
                amount=float(amount),
                description=description,
                user=request.user
            )
            messages.success(request, 'Withdrawal successful!')
            return redirect('dashboard')
        except TradingAccount.DoesNotExist:
            messages.error(request, 'Trading account not found.')
        except ValueError as e:
            messages.error(request, f'Withdrawal failed: {e}')
        except Exception as e:
            messages.error(request, f'An unexpected error occurred: {e}')
        
        return redirect('fund_management')

class DepositSpotAssetView(View):
    def post(self, request, *args, **kwargs):
        try:
            trading_account_id = request.POST.get('trading_account_id')
            asset_id = request.POST.get('asset_id')
            quantity = Decimal(request.POST.get('quantity'))
            price_usd = Decimal(request.POST.get('price_usd'))
            description = request.POST.get('description', 'Spot Asset Deposit via UI')

            trading_account = get_object_or_404(TradingAccount, id=trading_account_id, user=request.user)
            asset = get_object_or_404(Asset, id=asset_id)

            deposit_spot_asset(
                trading_account=trading_account,
                asset=asset,
                quantity=quantity,
                price_usd=price_usd,
                description=description,
                user=request.user
            )
            messages.success(request, 'Spot asset deposited successfully!')
        except (ValueError, TypeError, TradingAccount.DoesNotExist, Asset.DoesNotExist) as e:
            messages.error(request, f'Failed to deposit spot asset: {e}')
        except Exception as e:
            messages.error(request, f'An unexpected error occurred: {e}')
        return redirect('trade_assets')

class WithdrawSpotAssetView(View):
    def post(self, request, *args, **kwargs):
        try:
            trading_account_id = request.POST.get('trading_account_id')
            asset_id = request.POST.get('asset_id')
            quantity = Decimal(request.POST.get('quantity'))
            price_usd = Decimal(request.POST.get('price_usd'))
            description = request.POST.get('description', 'Spot Asset Withdrawal via UI')

            trading_account = get_object_or_404(TradingAccount, id=trading_account_id, user=request.user)
            asset = get_object_or_404(Asset, id=asset_id)

            withdraw_spot_asset(
                trading_account=trading_account,
                asset=asset,
                quantity=quantity,
                price_usd=price_usd,
                description=description,
                user=request.user
            )
            messages.success(request, 'Spot asset withdrawn successfully!')
        except (ValueError, TypeError, TradingAccount.DoesNotExist, Asset.DoesNotExist) as e:
            messages.error(request, f'Failed to withdraw spot asset: {e}')
        except Exception as e:
            messages.error(request, f'An unexpected error occurred: {e}')
        return redirect('trade_assets')

class TradeView(View):
    def get(self, request, *args, **kwargs):
        trading_accounts = TradingAccount.objects.filter(user=request.user)
        assets = Asset.objects.all()
        spot_assets = assets.filter(asset_type=Asset.SPOT)
        derivative_assets = assets.filter(asset_type=Asset.DERIVATIVE)
        return render(request, 'trade.html', {
            'trading_accounts': trading_accounts, 
            'assets': assets,
            'spot_assets': spot_assets,
            'derivative_assets': derivative_assets
        })

class TradeBuyView(View):
    def post(self, request, *args, **kwargs):
        trading_account_id = request.POST.get('trading_account_id')
        asset_id = request.POST.get('asset_id')
        quantity = request.POST.get('quantity')
        trade_cost = request.POST.get('trade_cost')
        description = request.POST.get('description', 'Spot Buy via UI')

        try:
            trading_account = TradingAccount.objects.get(id=trading_account_id, user=request.user)
            asset = Asset.objects.get(id=asset_id)
            execute_spot_buy(
                trading_account=trading_account,
                asset=asset,
                quantity=Decimal(quantity),
                trade_cost=Decimal(trade_cost),
                description=description,
                user=request.user
            )
            messages.success(request, 'Buy order executed successfully!')
            return redirect('trade_assets')
        except TradingAccount.DoesNotExist:
            messages.error(request, 'Trading account not found.')
        except Asset.DoesNotExist:
            messages.error(request, 'Asset not found.')
        except ValueError as e:
            messages.error(request, f'Buy order failed: {e}')
        except Exception as e:
            messages.error(request, f'An unexpected error occurred: {e}')
        
        trading_accounts = TradingAccount.objects.filter(user=request.user)
        assets = Asset.objects.all()
        return render(request, 'trade.html', {'trading_accounts': trading_accounts, 'assets': assets})

class TradeSellView(View):
    def post(self, request, *args, **kwargs):
        trading_account_id = request.POST.get('trading_account_id')
        asset_id = request.POST.get('asset_id')
        quantity = request.POST.get('quantity')
        trade_cost = request.POST.get('trade_cost')
        description = request.POST.get('description', 'Spot Sell via UI')

        try:
            trading_account = TradingAccount.objects.get(id=trading_account_id, user=request.user)
            asset = Asset.objects.get(id=asset_id)
            execute_spot_sell(
                trading_account=trading_account,
                asset=asset,
                quantity=Decimal(quantity),
                sale_proceeds=Decimal(trade_cost),
                description=description,
                user=request.user
            )
            messages.success(request, 'Sell order executed successfully!')
            return redirect('trade_assets')
        except TradingAccount.DoesNotExist:
            messages.error(request, 'Trading account not found.')
        except Asset.DoesNotExist:
            messages.error(request, 'Asset not found.')
        except ValueError as e:
            messages.error(request, f'Sell order failed: {e}')
        except Exception as e:
            messages.error(request, f'An unexpected error occurred: {e}')
        
        trading_accounts = TradingAccount.objects.filter(user=request.user)
        assets = Asset.objects.all()
        return render(request, 'trade.html', {'trading_accounts': trading_accounts, 'assets': assets})

class HistoryView(LoginRequiredMixin, TemplateView):
    template_name = 'history.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user

        # Fetch Journal Entries related to the user's trading accounts
        user_trading_accounts = TradingAccount.objects.filter(user=user)
        
        # Get the ChartOfAccount instances linked to these trading accounts
        user_chart_of_accounts = ChartOfAccount.objects.filter(trading_account__in=user_trading_accounts)

        # Get the journal entries from these accounts
        context['journal_entries'] = JournalEntry.objects.filter(
            journalentryline__account__in=user_chart_of_accounts
        ).distinct().order_by('-entry_date', '-id').prefetch_related('journalentryline_set__account')
        
        # Fetch Closed Trades related to the user's trading accounts
        context['all_trades'] = Trade.objects.filter(
            trading_account__in=user_trading_accounts
        ).order_by('-entry_date').select_related('asset', 'trading_account')

        context['title'] = 'Transaction History'
        return context

class LoginView(View):
    def get(self, request):
        return render(request, 'login.html')

    def post(self, request):
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            messages.success(request, f'Welcome, {username}!')
            return redirect('dashboard')
        else:
            messages.error(request, 'Invalid username or password.')
            return render(request, 'login.html')

def logout_view(request):
    logout(request)
    messages.info(request, 'You have been logged out.')
    return redirect('login')
class CreateTradingAccountView(LoginRequiredMixin, FormView):
    """
    این ویو صفحه ساخت حساب معاملاتی جدید را مدیریت می‌کند.
    """
    template_name = 'create_trading_account.html'
    form_class = TradingAccountForm
    success_url = reverse_lazy('dashboard') # نام URL داشبورد خود را اینجا قرار دهید

    def form_valid(self, form):
        """
        این متد زمانی اجرا می‌شود که کاربر فرم را با داده‌های معتبر ارسال کند.
        اینجا بهترین مکان برای فراخوانی سرویس ماست.
        """
        try:
            # داده‌های تمیز شده فرم را استخراج می‌کنیم
            data = form.cleaned_data
            
            # 🚀 فراخوانی صریح تابع سرویس 🚀
            # به جای ذخیره مستقیم مدل، منطق کسب‌وکار را از سرویس صدا می‌زنیم
            create_trading_account(
                user=self.request.user,
                name=data['name'],
                account_type=data['account_type'],
                account_purpose=data['account_purpose']
            )
            
            # ارسال پیام موفقیت‌آمیز (اختیاری)
            # messages.success(self.request, "حساب معاملاتی جدید با موفقیت ایجاد شد.")
            
        except Exception as e:
            # اگر تابع سرویس ما با خطا مواجه شود، آن را به کاربر نمایش می‌دهیم
            form.add_error(None, f"خطا در ایجاد حساب: {e}")
            return self.form_invalid(form)
            
        # در صورت موفقیت، کاربر را به آدرس success_url هدایت می‌کنیم
        return HttpResponseRedirect(self.get_success_url())

class ChartOfAccountsView(TemplateView):
    template_name = 'chart_of_accounts.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.request.user.is_authenticated:
            trading_accounts = TradingAccount.objects.filter(user=self.request.user)
            context['trading_accounts'] = trading_accounts

            selected_account_id = self.request.GET.get('trading_account_id')
            if selected_account_id:
                try:
                    selected_account = TradingAccount.objects.get(id=selected_account_id, user=self.request.user)
                    context['selected_account'] = selected_account
                    context['chart_of_accounts'] = ChartOfAccount.objects.filter(
                        trading_account=selected_account
                    ).order_by('account_number')
                except TradingAccount.DoesNotExist:
                    messages.error(self.request, 'Selected trading account not found.')
            
        return context

class IncomeStatementView(TemplateView):
    template_name = 'income_statement.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.request.user.is_authenticated:
            trading_accounts = TradingAccount.objects.filter(user=self.request.user)
            context['trading_accounts'] = trading_accounts

            selected_account_id = self.request.GET.get('trading_account_id')
            start_date_str = self.request.GET.get('start_date')
            end_date_str = self.request.GET.get('end_date')

            if selected_account_id and start_date_str and end_date_str:
                try:
                    selected_account = TradingAccount.objects.get(id=selected_account_id, user=self.request.user)
                    start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
                    end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
                    
                    report_data = generate_income_statement(selected_account, start_date, end_date)
                    context['report_data'] = report_data
                    context['selected_account'] = selected_account
                    context['start_date'] = start_date
                    context['end_date'] = end_date

                except TradingAccount.DoesNotExist:
                    messages.error(self.request, 'Selected trading account not found.')
                except ValueError:
                    messages.error(self.request, 'Invalid date format. Please use YYYY-MM-DD.')
                except Exception as e:
                    messages.error(self.request, f'Error generating report: {e}')

        return context



class DeleteTradingAccountView(View):
    def get(self, request, pk):
        trading_account = get_object_or_404(TradingAccount, pk=pk, user=request.user)
        return render(request, 'delete_trading_account.html', {'trading_account': trading_account})

    def post(self, request, pk):
        trading_account = get_object_or_404(TradingAccount, pk=pk, user=request.user)
        try:
            trading_account.delete()
            messages.success(request, f'Trading account "{trading_account.name}" deleted successfully.')
            return redirect('dashboard')
        except Exception as e:
            messages.error(request, f'Error deleting trading account: {e}')
            return render(request, 'delete_trading_account.html', {'trading_account': trading_account})

class CalculateUnrealizedPnLView(View):
    def get(self, request):
        return render(request, 'unrealized_pnl.html')

    def post(self, request):
        try:
            calculate_unrealized_pnl(user=request.user)
            messages.success(request, 'Unrealized PnL calculated and posted successfully!')
        except Exception as e:
            messages.error(request, f'Error calculating Unrealized PnL: {e}')
        return redirect('unrealized_pnl_view') # Redirect back to the same page or dashboard

class TransferFundsView(View):
    def get(self, request):
        trading_accounts = TradingAccount.objects.filter(user=request.user)
        return render(request, 'transfer_funds.html', {'trading_accounts': trading_accounts})

    def post(self, request):
        from_account_id = request.POST.get('from_trading_account_id')
        to_account_id = request.POST.get('to_trading_account_id')
        amount = request.POST.get('amount')

        try:
            from_account = TradingAccount.objects.get(id=from_account_id, user=request.user)
            to_account = TradingAccount.objects.get(id=to_account_id, user=request.user)
            
            transfer_funds_between_accounts(
                from_trading_account=from_account,
                to_trading_account=to_account,
                amount=float(amount),
                user=request.user
            )
            messages.success(request, 'Funds transferred successfully!')
            return redirect('transfer_funds') # Redirect back to the same page or dashboard
        except TradingAccount.DoesNotExist:
            messages.error(request, 'One or both trading accounts not found.')
        except ValueError as e:
            messages.error(request, f'Transfer failed: {e}')
        except Exception as e:
            messages.error(request, f'An unexpected error occurred: {e}')
        
        trading_accounts = TradingAccount.objects.filter(user=request.user)
        return render(request, 'transfer_funds.html', {'trading_accounts': trading_accounts})

class RecordExpenseView(LoginRequiredMixin, FormView):
    template_name = 'record_expense.html'
    form_class = ExpenseForm
    success_url = reverse_lazy('transaction_history')

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def form_valid(self, form):
        data = form.cleaned_data
        try:
            record_expense(
                trading_account=data['trading_account'],
                expense_account=data['expense_account'],
                amount=data['amount'],
                description=data['description'] or 'Expense',
                user=self.request.user,
            )
            messages.success(self.request, 'Expense recorded successfully!')
            return super().form_valid(form)
        except ValueError as e:
            messages.error(self.request, f'Failed to record expense: {e}')
            return self.form_invalid(form)

# --- Currency CRUD Views ---

class CurrencyListView(ListView):
    model = Currency
    template_name = 'currency_list.html'
    context_object_name = 'currencies'

class CurrencyCreateView(CreateView):
    model = Currency
    template_name = 'currency_form.html'
    fields = ['code', 'name']
    success_url = reverse_lazy('currency_list')

class CurrencyUpdateView(UpdateView):
    model = Currency
    template_name = 'currency_form.html'
    fields = ['code', 'name']
    success_url = reverse_lazy('currency_list')

class CurrencyDeleteView(DeleteView):
    model = Currency
    template_name = 'currency_confirm_delete.html'
    success_url = reverse_lazy('currency_list')

# --- Asset CRUD Views ---

class AssetListView(ListView):
    model = Asset
    template_name = 'asset_list.html'
    context_object_name = 'assets'

class AssetCreateView(CreateView):
    model = Asset
    template_name = 'asset_form.html'
    fields = ['symbol', 'name', 'asset_type']
    success_url = reverse_lazy('asset_list')

class AssetUpdateView(UpdateView):
    model = Asset
    template_name = 'asset_form.html'
    fields = ['symbol', 'name', 'asset_type']
    success_url = reverse_lazy('asset_list')

class AssetDeleteView(DeleteView):
    model = Asset
    template_name = 'asset_confirm_delete.html'
    success_url = reverse_lazy('asset_list')

# --- Chart of Account CRUD Views ---

class ChartOfAccountListView(ListView):
    model = ChartOfAccount
    template_name = 'chartofaccount_list.html'
    context_object_name = 'accounts'

class ChartOfAccountCreateView(CreateView):
    model = ChartOfAccount
    template_name = 'chartofaccount_form.html'
    fields = ['account_number', 'account_name', 'account_name_fa', 'account_type', 'parent_account', 'is_active', 'trading_account']
    success_url = reverse_lazy('chartofaccount_list')

class ChartOfAccountUpdateView(UpdateView):
    model = ChartOfAccount
    template_name = 'chartofaccount_form.html'
    fields = ['account_number', 'account_name', 'account_name_fa', 'account_type', 'parent_account', 'is_active', 'trading_account']
    success_url = reverse_lazy('chartofaccount_list')


class BalanceSheetView(LoginRequiredMixin, TemplateView):
    template_name = 'balance_sheet.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        trading_accounts = TradingAccount.objects.filter(user=user)
        context['trading_accounts'] = trading_accounts

        selected_account_id = self.request.GET.get('trading_account_id')
        if selected_account_id:
            selected_account = get_object_or_404(TradingAccount, id=selected_account_id, user=user)
            context['selected_account'] = selected_account
            context['report_date'] = timezone.now()

            # --- شروع منطق جدید و اصلاح شده ---

            # ۱. دریافت تمام حساب‌های مربوط به این حساب معاملاتی
            accounts = ChartOfAccount.objects.filter(trading_account=selected_account)

            # ۲. محاسبه موجودی برای هر حساب به صورت بهینه
            # ما یک دیکشنری برای نگهداری موجودی‌ها می‌سازیم
            account_balances = {}
            lines = JournalEntryLine.objects.filter(account__in=accounts)

            # محاسبه مجموع بدهکار و بستانکار برای همه حساب‌ها در یک کوئری
            balances_data = lines.values('account_id').annotate(
                total_debit=Sum('debit_amount'),
                total_credit=Sum('credit_amount')
            )

            for balance_info in balances_data:
                account_balances[balance_info['account_id']] = {
                    'debit': balance_info['total_debit'] or 0,
                    'credit': balance_info['total_credit'] or 0
                }

            # ۳. دسته‌بندی حساب‌ها و تزریق موجودی محاسبه شده به هر حساب
            asset_accounts = []
            liability_accounts = []
            equity_accounts = []
            
            for acc in accounts:
                balance_info = account_balances.get(acc.id, {'debit': 0, 'credit': 0})
                debit_total = balance_info['debit']
                credit_total = balance_info['credit']

                # محاسبه موجودی نهایی بر اساس نوع حساب
                if acc.account_type in [ASSET, EXPENSE]:
                    acc.balance = debit_total - credit_total
                else: # LIABILITY, EQUITY, REVENUE
                    acc.balance = credit_total - debit_total

                # اضافه کردن به لیست مربوطه
                if acc.account_type == ASSET:
                    asset_accounts.append(acc)
                elif acc.account_type == LIABILITY:
                    liability_accounts.append(acc)
                elif acc.account_type == EQUITY:
                    equity_accounts.append(acc)

            # ۴. محاسبه مجموع کل
            total_assets = sum(acc.balance for acc in asset_accounts)
            total_liabilities = sum(acc.balance for acc in liability_accounts)
            total_equity = sum(acc.balance for acc in equity_accounts)
            # --- پایان منطق جدید ---

            context['asset_accounts'] = asset_accounts
            context['liability_accounts'] = liability_accounts
            context['equity_accounts'] = equity_accounts
            context['total_assets'] = total_assets
            context['total_liabilities'] = total_liabilities
            context['total_equity'] = total_equity
            context['total_liabilities_and_equity'] = total_liabilities + total_equity

        return context

from django.core.serializers.json import DjangoJSONEncoder
import json

class TrialBalanceView(LoginRequiredMixin, TemplateView):
    template_name = 'trial_balance.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        trading_accounts = TradingAccount.objects.filter(user=user)
        context['trading_accounts'] = trading_accounts

        selected_account_id = self.request.GET.get('trading_account_id')
        if selected_account_id:
            selected_account = get_object_or_404(TradingAccount, id=selected_account_id, user=user)
            context['selected_account'] = selected_account

            accounts = ChartOfAccount.objects.filter(trading_account=selected_account).prefetch_related('journalentryline_set__journal_entry')
            
            account_details = {}
            for acc in accounts:
                lines = acc.journalentryline_set.all()
                total_debit = lines.aggregate(Sum('debit_amount'))['debit_amount__sum'] or 0
                total_credit = lines.aggregate(Sum('credit_amount'))['credit_amount__sum'] or 0
                
                balance = 0
                if acc.account_type in [ASSET, EXPENSE]:
                    balance = total_debit - total_credit
                else: # LIABILITY, EQUITY, REVENUE
                    balance = total_credit - total_debit

                # Serialize the lines into a list of dictionaries
                lines_data = []
                for line in lines:
                    lines_data.append({
                        'date': line.journal_entry.entry_date.strftime('%Y-%m-%d'),
                        'description': line.journal_entry.description,
                        'debit': str(line.debit_amount),
                        'credit': str(line.credit_amount)
                    })

                account_details[acc.id] = {
                    'object': acc,
                    'debit': total_debit,
                    'credit': total_credit,
                    'balance': balance,
                    'lines_json': json.dumps(lines_data, cls=DjangoJSONEncoder), # Pass a JSON string
                    'children': []
                }

            # Build the hierarchy
            root_accounts = []
            for acc_id, details in account_details.items():
                parent_id = details['object'].parent_account_id
                if parent_id in account_details:
                    account_details[parent_id]['children'].append(details)
                else:
                    root_accounts.append(details)

            context['root_accounts'] = root_accounts

        return context

class ChartOfAccountDeleteView(DeleteView):
    model = ChartOfAccount
    template_name = 'chartofaccount_confirm_delete.html'
    success_url = reverse_lazy('chartofaccount_list')

class SpotAssetListView(LoginRequiredMixin, TemplateView):
    template_name = 'spot_asset_list.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        
        # Get all asset lots for the user, grouped by trading account
        asset_lots = AssetLot.objects.filter(trading_account__user=user).select_related('asset', 'trading_account')

        # Process the lots to group them by asset
        spot_assets = {}
        for lot in asset_lots:
            if lot.asset.symbol not in spot_assets:
                spot_assets[lot.asset.symbol] = {
                    'name': lot.asset.name,
                    'lots': [],
                    'total_quantity': 0,
                    'total_cost': 0,
                }
            
            spot_assets[lot.asset.symbol]['lots'].append(lot)
            spot_assets[lot.asset.symbol]['total_quantity'] += lot.remaining_quantity
            spot_assets[lot.asset.symbol]['total_cost'] += lot.remaining_quantity * lot.purchase_price_usd

        # Calculate the weighted average price for each asset
        for symbol, data in spot_assets.items():
            if data['total_quantity'] > 0:
                data['average_price'] = data['total_cost'] / data['total_quantity']
            else:
                data['average_price'] = 0

        context['spot_assets'] = spot_assets
        return context
