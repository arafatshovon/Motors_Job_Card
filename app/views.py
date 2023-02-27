from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.models import User, auth
from app.jobcard import JobCard, replace_elements, remove_duplicates, remove_elements
from app.dictmap import mapping, removed_list
from django.http import JsonResponse


def login(request):
    if request.method == 'POST':
        username = request.POST['username']
        password = request.POST['password']
        user = auth.authenticate(username=username, password=password)
        if user is not None:
            return render(request, 'checkout.html')
        else:
            messages.info(request, 'Invalid Credentials')
            return redirect('login')

    else:
        return render(request, 'login.html')


class UserDataClass:
    user_name: str


def jobquery_web(request):
    dict_response = jobquery(request, method='POST')
    user_data_dict = dict_response['user_data_dict']
    suggestion_list = dict_response['suggestion_list']
    ret = dict_response['ret']
    user_data = UserDataClass()
    if ret:
        user_data.customer_name = user_data_dict['customer_name']
        user_data.chassis_number = user_data_dict['chassis']
        user_data.mileage = user_data_dict['mileage']
        user_data.purchase_date = user_data_dict['purchase_date']
        user_data.job_date = user_data_dict['job_date']
        user_data.engine_number = user_data_dict['engine_number']
        user_data.brand = user_data_dict['brand']

    return render(request, 'checkout.html', {'ret': ret, 'user_data': user_data, 'suggestion_list': suggestion_list})


def jobquery_api(request):
    dict_response = jobquery(request, method='GET')
    return JsonResponse(dict_response)


def jobquery(request, method='GET'):
    if method == 'POST':
        CHESIS_NUMBER = request.POST['chassis']
        MILEAGE = int(request.POST['mileage'])
    else:
        CHESIS_NUMBER = request.GET['chassis']
        MILEAGE = int(request.GET['mileage'])

    JC = JobCard()
    ret, user_info, DATAS = JC.get_job_card(CHESIS_NUMBER, MILEAGE, N=10)
    if ret:
        user_data = UserDataClass()
        user_data_dict = {}
        amount = UserDataClass()
        suggestion_list = []
        user_data_dict['customer_name'] = user_info['customer_name']
        user_data_dict['chassis'] = CHESIS_NUMBER
        user_data_dict['mileage'] = MILEAGE
        user_data_dict['purchase_date'] = user_info['purchase_date']
        user_data_dict['job_date'] = user_info['job_date']
        user_data_dict['engine_number'] = user_info['engine_number']
        user_data_dict['brand'] = user_info['brand']

        user_data.customer_name = user_info['customer_name']
        user_data.chassis_number = CHESIS_NUMBER
        user_data.mileage = MILEAGE
        user_data.purchase_date = user_info['purchase_date']
        user_data.job_date = user_info['job_date']
        user_data.engine_number = user_info['engine_number']
        user_data.brand = user_info['brand']
        result = DATAS[0].tolist()
        result = replace_elements(result, mapping)
        result = remove_duplicates(result)
        result = remove_elements(result, removed_list)

        if len(result) > 5:
            suggestion_list = result[:5]
        else:
            suggestion_list = result

        amount.total = len(suggestion_list)
        amount.a1 = 25
        amount.a2 = 20
        amount.a3 = 15
        amount.a4 = 8
        amount.a5 = 5

    else:
        user_data_dict = {}
        user_data = UserDataClass()
        suggestion = UserDataClass()
        amount = UserDataClass()
        suggestion_list = []
        user_data.chassis_number = CHESIS_NUMBER
        user_data.mileage = MILEAGE

    return {'ret': ret, 'user_data_dict': user_data_dict, 'suggestion_list': suggestion_list}


def home(request):
    user_data = UserDataClass()
    suggestion = UserDataClass()
    amount = UserDataClass()
    suggestion_list = []
    ret = True
    return render(request, 'checkout.html', {'user_data': user_data, 'suggestion_list': suggestion_list, 'amount': amount, 'ret': ret})

