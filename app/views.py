from django.shortcuts import render
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
import requests
import json

def index(request):
    return render(request, 'index.html')


@csrf_exempt
@require_http_methods(["GET"])
def get_rdf4j_data(request):
    try:
        sparql_query = """PREFIX schema: <http://schema.org/>
        PREFIX devices: <http://example.org/devices/>

        SELECT ?categoryName ?serviceType ?deviceModel ?brand ?price ?year ?description
        WHERE {
            ?type a schema:Category ;
                  schema:name ?categoryName ;
                  schema:serviceType ?serviceType .

            ?device schema:category ?type ;
                    schema:model ?deviceModel ;
                    schema:brand ?brand ;
                    schema:price ?price ;
                    devices:manufacturingYear ?year ;
                    schema:description ?description .

            FILTER(?price < 2000)
        }
        ORDER BY ?categoryName ?price"""

        rdf4j_url = "http://localhost:8080/rdf4j-server/repositories/grafexamen"
        headers = {
            'Accept': 'application/sparql-results+json',
            'Content-Type': 'application/sparql-query'
        }

        response = requests.get(f"{rdf4j_url}?query={sparql_query}",
                                 headers=headers)

        if response.status_code == 200:
            data = response.json()
            processed_data = process_rdf4j_results(data)

            return JsonResponse({
                'success': True,
                'data': processed_data,
                'count': len(processed_data),
                'message': f'Gasite {len(processed_data)} device-uri sub 2000 lei din RDF4J'
            })
        else:
            return JsonResponse({
                'success': False,
                'error': f'Failed to fetch from RDF4J: {response.status_code}',
                'details': response.text
            }, status=500)

    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': f'RDF4J connection error: {str(e)}'
        }, status=500)

def add_cors_headers(response):
    """Adaugă CORS headers la răspuns"""
    response["Access-Control-Allow-Origin"] = "*"
    response["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS, PUT, DELETE"
    response["Access-Control-Allow-Headers"] = "Content-Type, Authorization, X-Requested-With"
    return response

@csrf_exempt
@require_http_methods(["POST"])
def transfer_to_json_server(request):
    try:
        data = json.loads(request.body)
        devices_data = data.get('data', [])

        if not devices_data:
            response = JsonResponse({
                'success': False,
                'error': 'No data provided'
            }, status=400)
            return add_cors_headers(response)

        categories = {}
        devices = []

        for item in devices_data:
            type_key = item['categoryName']

            if type_key not in categories:
                categories[type_key] = {
                    'id': len(categories) + 1,
                    'name': item['categoryName'],
                    'service_type': item['serviceType']
                }

            devices.append({
                'id': len(devices) + 1,
                'category_id': categories[type_key]['id'],
                'model': item['deviceModel'],
                'brand': item['brand'],
                'price': float(item['price']),
                'manufacturing_year': int(item.get('year', 2023)),
                'description': item.get('description', '')
            })

        json_server_url = "http://localhost:4000"

        try:
            requests.delete(f"{json_server_url}/db")
        except:
            pass

        types_sent = 0
        for category in categories.values():
            response = requests.post(f"{json_server_url}/categories",
                                     json=category,
                                     headers={'Content-Type': 'application/json'})
            if response.status_code in [200, 201]:
                types_sent += 1

        devices_sent = 0
        for device in devices:
            response = requests.post(f"{json_server_url}/devices",
                                     json=device,
                                     headers={'Content-Type': 'application/json'})
            if response.status_code in [200, 201]:
                devices_sent += 1

        return JsonResponse({
            'success': True,
            'message': f'Transfer complet: {types_sent} tipuri si {devices_sent} device-uri in JSON-Server',
            'types_count': types_sent,
            'devices_count': devices_sent
        })

    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': f'JSON-Server transfer error: {str(e)}'
        }, status=500)


@csrf_exempt
@require_http_methods(["GET"])
def get_json_server_data(request):
    try:
        json_server_url = "http://localhost:4000"

        categories_response = requests.get(f"{json_server_url}/categories")
        devices_response = requests.get(f"{json_server_url}/devices")

        if categories_response.status_code != 200 or devices_response.status_code != 200:
            return JsonResponse({
                'success': False,
                'error': 'Failed to fetch from JSON-Server',
                'categories_status': categories_response.status_code,
                'devices_status': devices_response.status_code
            }, status=500)

        categories_data = categories_response.json()
        devices_data = devices_response.json()

        filtered_devices = [d for d in devices_data if d['brand'] == 'Apple']

        unified_data = []
        for device in filtered_devices:
            category_type = next((t for t in categories_data if t['id'] == device['category_id']), None)
            if category_type:
                unified_data.append({
                    'categoryName': category_type['name'],
                    'categoryServiceType': category_type['service_type'],
                    'deviceModel': device['model'],
                    'brand': device['brand'],
                    'price': device['price'],
                    'year': device['manufacturing_year'],
                    'description': device.get('description', '')
                })

        return JsonResponse({
            'success': True,
            'data': unified_data,
            'categories': categories_data,
            'count': len(unified_data),
            'message': f'Gasite {len(unified_data)} device-uri Apple din JSON-Server'
        })

    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': f'JSON-Server read error: {str(e)}'
        }, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def add_to_graphql_server(request):
    try:
        data = json.loads(request.body)
        existing_data = data.get('existing_data', [])
        new_device = data.get('new_device', {})

        if not new_device:
            return JsonResponse({
                'success': False,
                'error': 'No new device data provided'
            }, status=400)

        all_data = existing_data.copy()
        all_data.append(new_device)

        categories = {}
        devices = []

        for item in all_data:
            type_key = item['categoryName']

            if type_key not in categories:
                categories[type_key] = {
                    'id': len(categories) + 1,
                    'name': item['categoryName'],
                    'service_type': item.get('serviceType', 'Unknow'),
                }

            devices.append({
                'id': len(devices) + 1,
                'category_name': type_key,
                'model': item['deviceModel'],
                'brand': item['brand'],
                'price': int(float(item['price'])),
                'manufacturing_year': int(item.get('year', 2024)),
                'description': item.get('description', '')
            })

        data_structure = {
            'categories': list(categories.values()),
            'devices': devices
        }

        graphql_server_url = "http://localhost:3000"

        try:
            requests.delete(f"{graphql_server_url}/reset")
        except:
            pass

        types_added = 0
        category_ids = {}
        for category in data_structure['categories']:
            mutation_payload = {
                "query": "mutation { createCategory(name: \"" + category[
                    'name'] + "\", service_type: \"" + category['service_type'] + "\") { id name service_type } }"
            }

            response = requests.post(f"{graphql_server_url}/categories",
                                     json=mutation_payload,
                                     headers={'Content-Type': 'application/json'})

            if response.status_code in [200, 201]:
                category_ids[response.json().get('name')] = response.json().get('id')
                types_added += 1

        devices_added = 0
        for device in data_structure['devices']:
            mutation_payload = {
                "query": f"""mutation {{ 
                               createDevice(
                                   category_id: {category_ids[device['category_name']]}, 
                                   model: "{device['model']}", 
                                   brand: "{device['brand']}", 
                                   price: {device['price']}, 
                                   manufacturing_year: {device['manufacturing_year']}, 
                                   description: "{device['description']}"
                               ) {{ 
                                   id model brand price 
                               }} 
                           }}"""
            }

            response = requests.post(f"{graphql_server_url}/devices",
                                     json=mutation_payload,
                                     headers={'Content-Type': 'application/json'})
            if response.status_code in [200, 201]:
                devices_added += 1

        return JsonResponse({
            'success': True,
            'message': f'Adaugate in GraphQL Server: {types_added} tipuri si {devices_added} device-uri',
            'types_added': types_added,
            'devices_added': devices_added,
            'total_devices': len(devices)
        })

    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': f'GraphQL Server add error: {str(e)}'
        }, status=500)


@csrf_exempt
@require_http_methods(["GET"])
def get_graphql_data(request):
    try:
        graphql_server_url = "http://localhost:3000"

        query = {
            'query': '''
            {
                allDevices(filter: {price_lt: 1500}) {
                    id
                    model
                    brand
                    price
                    manufacturing_year
                    description
                    category_id
                }
                allCategories {
                    id
                    name
                    service_type
                }
            }
            '''
        }

        response = requests.post(f"{graphql_server_url}/graphql",
                                 json=query,
                                 headers={'Content-Type': 'application/json'})

        if response.status_code == 200:
            result = response.json()

            if 'errors' in result:
                return JsonResponse({
                    'success': False,
                    'error': 'GraphQL query errors',
                    'details': result['errors']
                }, status=400)

            devices = result.get('data', {}).get('allDevices', [])
            categories = result.get('data', {}).get('allCategories', [])

            unified_data = []
            for device in devices:
                category = next((t for t in categories
                                    if t['id'] == device['category_id']), None)
                if category:
                    unified_data.append({
                        'categoryName': category['name'],
                        'service_type': category['service_type'],
                        'deviceModel': device['model'],
                        'brand': device['brand'],
                        'price': device['price'],
                        'year': device['manufacturing_year'],
                        'description': device.get('description', '')
                    })

            return JsonResponse({
                'success': True,
                'data': unified_data,
                'count': len(unified_data),
                'message': f'Găsite {len(unified_data)} device-uri sub 1500 lei din GraphQL Server'
            })

        else:
            return JsonResponse({
                'success': False,
                'error': f'GraphQL Server response error: {response.status_code}',
                'details': response.text
            }, status=500)

    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': f'GraphQL Server connection error: {str(e)}'
        }, status=500)


def process_rdf4j_results(rdf_data):
    """Procesează rezultatele din RDF4J pentru afișare unificată"""
    processed = []
    if 'results' in rdf_data and 'bindings' in rdf_data['results']:
        for binding in rdf_data['results']['bindings']:
            processed.append({
                'categoryName': binding.get('categoryName', {}).get('value', ''),
                'serviceType': binding.get('serviceType', {}).get('value', ''),
                'deviceModel': binding.get('deviceModel', {}).get('value', ''),
                'brand': binding.get('brand', {}).get('value', ''),
                'price': binding.get('price', {}).get('value', '0'),
                'year': binding.get('year', {}).get('value', '2023'),
                'description': binding.get('description', {}).get('value', '')
            })
    return processed


@csrf_exempt
@require_http_methods(["GET"])
def test_servers(request):
    """Test conectivitatea la toate serverele"""
    results = {}

    # Test RDF4J
    try:
        response = requests.get("http://localhost:8080/rdf4j-server/repositories/grafexamen/size")
        results['rdf4j'] = {
            'status': 'OK' if response.status_code == 200 else 'ERROR',
            'details': f'Status: {response.status_code}'
        }
    except Exception as e:
        results['rdf4j'] = {'status': 'ERROR', 'details': str(e)}

    # Test JSON-Server
    try:
        response = requests.get("http://localhost:4000/db")
        results['json_server'] = {
            'status': 'OK' if response.status_code == 200 else 'ERROR',
            'details': f'Status: {response.status_code}'
        }
    except Exception as e:
        results['json_server'] = {'status': 'ERROR', 'details': str(e)}

    # Test GraphQL-Server
    try:
        query = {'query': '{ __schema { types { name } } }'}
        response = requests.post("http://localhost:3000/graphql", json=query)
        results['graphql_server'] = {
            'status': 'OK' if response.status_code == 200 else 'ERROR',
            'details': f'Status: {response.status_code}'
        }
    except Exception as e:
        results['graphql_server'] = {'status': 'ERROR', 'details': str(e)}

    return JsonResponse({'servers_status': results})