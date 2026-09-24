from django.contrib import admin

from estoque.models import CategoriaItem, ItemEstoque, LoteEstoque, MovimentacaoEstoque

admin.site.register([CategoriaItem, ItemEstoque, LoteEstoque, MovimentacaoEstoque])
