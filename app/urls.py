from django.urls import path
from . import views

urlpatterns = [
    # Frontend page
    path('', views.index, name='index'),

    # API endpoints pentru pașii proiectului
    path('api/rdf4j-data/', views.get_rdf4j_data, name='get_rdf4j_data'),
    path('api/transfer-to-json-server/', views.transfer_to_json_server, name='transfer_to_json_server'),
    path('api/json-server-data/', views.get_json_server_data, name='get_json_server_data'),
    path('api/add-to-graphql/', views.add_to_graphql_server, name='add_to_graphql_server'),
    path('api/graphql-data/', views.get_graphql_data, name='get_graphql_data'),

    path('api/test-servers/', views.test_servers, name='test_servers'),
]