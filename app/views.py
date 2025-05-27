from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
import requests
import json

def index(request):
    """Pagina principală cu frontend-ul"""
    return render(request, 'index.html')


@csrf_exempt
@require_http_methods(["GET"])
def get_rdf4j_data(request):
    """Pasul 1: Extrage date din RDF4J cu filtrare"""
    try:
        # SPARQL query cu filtrare - doar device-urile sub 2000 lei
        sparql_query = """
        PREFIX schema: <http://schema.org/>
        PREFIX devices: <http://example.org/devices/>

        SELECT ?typeName ?category ?manufacturer ?deviceModel ?brand ?price ?year ?description
        WHERE {
            ?type a schema:Category ;
                  schema:name ?typeName ;
                  devices:category ?category ;
                  devices:mainManufacturer ?manufacturer .

            ?device schema:category ?type ;
                    schema:model ?deviceModel ;
                    schema:brand ?brand ;
                    schema:price ?price ;
                    devices:manufacturingYear ?year ;
                    schema:description ?description .

            # Condiție de filtrare - doar device-urile sub 2000 lei
            FILTER(?price < 2000)
        }
        ORDER BY ?typeName ?price
        """

        # Cerere către RDF4J
        rdf4j_url = "http://localhost:8080/rdf4j-server/repositories/grafexamen"
        headers = {
            'Accept': 'application/sparql-results+json',
            'Content-Type': 'application/sparql-query'
        }

        response = requests.post(f"{rdf4j_url}/query",
                                 data=sparql_query,
                                 headers=headers)

        if response.status_code == 200:
            data = response.json()
            processed_data = process_rdf4j_results(data)

            return JsonResponse({
                'success': True,
                'data': processed_data,
                'count': len(processed_data),
                'message': f'Găsite {len(processed_data)} device-uri sub 2000 lei din RDF4J'
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


@csrf_exempt
@require_http_methods(["POST"])
def transfer_to_json_server(request):
    """Pasul 2: Transfer date la JSON-Server (REST)"""
    try:
        # Preia datele din request
        data = json.loads(request.body)
        devices_data = data.get('data', [])

        if not devices_data:
            return JsonResponse({
                'success': False,
                'error': 'No data provided'
            }, status=400)

        # Separă datele în tipuri și device-uri pentru normalizare
        device_types = {}
        devices = []

        # Procesează datele pentru a crea structuri separate
        for item in devices_data:
            type_key = item['typeName']

            # Adaugă tipul dacă nu există
            if type_key not in device_types:
                device_types[type_key] = {
                    'id': len(device_types) + 1,
                    'name': item['typeName'],
                    'category': item['category'],
                    'main_manufacturer': item['manufacturer']
                }

            # Adaugă device-ul
            devices.append({
                'id': len(devices) + 1,
                'device_type_id': device_types[type_key]['id'],
                'model': item['deviceModel'],
                'brand': item['brand'],
                'price': float(item['price']),
                'manufacturing_year': int(item.get('year', 2023)),
                'description': item.get('description', '')
            })

        # Trimite datele la JSON-Server
        json_server_url = "http://localhost:4000"

        # Șterge datele existente (opțional, pentru test clean)
        try:
            requests.delete(f"{json_server_url}/db")
        except:
            pass  # Ignoră eroarea dacă nu există

        # Trimite tipurile de device-uri
        types_sent = 0
        for device_type in device_types.values():
            response = requests.post(f"{json_server_url}/device_types",
                                     json=device_type,
                                     headers={'Content-Type': 'application/json'})
            if response.status_code in [200, 201]:
                types_sent += 1

        # Trimite device-urile
        devices_sent = 0
        for device in devices:
            response = requests.post(f"{json_server_url}/devices",
                                     json=device,
                                     headers={'Content-Type': 'application/json'})
            if response.status_code in [200, 201]:
                devices_sent += 1

        return JsonResponse({
            'success': True,
            'message': f'Transfer complet: {types_sent} tipuri și {devices_sent} device-uri în JSON-Server',
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
    """Pasul 3: Citește din JSON-Server cu filtrare și JOIN"""
    try:
        json_server_url = "http://localhost:4000"

        # Preia tipurile și device-urile
        types_response = requests.get(f"{json_server_url}/device_types")
        devices_response = requests.get(f"{json_server_url}/devices")

        if types_response.status_code != 200 or devices_response.status_code != 200:
            return JsonResponse({
                'success': False,
                'error': 'Failed to fetch from JSON-Server',
                'types_status': types_response.status_code,
                'devices_status': devices_response.status_code
            }, status=500)

        types_data = types_response.json()
        devices_data = devices_response.json()

        # Aplicare filtru - doar device-urile Apple (ca exemplu de filtrare)
        filtered_devices = [d for d in devices_data if d['brand'] == 'Apple']

        # JOIN pentru afișare unificată
        unified_data = []
        for device in filtered_devices:
            device_type = next((t for t in types_data if t['id'] == device['device_type_id']), None)
            if device_type:
                unified_data.append({
                    'typeName': device_type['name'],
                    'category': device_type['category'],
                    'manufacturer': device_type['main_manufacturer'],
                    'deviceModel': device['model'],
                    'brand': device['brand'],
                    'price': device['price'],
                    'year': device['manufacturing_year'],
                    'description': device.get('description', '')
                })

        return JsonResponse({
            'success': True,
            'data': unified_data,
            'device_types': types_data,  # Pentru dropdown în frontend
            'count': len(unified_data),
            'message': f'Găsite {len(unified_data)} device-uri Apple din JSON-Server'
        })

    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': f'JSON-Server read error: {str(e)}'
        }, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def add_to_graphql_server(request):
    """Pasul 4: Adaugă datele existente + nouă înregistrare în GraphQL Server"""
    try:
        data = json.loads(request.body)
        existing_data = data.get('existing_data', [])
        new_device = data.get('new_device', {})

        if not new_device:
            return JsonResponse({
                'success': False,
                'error': 'No new device data provided'
            }, status=400)

        # Combină datele existente cu noua înregistrare
        all_data = existing_data.copy()
        all_data.append(new_device)

        # Separă din nou în tipuri și device-uri
        device_types_dict = {}
        devices_list = []

        for item in all_data:
            type_key = item['typeName']

            # Adaugă tipul dacă nu există
            if type_key not in device_types_dict:
                device_types_dict[type_key] = {
                    'id': len(device_types_dict) + 1,
                    'name': item['typeName'],
                    'category': item.get('category', 'Unknown'),
                    'main_manufacturer': item.get('manufacturer', 'Unknown')
                }

            # Adaugă device-ul
            devices_list.append({
                'id': len(devices_list) + 1,
                'device_type_id': device_types_dict[type_key]['id'],
                'model': item['deviceModel'],
                'brand': item['brand'],
                'price': float(item['price']),
                'manufacturing_year': int(item.get('year', 2024)),
                'description': item.get('description', '')
            })

        # Structura pentru GraphQL server
        data_structure = {
            'deviceTypes': list(device_types_dict.values()),
            'devices': devices_list
        }

        # Pentru JSON-GraphQL-Server, trebuie să actualizăm baza de date
        # Metoda 1: POST către fiecare endpoint
        graphql_server_url = "http://localhost:3000"

        # Resetează datele (dacă server-ul suportă)
        try:
            requests.delete(f"{graphql_server_url}/reset")
        except:
            pass

        # Adaugă tipurile
        types_added = 0
        for device_type in data_structure['deviceTypes']:
            response = requests.post(f"{graphql_server_url}/deviceTypes",
                                     json=device_type,
                                     headers={'Content-Type': 'application/json'})
            if response.status_code in [200, 201]:
                types_added += 1

        # Adaugă device-urile
        devices_added = 0
        for device in data_structure['devices']:
            response = requests.post(f"{graphql_server_url}/devices",
                                     json=device,
                                     headers={'Content-Type': 'application/json'})
            if response.status_code in [200, 201]:
                devices_added += 1

        return JsonResponse({
            'success': True,
            'message': f'Adăugate în GraphQL Server: {types_added} tipuri și {devices_added} device-uri',
            'types_added': types_added,
            'devices_added': devices_added,
            'total_devices': len(devices_list)
        })

    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': f'GraphQL Server add error: {str(e)}'
        }, status=500)


@csrf_exempt
@require_http_methods(["GET"])
def get_graphql_data(request):
    """Pasul 5: Citește din GraphQL Server cu query și filtrare"""
    try:
        graphql_server_url = "http://localhost:3000"

        # GraphQL query cu filtrare - doar device-urile sub 1500 lei
        query = {
            'query': '''
            {
                devices(where: {price_lt: 1500}) {
                    id
                    model
                    brand
                    price
                    manufacturing_year
                    description
                    device_type_id
                }
                deviceTypes {
                    id
                    name
                    category
                    main_manufacturer
                }
            }
            '''
        }

        response = requests.post(f"{graphql_server_url}/graphql",
                                 json=query,
                                 headers={'Content-Type': 'application/json'})

        if response.status_code == 200:
            result = response.json()

            # Verifică dacă există erori GraphQL
            if 'errors' in result:
                return JsonResponse({
                    'success': False,
                    'error': 'GraphQL query errors',
                    'details': result['errors']
                }, status=400)

            devices = result.get('data', {}).get('devices', [])
            device_types = result.get('data', {}).get('deviceTypes', [])

            # JOIN pentru afișare unificată
            unified_data = []
            for device in devices:
                device_type = next((t for t in device_types
                                    if t['id'] == device['device_type_id']), None)
                if device_type:
                    unified_data.append({
                        'typeName': device_type['name'],
                        'category': device_type['category'],
                        'manufacturer': device_type['main_manufacturer'],
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
                'typeName': binding.get('typeName', {}).get('value', ''),
                'category': binding.get('category', {}).get('value', ''),
                'manufacturer': binding.get('manufacturer', {}).get('value', ''),
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