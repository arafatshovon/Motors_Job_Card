from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.models import User, auth
from app.jobcard2 import JobCard, replace_elements, remove_duplicates, remove_elements
from app.dictmap import mapping, removed_list
from django.http import JsonResponse
from app.db_management import db_manager


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
    error_msg = dict_response['error']
    user_data = UserDataClass()
    if ret:
        user_data.customer_name = user_data_dict['customer_name']
        user_data.chassis_number = user_data_dict['chassis']
        user_data.mileage = user_data_dict['mileage']
        user_data.purchase_date = user_data_dict['purchase_date']
        user_data.job_date = user_data_dict['job_date']
        user_data.engine_number = user_data_dict['engine_number']
        user_data.brand = user_data_dict['brand']

    return render(request, 'checkout.html', {'ret': ret, 'user_data': user_data, 'suggestion_list': suggestion_list, 'error': error_msg})


def jobquery_api(request):
    dict_response = jobquery(request, method='GET')
    return JsonResponse(dict_response)

def top_warranty_parts_api(request):
    """
    Returns top N warranty-claimed parts (by count) from cached warranty dataframe.

    Query params:
      - limit: int (default: 30, max: 200)
    """
    try:
        limit_raw = request.GET.get('limit', '30')
        try:
            limit = int(limit_raw)
        except Exception:
            return JsonResponse(
                {'ret': False, 'data': [], 'error': f"Invalid 'limit' query param: {limit_raw}"},
                status=400,
            )

        limit = max(1, min(limit, 200))

        df = db_manager.get_converted_warranty_df()
        if df is None or getattr(df, "empty", True):
            return JsonResponse({'ret': True, 'data': [], 'error': None})

        cols = {'part_code', 'product_name'}
        if not cols.issubset(set(df.columns)):
            return JsonResponse(
                {
                    'ret': False,
                    'data': [],
                    'error': f"Warranty dataframe missing required columns: {sorted(cols)}",
                },
                status=500,
            )

        top_df = (
            df[['part_code', 'product_name']]
            .dropna()
            .groupby(['part_code', 'product_name'], as_index=False)
            .size()
            .rename(columns={'size': 'claimCount'})
            .sort_values(['claimCount', 'part_code'], ascending=[False, True])
            .head(limit)
        )

        data = [
            {
                'partCode': str(row['part_code']),
                'partName': str(row['product_name']),
                'claimCount': int(row['claimCount']),
            }
            for _, row in top_df.iterrows()
        ]

        return JsonResponse({'ret': True, 'data': data, 'error': None})
    except Exception as e:
        error_msg = f"{e.__class__.__name__}: {e}"
        return JsonResponse({'ret': False, 'data': [], 'error': error_msg}, status=500)


def jobquery(request, method='GET'):
    ret = False
    user_data_dict = {}
    error_msg = None

    try:
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

            if DATAS.empty:
                suggestion_list = []
            else:
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
            user_data = UserDataClass()
            suggestion = UserDataClass()
            amount = UserDataClass()
            suggestion_list = []
            user_data.chassis_number = CHESIS_NUMBER
            user_data.mileage = MILEAGE
    except Exception as e:
        print("============= Handled Exception =============")
        error_msg = f"{e.__class__.__name__}: {e}"
        print(error_msg)
        suggestion_list = []

    return {'ret': ret, 'user_data_dict': user_data_dict, 'suggestion_list': suggestion_list, 'error': error_msg }


def home(request):
    user_data = UserDataClass()
    suggestion = UserDataClass()
    amount = UserDataClass()
    suggestion_list = []
    ret = True
    return render(request, 'checkout.html', {'user_data': user_data, 'suggestion_list': suggestion_list, 'amount': amount, 'ret': ret})

