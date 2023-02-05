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
    user_info, DATAS = JC.get_job_card(CHESIS_NUMBER, MILEAGE, N=20)
    user_data = UserDataClass()
    suggestion = UserDataClass()
    amount = UserDataClass()
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

    suggestion.p1 = result[0]
    suggestion.p2 = result[1]
    suggestion.p3 = result[2]
    suggestion.p4 = result[3]
    suggestion.p5 = result[4]
    amount.total = 5
    amount.a1 = 25
    amount.a2 = 20
    amount.a3 = 15
    amount.a4 = 8
    amount.a5 = 5
    return render(request, 'checkout.html', {'user_data': user_data, 'suggestion' : suggestion, 'amount':amount})


class TestClass:
    def __init__(self, num1, num2):
        self.num1 = num1
        self.num2 = num2
    def add(self):
        return self.num1 + self.num2
    def subtract(self):
        return self.num1 - self.num2


def home(request):
    user_data = UserDataClass()
    suggestion = UserDataClass()
    amount = UserDataClass()
    return render(request, 'checkout.html', {'user_data': user_data, 'suggestion' : suggestion, 'amount': amount})

def add(request):
    val1 = int(request.POST.get('num1', False))
    val2 = int(request.POST['num2'])

    # res = int(val1)+int(val2)
    res = TestClass(val1, val2).subtract()

    return render(request, 'jobcard.html', {'name': 'Siam', 'result': res})