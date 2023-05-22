## Version 2.0
import pandas as pd
import numpy as np
import datetime
import json
import re
from collections import Counter
from app.dictmap import mapping, removed_list


def rename_tank_side(output):
    patterns = ['TANK SIDE COVER 1', 'TANK SIDE COVER 2']
    for pattern in patterns:
        match = re.search(pattern, output)
        if match:
            matched_string = match.group()
            output = matched_string
    return output

def remove_forbidden(input_list):
    input_list_copy = list(input_list)
    forbidden_elements = ['TANK SIDE COVER 1', 'TANK SIDE COVER 2']
    for element in list(input_list):
        if element in forbidden_elements:
            input_list_copy.remove(element)
    return input_list_copy


def get_suggestion(out_1, out_2, mileage, max_num_suggestion):
    if mileage < 50:
        out_1 = remove_forbidden(out_1)
        out_2 = remove_forbidden(out_2)
    output_list = []
    waiting_list = list(out_2)
    output_list += list(out_1)[:5]
    for p in waiting_list:
        if len(output_list) >= max_num_suggestion:
            break
        elif p not in output_list:
            output_list.append(p)
    return output_list


def convert_float(s):
    if s[0].isdigit():
        try:
            ss = ''.join(i for i in s if i.isdigit())
            return float(ss)
        except:
            return None
    else:
        return None


def count_date(current, invoice):
    d1 = datetime.datetime.strptime(invoice, "%Y-%m-%d")
    d2 = datetime.datetime.strptime(current, "%Y-%m-%d")
    delta = d2 - d1
    return delta.days


def average_mileage(mileage, day_count):
    if day_count > 0:
        return mileage/day_count
    else:
        return -1


def remove_elements(input_list, elements_to_remove):
    return [element for element in input_list if element not in elements_to_remove]


def replace_elements(input_list, mapping_dict):
    return [mapping_dict.get(i, i) for i in input_list]


def remove_duplicates(input_list):
    seen = set()
    result = []
    for element in input_list:
        if element not in seen:
            seen.add(element)
            result.append(element)
    return result


class JobCard:
    def __init__(self, root_dir = './app/'):
        self.sale_df = pd.read_csv(f"{root_dir}data/sale_df_db.csv")
        self.warranty_df = pd.read_csv(f"{root_dir}data/warranty_converted_df_db.csv")
        self.cleaned_warranty_df = self.get_warranty_df()
        self.bin_dict = json.load(open(f'{root_dir}cluster_data/bin_dict.json'))
        self.mileage_bins = self.bin_dict['mileage_bins']
        
    def get_info(self, CHESIS_NUMBER, MILEAGE):
        user_data = self.sale_df[self.sale_df['chassis_no'] == CHESIS_NUMBER]
        self.data_dict = {}
        if not user_data.empty:
            ret = True
            mileage = MILEAGE
            user_data = user_data.iloc[0]
            current_date = datetime.datetime.now().strftime("%Y-%m-%d")
            day_count = count_date(current_date, user_data['invoice_date'])
            self.data_dict = {'customer_name': user_data['customer_name'],
                              'product_code': user_data['product_code'],
                              'day_count': day_count,
                              'mileage': mileage,
                              'avg_mileage': average_mileage(mileage, day_count),
                              'purchase_date': user_data['invoice_date'],
                              'engine_number': user_data['engine_no'],
                              'brand': user_data['product_name'],
                              'job_date': (datetime.datetime.now() + datetime.timedelta(hours=6)).strftime(
                                  "%Y-%m-%d %H:%M:%S")
                              }
        else:
            print('======  InValid ======')
            ret = False

        return ret, self.data_dict
        
        
    def get_warranty_df(self):
        drop_column = ['service_type', 'dc_warranty_id', 'master_code', 'dealer_name', 'customer_name', 'total_cost']
        cleaned_warranty_df = self.warranty_df.drop(drop_column, axis=1)
        cleaned_warranty_df.dropna(inplace=True)
        cleaned_warranty_df['day_count'] = cleaned_warranty_df.apply(lambda row: count_date(row['warranty_date'],row['inv_date']),axis=1)
        cleaned_warranty_df['avg_mileage'] = cleaned_warranty_df.apply(lambda row: average_mileage(row['mileage'],row['day_count']),axis=1)
        cleaned_warranty_df.dropna(inplace=True)
        return cleaned_warranty_df
    
    def get_job_card(self, CHESIS_NUMBER, MILEAGE, N=10):
        ret, user_info = self.get_info(CHESIS_NUMBER, MILEAGE)
        if ret:
            bike_code = self.data_dict['product_code']
            input_mileage = self.data_dict['mileage']
            max_num_suggestion = N
            self.valid_parts = self.get_prediction_bike(bike_code=bike_code)
            self.valid_parts = [rename_tank_side(valid_part) for valid_part in self.valid_parts]

            selected_df = self.cleaned_warranty_df[self.cleaned_warranty_df['bike_code'] == bike_code]
            out_1 = self.get_parts_from_mileage(selected_df, input_mileage=MILEAGE)
            out_2 = self.get_parts_from_mileage(self.cleaned_warranty_df, input_mileage=MILEAGE)
            suggestions = get_suggestion(out_1, out_2, input_mileage, max_num_suggestion)

            DATAS = []
            for i in range(min(N, len(suggestions))):
                DATAS.append([suggestions[i], suggestions[i]])
            return ret, user_info, pd.DataFrame(DATAS)

        else:
            return ret, [], pd.DataFrame([])

    def get_prediction_bike(self, bike_code):
        selected_df = self.cleaned_warranty_df[self.cleaned_warranty_df['bike_code'] == bike_code]
        return list(set(selected_df['product_name']))

    def get_prediction_all(self, df, input_mileage):
        input_mileage_cluster = pd.cut(pd.Series(input_mileage), bins=self.bin_dict['mileage_bins'])
        out_df = df[df['mileage_cluster'] == str(input_mileage_cluster[0])]
        return list(out_df['product_name'])

    def get_parts_from_mileage(self, df, input_mileage):
        result = self.get_prediction_all(df, input_mileage)
        result = [rename_tank_side(res) for res in result]
        result = replace_elements(result, mapping)
        count = dict(Counter(result))
        filtered_dict = {k: v for k, v in count.items() if k in self.valid_parts}
        sorted_dict = dict(sorted(filtered_dict.items(), key=lambda x: -x[1]))
        return sorted_dict
