from collections import defaultdict
import json
from datetime import datetime

from django.views.generic.base import TemplateView
from django.views.generic.list import ListView
from django.shortcuts import render, redirect
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import ensure_csrf_cookie
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.core import serializers
from django.contrib import messages
from django.core.exceptions import ObjectDoesNotExist
from django.db.models import Sum

from .models import Product, Entry, Exit, Game, EntryForm, GameForm, ExitForm\
                    ,Account, Code, Equity


decorators = [login_required, ensure_csrf_cookie]

@method_decorator(decorators, name='dispatch')
class Home(TemplateView):
    template_name = 'home.html'

    def get_context_data(self, **kwargs):
        """ 차트 데이터 가공
        변동성: |평가손익(오늘) - 평가손익(어제)|/(원금 + 손익) * 100
        """
        context = super().get_context_data(**kwargs)
        # source data 가공하기
        queryset= Equity.objects.all().order_by('date')
        equity = defaultdict(list)
        total_y = 0 #변동성 계산용
        for idx, item in enumerate(queryset):
            date = datetime.combine(item.date, datetime.min.time()).timestamp()*1000 + idx
            principal = float(item.principal)
            profit = float(item.profit)
            profit_estim = float(item.estimated_profit)
            total = principal + profit + profit_estim
            volatility = abs((total-total_y)/total)*100 if total > 0 else 0
            
            total_y = total     
            
            equity['principal'].append([date, principal])
            equity['profit'].append([date, profit])
            equity['profit_estim'].append([date, profit_estim])
            equity['volatility'].append([date, volatility])
        
        context['equity'] = dict(equity)
        return context

@method_decorator(decorators, name='dispatch')
class TradingView(ListView):
    """
     매매기록과 미결제 약정을 볼 수 있는 페이지
    """
    model = Game
    template_name = 'trading/record.html'
    context_object_name = 'games'
    paginate_by = 30
    queryset = Game.objects.filter(is_completed=True).order_by('-id')
    #ordering = ['-id']

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['open_game'] = Game.objects.filter(is_completed=False)
        return context

    def get(self, request, *args, **kwargs):
        # modal 화면 ajax call
        if request.is_ajax():
            if request.GET.get('action') == 'init':
                #data = serializers.serialize("json", Product.objects.all())
                markets = list(Product.objects.all().values_list("name", flat=True))
                return JsonResponse({'product_list':markets})

            else:
                game_id = request.GET.get('id')
                context_data = self.get_game_detail_context(game_id)
                return JsonResponse(context_data)

        return super(TradingView, self).get(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        formtype = request.POST.get('form_type')
        if formtype == 'new_game':
            form = GameForm(request.POST)
            if form.is_valid():
                pname = form.cleaned_data['name']
                if not Product.objects.filter(name=pname).exists():
                    msg = pname + " is Not registered in DB"
                    messages.add_message(request, messages.WARNING, msg)
                else:
                    game = form.save(commit=False)
                    game.product = Product.objects.get(name=pname)
                    game.save()
            else:
                msg = "Form is NOT valid"
                messages.add_message(request, messages.WARNING, msg)

        elif formtype == 'delete_game':
            if 'id' in request.POST:
                try:
                    game = Game.objects.get(pk=request.POST.get('id'))
                    game.delete()
                except ObjectDoesNotExist:
                    print("Game doesn't exist")
                    msg = "Game doesn't exist"
                    messages.add_message(request, messages.WARNING, msg)
            else:
                msg = "Form is NOT valid ('ID' attribute not in the form)"
                messages.add_message(request, messages.WARNING, msg)

        elif formtype == 'save_entry':
            form = EntryForm(request.POST)
            if form.is_valid():
                game = Game.objects.get(pk=request.POST.get('game_id'))

                if form.cleaned_data['entry_price'] < 0 or form.cleaned_data['loss_cut'] < 0:
                    msg = "Price must be positive number"

                elif (form.cleaned_data['entry_price']-form.cleaned_data['loss_cut'])*game.position <= 0:
                    pos = "smaller" if game.position else "greater"
                    msg = "Loss cut must be %s than entry price"%pos

                #elif game.entry_set.count() and \
                #     form.cleaned_data['entry_date'] < game.entry_set.order_by('-entry_date')[0].entry_date:
                #    msg = "Entry date must be newest"

                else:
                    entry = form.save(commit=False)
                    entry.game = Game.objects.get(pk=request.POST.get('game_id'))
                    entry.code = Code.objects.get(code=request.POST.get('code'))
                    entry.save()
                    data = self.get_game_detail_context(entry.game.id)
                    return JsonResponse({'succeed': True, 'data': data})
            else:
                msg = 'Form is not valid'

            return JsonResponse({'succeed': False, 'msg': msg})

        elif formtype == 'delete_entry':
            if 'id' in request.POST:
                try:
                    entry = Entry.objects.get(pk=request.POST.get('id'))
                    entry.delete()
                    entry.game.save()
                    succeed = True
                    data = self.get_game_detail_context(entry.game.id)
                except ObjectDoesNotExist:
                    print("Game doesn't exist")
                    succeed = False
                    data = 'No mathcing entry found'
            else:
                succeed = False
                data = "Form is NOT valid ('ID' attribute not in the form)"

            return JsonResponse({'succeed': succeed, 'data': data})

        elif formtype == 'new_exit':
            form = ExitForm(request.POST)
            if form.is_valid():

                game = Game.objects.get(pk=request.POST.get('game_id'))
                entry = game.entry_set.get(pk=request.POST.get('entry_id'))
                # 진입매매당 청산된 총 계약수
                cons = entry.exit_set.aggregate(sum=Sum('contracts')).get('sum') 
                cons = cons if cons else 0
                if request.POST.get('exit_id'):
                    exit = Exit.objects.get(pk=request.POST.get('exit_id'))
                    cons = cons - exit.contracts

                if form.cleaned_data['exit_price'] < 0:
                    succeed = False
                    data = "Price must be positive number"

                elif form.cleaned_data['contracts'] + cons > entry.contracts:
                    succeed = False
                    data = "Total contracts can NOT be greater than %s (current: %s)"%(entry.contracts, cons)


                elif 'exit' in locals():
                    exit.exit_price = form.cleaned_data['exit_price']
                    exit.contracts = form.cleaned_data['contracts']
                    exit.exit_date = form.cleaned_data['exit_date']
                    exit.save()
                    exit.game.save()
                    succeed = True
                    data = self.get_game_detail_context(game.id)

                else:
                    exit = form.save(commit=False)
                    exit.game = Game.objects.get(pk=request.POST.get('game_id'))
                    exit.entry = entry
                    exit.save()
                    exit.game.save()
                    succeed = True
                    data = self.get_game_detail_context(game.id)
            else:
                succeed = False
                data = 'Form is not valid'

            return JsonResponse({'succeed': succeed, 'data': data})

        elif formtype == 'delete_exit':
            if 'id' in request.POST:
                try:
                    exit = Exit.objects.get(pk=request.POST.get('id'))
                    exit.delete()
                    exit.game.save()
                    succeed = True
                    data = self.get_game_detail_context(exit.game.id)

                except ObjectDoesNotExist:
                    print("Game doesn't exist")
                    succeed = False
                    data = 'No mathcing entry found'
            else:
                succeed = False
                data = "Form is NOT valid ('ID' attribute not in the form)"

            return JsonResponse({'succeed': succeed, 'data': data})

        elif formtype == 'game_complete':
            if 'id' in request.POST:
                try:
                    game = Game.objects.get(pk=request.POST.get('id'))
                    flag = True if request.POST.get('is_completed') == 'true' else False
                    game.is_completed = flag
                    game.save()
                    succeed = True
                    data = "game completion state changed"

                except ObjectDoesNotExist:
                    print("Game doesn't exist")
                    succeed = False
                    data = 'No mathcing entry found'
            else:
                succeed = False
                data = "Form is NOT valid ('ID' attribute not in the form)"

            return JsonResponse({'succeed': succeed, 'data': data})

        return redirect('record')

    def get_game_detail_context(self, game_id):
        """ game row 클릭시 열리는  modal 화면 context data"""
        game = Game.objects.filter(pk=game_id)
        #codes = list(game[0].product.code_set.order_by('month').values_list('code', flat=True))
        entries = game[0].entry_set.all()
        exits = game[0].exit_set.all()
        if game[0].product:
            codes = list(game[0].product.code_set.order_by('month').values_list('code', flat=True))
        else:
            codes = []
        
        context = dict(
            info=game.values()[0],
            codes = codes,
            entries=[entry for entry in entries.values()],
            exits=[ex for ex in exits.values()]
        )
        return context




class AccountView(ListView):
    """
     매매기록과 미결제 약정을 볼 수 있는 페이지
    """
    model = Account
    template_name = 'trading/account.html'
    context_object_name = 'account'
    paginate_by = 15
    queryset = Account.objects.order_by('-date')
    #ordering = ['-id']

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['total'] = Account.objects.all().aggregate(
            krw=Sum('krw'),
            usd=Sum('usd'),
            cash=Sum('cash')
        )
        return context
