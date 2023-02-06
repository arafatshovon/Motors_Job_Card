from django.shortcuts import render
from django.http import HttpResponse
import pandas as pd
from app.jobcard import JobCard, replace_elements, remove_duplicates
from app.dictmap import mapping


class UserDataClass:
    user_name: str


def jobquery(request):
    CHESIS_NUMBER = request.POST['chassis']
    MILEAGE = int(request.POST['mileage'])
    JC = JobCard()
    ret, user_info, DATAS = JC.get_job_card(CHESIS_NUMBER, MILEAGE, N=10)
    if ret:
        user_data = UserDataClass()
        amount = UserDataClass()
        suggestion_list = []
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

        if len(result)>5:
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
        user_data = UserDataClass()
        suggestion = UserDataClass()
        amount = UserDataClass()
        suggestion_list = []
        user_data.chassis_number = CHESIS_NUMBER
        user_data.mileage = MILEAGE

    return render(request, 'checkout.html', {'user_data': user_data, 'suggestion_list' : suggestion_list, 'amount':amount, 'ret':ret})


def home(request):
    user_data = UserDataClass()
    suggestion = UserDataClass()
    amount = UserDataClass()
    suggestion_list = []
    ret = True
    return render(request, 'checkout.html', {'user_data': user_data, 'suggestion_list' : suggestion_list, 'amount': amount, 'ret':ret})

