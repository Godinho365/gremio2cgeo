"""Paginação padrão da API.

`page_size_query_param` existe para telas que precisam da lista inteira em um
seletor (ex.: escolher o responsável por uma cautela) sem truncar em silêncio.
"""
from __future__ import annotations

from rest_framework.pagination import PageNumberPagination


class DefaultPagination(PageNumberPagination):
    page_size = 25
    page_size_query_param = "page_size"
    max_page_size = 200
