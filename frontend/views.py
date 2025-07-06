from django.shortcuts import render, redirect, get_object_or_404
from django.views.generic import TemplateView, View
from core.models import TradingAccount, Asset, JournalEntry, ClosedTradesLog, ChartOfAccount
from core.services import make_deposit, make_withdrawal, execute_spot_buy, execute_spot_sell, create_trading_account, generate_income_statement, record_closed_trade, calculate_unrealized_pnl, transfer_funds_between_accounts
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from datetime import datetime

class DashboardView(TemplateView):
    template_name = 'index.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.request.user.is_authenticated:
            context['trading_accounts'] = TradingAccount.objects.filter(user=self.request.user)
        return context

class DepositView(View):
    def get(self, request, *args, **kwargs):
        trading_accounts = TradingAccount.objects.filter(user=request.user)
        return render(request, 'deposit.html', {'trading_accounts': trading_accounts})

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
        
        trading_accounts = TradingAccount.objects.filter(user=request.user)
        return render(request, 'deposit.html', {'trading_accounts': trading_accounts})

class WithdrawView(View):
    def get(self, request, *args, **kwargs):
        trading_accounts = TradingAccount.objects.filter(user=request.user)
        return render(request, 'withdraw.html', {'trading_accounts': trading_accounts})

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
        
        trading_accounts = TradingAccount.objects.filter(user=request.user)
        return render(request, 'withdraw.html', {'trading_accounts': trading_accounts})

class TradeView(View):
    def get(self, request, *args, **kwargs):
        trading_accounts = TradingAccount.objects.filter(user=request.user)
        assets = Asset.objects.all()
        return render(request, 'trade.html', {'trading_accounts': trading_accounts, 'assets': assets})

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
                quantity=float(quantity),
                trade_cost=float(trade_cost),
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
                quantity=float(quantity),
                trade_cost=float(trade_cost),
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

class HistoryView(TemplateView):
    template_name = 'history.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.request.user.is_authenticated:
            # Fetch Journal Entries related to the user's trading accounts
            user_trading_accounts = TradingAccount.objects.filter(user=self.request.user)
            context['journal_entries'] = JournalEntry.objects.filter(
                posted_by=self.request.user
            ).order_by('-entry_date').prefetch_related('journalentryline_set__account')
            
            # Fetch Closed Trades related to the user's trading accounts
            context['closed_trades'] = ClosedTradesLog.objects.filter(
                trading_account__in=user_trading_accounts
            ).order_by('-trade_date').select_related('asset', 'trading_account')

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

class CreateTradingAccountView(View):
    def get(self, request):
        return render(request, 'create_trading_account.html')

    def post(self, request):
        name = request.POST.get('name')
        account_type = request.POST.get('account_type')
        account_purpose = request.POST.get('account_purpose')

        try:
            create_trading_account(
                user=request.user,
                name=name,
                account_type=account_type,
                account_purpose=account_purpose
            )
            messages.success(request, 'Trading account created successfully!')
            return redirect('dashboard')
        except Exception as e:
            messages.error(request, f'Error creating trading account: {e}')
            return render(request, 'create_trading_account.html')

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

class AddClosedTradeView(View):
    def get(self, request):
        trading_accounts = TradingAccount.objects.filter(user=request.user)
        derivative_assets = Asset.objects.filter(asset_type=Asset.DERIVATIVE)
        return render(request, 'add_closed_trade.html', {
            'trading_accounts': trading_accounts,
            'derivative_assets': derivative_assets
        })

    def post(self, request):
        trading_account_id = request.POST.get('trading_account_id')
        asset_id = request.POST.get('asset_id')
        trade_date_str = request.POST.get('trade_date')
        net_profit_or_loss = request.POST.get('net_profit_or_loss')
        commission_fee = request.POST.get('commission_fee', 0)

        try:
            trading_account = TradingAccount.objects.get(id=trading_account_id, user=request.user)
            asset = Asset.objects.get(id=asset_id)
            trade_date = datetime.strptime(trade_date_str, '%Y-%m-%d').date()

            record_closed_trade(
                trading_account=trading_account,
                asset=asset,
                trade_date=trade_date,
                net_profit_or_loss=float(net_profit_or_loss),
                commission_fee=float(commission_fee),
                user=request.user
            )
            messages.success(request, 'Closed trade recorded successfully!')
            return redirect('transaction_history')
        except TradingAccount.DoesNotExist:
            messages.error(request, 'Trading account not found.')
        except Asset.DoesNotExist:
            messages.error(request, 'Asset not found.')
        except ValueError as e:
            messages.error(request, f'Error recording trade: {e}')
        except Exception as e:
            messages.error(request, f'An unexpected error occurred: {e}')
        
        trading_accounts = TradingAccount.objects.filter(user=request.user)
        derivative_assets = Asset.objects.filter(asset_type=Asset.DERIVATIVE)
        return render(request, 'add_closed_trade.html', {
            'trading_accounts': trading_accounts,
            'derivative_assets': derivative_assets
        })

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