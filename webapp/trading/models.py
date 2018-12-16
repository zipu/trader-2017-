from django.db import models
from django.forms import ModelForm
from django import forms
from django.db.models import Sum
from datetime import date, timedelta

# Create your models here.
class Product(models.Model):
    """ 상품 정보 """
    name = models.CharField(max_length=50, unique=True) # 상품명
    group = models.CharField(primary_key=True, max_length=30, unique=True) #그룹 코드
    market = models.CharField(max_length=10) #시장구분
    active = models.CharField(max_length=10,null=True, blank=True) #액티브 월물명
    front = models.CharField(max_length=10,null=True, blank=True) #근월물명
    activated_date = models.DateField(null=True, blank=True) #액티브 월물 변경일
    price_gap = models.DecimalField(max_digits=20, decimal_places=7, null=True, blank=True) #가격 갭 
    currency = models.CharField(max_length=10) #기준 통화
    open_margin = models.DecimalField(max_digits=10, decimal_places=2)
    keep_margin = models.DecimalField(max_digits=10, decimal_places=2)
    open_time = models.TimeField()
    close_time = models.TimeField()
    tick_unit = models.DecimalField(max_digits=20, decimal_places=7)
    tick_value = models.DecimalField(max_digits=20, decimal_places=3)
    commission = models.DecimalField(max_digits=5, decimal_places=2)
    notation = models.PositiveSmallIntegerField() # 진법
    decimal_places = models.PositiveSmallIntegerField()
    last_update = models.DateTimeField()
    is_favorite = models.BooleanField(blank=True, default=False)


    def __str__(self):
        return self.name

class Code(models.Model):
    """ 월물별 상품 정보 """
    code = models.CharField(primary_key=True, max_length=10)
    product = models.ForeignKey('Product', on_delete=models.CASCADE)
    month = models.DateField() #만기월물
    ec_price = models.DecimalField(max_digits=20, decimal_places=7) #정산가격

    def __str__(self):
        return self.code


class Game(models.Model):
    # choices
    POSITION = (
        (1, 'Long'),
        (-1, 'Short')
    )

    #계획
    pub_date = models.DateField(default=date.today)
    product = models.ForeignKey('Product', on_delete=models.PROTECT, null=True, blank=True)
    name = models.CharField(max_length=50, blank=True)
    position = models.IntegerField(choices=POSITION) #포지션

    #결과
    profit = models.DecimalField(null=True, blank=True, max_digits=20, decimal_places=3) #손익
    profit_per_contract = models.DecimalField(null=True, blank=True, max_digits=20, decimal_places=3) #단위손익
    profit_to_risk = models.DecimalField(null=True, blank=True, max_digits=10, decimal_places=2)
    commission = models.DecimalField(max_digits=5, decimal_places=2, blank=True, null=True) #수수료

    #완료
    is_completed = models.BooleanField(default=False)

    def save(self, *args, **kwargs):
        if self.product:
            self.name = self.product.name

        agg = self.exit_set.all().aggregate(
            profit=Sum('profit'),
            commission=Sum('commission'),
            ppc=Sum('profit_per_contract'),
            ptr=Sum('ptr_ratio')
        )
        self.profit = agg.get('profit') if agg.get('profit') else 0
        self.profit_per_contract = agg.get('ppc')/self.exit_set.all().count() if agg.get('ppc') else 0
        self.profit_to_risk = agg.get('ptr')/self.exit_set.all().count() if agg.get('ptr') else 0
        self.commission = agg.get('commission') if agg.get('commission') else 0
        super(Game, self).save(*args, **kwargs)

    def __str__(self):
        return self.name + " #" + str(self.id)

class Entry(models.Model):
    """ 진입 내역 """
    game = models.ForeignKey('Game', on_delete=models.CASCADE)
    code = models.ForeignKey('Code', on_delete=models.PROTECT, null=True, blank=True)
    entry_date = models.DateTimeField() #진입날짜
    contracts = models.PositiveSmallIntegerField(default=1) #계약수
    entry_price = models.DecimalField(max_digits=20, decimal_places=7) #진입가격
    loss_cut = models.DecimalField(max_digits=20, decimal_places=7) #로스컷
    plan = models.CharField(max_length=50, null=True, blank=True) #매매전략
    done = models.BooleanField(default=False)

    def __str__(self):
        return self.game.name+' #'+str(self.id)


class Exit(models.Model):
    """ 청산 내역 """
    game = models.ForeignKey('Game', on_delete=models.CASCADE, null=True, blank=True)
    entry = models.ForeignKey('Entry', on_delete=models.CASCADE, null=True, blank=True)
    exit_date = models.DateTimeField() #청산날짜
    contracts = models.PositiveSmallIntegerField(default=1) #계약수
    exit_price = models.DecimalField(max_digits=20, decimal_places=7) #청산가격

    #단위 결과
    profit = models.DecimalField(blank=True, max_digits=20, decimal_places=3) #손익
    profit_per_contract = models.DecimalField(null=True, blank=True, max_digits=20, decimal_places=3) #단위손익
    commission = models.DecimalField(max_digits=5, decimal_places=2, blank=True) #수수료
    holding_period = models.DurationField(blank=True) #보유기간
    ptr_ratio = models.DecimalField(null=True, blank=True, max_digits=10, decimal_places=2) #ptr ratio

    def save(self, *args, **kwargs):
        # 손익 계산
        if self.game and self.game.product:
            product = self.game.product
            price_diff = (self.exit_price - self.entry.entry_price) * self.game.position
            tick_diff = round(price_diff/product.tick_unit)
            risk = round(abs(self.entry.loss_cut - self.entry.entry_price)/product.tick_unit)*product.tick_value
            self.commission = product.commission * self.contracts
            self.profit_per_contract = tick_diff * product.tick_value - product.commission
            self.profit = tick_diff * self.contracts * product.tick_value - self.commission
            self.holding_period = self.exit_date - self.entry.entry_date
            self.ptr_ratio = self.profit_per_contract / risk if risk else 0
        
        if self.entry:
            exit_cons = self.entry.exit_set.aggregate(Sum('contracts'))['contracts__sum']
            exit_cons = exit_cons + self.contracts if exit_cons else self.contracts
            entry_cons = self.entry.contracts

            if entry_cons == exit_cons:
                self.entry.done = True
            elif entry_cons > exit_cons:
                self.entry.done = False
            else:
                raise ValueError("exit contracts can not be grather than entry contracts")
            self.entry.save()
        
        super(Exit, self).save(*args, **kwargs)

    def __str__(self):
        return str(self.exit_date)

class Equity(models.Model):
    date = models.DateField()
    principal = models.DecimalField(max_digits=10, decimal_places=2) #투자원금
    profit = models.DecimalField(default=0, max_digits=10, decimal_places=2) #확정손익
    estimated_profit = models.DecimalField(default=0, max_digits=10, decimal_places=2) #평가손익
    #total = models.DecimalField(max_digits=10, decimal_places=2) #총자산
    
    # equity db 업데이트
    def update_equity(self):
        self.principal = Account.objects.filter(date__lte=self.date).aggregate(Sum('usd'))['usd__sum']
        self.profit = Exit.objects.filter(exit_date__lte=self.date).aggregate(Sum('profit'))['profit__sum']
        self.estimated_profit = 0
        for entry in  Entry.objects.filter(done=False):
            product = entry.game.product
            exit_cons = entry.exit_set.aggregate(Sum('contracts'))['contracts__sum']
            contracts = entry.contracts - exit_cons if exit_cons else entry.contracts
            price_diff = (entry.code.ec_price - entry.entry_price) * entry.game.position
            tick_diff = round(price_diff/product.tick_unit)
            estim_profit = tick_diff * product.tick_value * contracts
            self.estimated_profit += estim_profit
        self.save()
    
    def __str__(self):
        return self.date.strftime("%Y-%m-%d")


class Account(models.Model):
    """
    계좌
    """
    date = models.DateField(null=True, blank=True)
    krw = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    usd = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    cash = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)

    def __str__(self):
        return str(self.date)


# Web forms
class GameForm(ModelForm):
    pub_date = forms.DateField(input_formats=['%Y-%m-%d'])
    class Meta:
        model = Game
        fields = [
            'pub_date',
            'name',
            'position',
        ]

class EntryForm(ModelForm):
    entry_date = forms.DateTimeField(input_formats=['%Y-%m-%d'])
    class Meta:
        model = Entry
        fields = [
            'entry_date',
            'entry_price',
            'contracts',
            'loss_cut',
            'plan',
        ]

class ExitForm(ModelForm):
    exit_date = forms.DateTimeField(input_formats=['%Y-%m-%d'])
    class Meta:
        model = Exit
        fields = [
            'exit_date',
            'exit_price',
            'contracts',
        ]


## Helper method #3
def recreate_equity():
    """ equity 테이블 초기생성시키는 함수"""
    dates = []
    for item in Exit.objects.all():
        dates.append(item.exit_date.date())
    dates = list(set(dates))
    dates.sort()
    for ndate in dates:
        equity = Equity()
        equity.date = ndate
        #equity, _ = Equity.objects.get_or_create(date=ndate)
        principal = Account.objects.filter(date__lte=ndate).aggregate(Sum('usd'))['usd__sum']
        equity.principal = principal if principal else 0
        profit = Exit.objects.filter(exit_date__lte=ndate).aggregate(Sum('profit'))['profit__sum']
        equity.profit = profit if profit else 0
        equity.save()