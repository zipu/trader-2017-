from django.views.generic.base import TemplateView
from django.views.decorators.csrf import ensure_csrf_cookie
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from django.shortcuts import render
from django.http import JsonResponse
from django.core import serializers

#from channels import Channel
import json

from trading.models import Product

decorators = [login_required, ensure_csrf_cookie]

@method_decorator(decorators, name='dispatch')
class MarketView(TemplateView):
    template_name = 'marketapp/market.html'
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['markets'] = list(set(Product.objects.all().values_list("market", flat=True)))
        return context
    
    def get(self, request, *args, **kwargs):
        # ajax로 상품 기본 정보 전달
        # 브라우저에서 localStroage.getItem("products") 로 받아서 쓸 수 있음
        if request.is_ajax():
            if request.GET.get('action') == 'init':
                data = serializers.serialize("json", Product.objects.all())
                markets = set(Product.objects.all().values_list("market", flat=True))
                response = dict(FAV={})
    
                for mkt in markets:
                    grp = serializers.serialize("json", Product.objects.filter(market=mkt))
                    response[mkt] = dict()
                    for product in json.loads(grp):
                        response[mkt][product['pk']] = product['fields']
                        if product['fields']['is_favorite']:
                            response['FAV'][product['pk']] = product['fields']
    
                return JsonResponse(response)

        return super(MarketView, self).get(request, *args, **kwargs)
