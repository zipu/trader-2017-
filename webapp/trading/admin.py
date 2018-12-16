from django.contrib import admin
from .models import Product, Code, Entry, Game, Account, Exit, Equity
# Register your models here.

admin.site.register([Product, Code, Entry, Game, Account, Exit, Equity])
