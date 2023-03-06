import pandas as pd
import numpy as np
import datetime
import json
import re
from collections import Counter
from app.dictmap import mapping, removed_list
# from app.jobcard2 import replace_elements, remove_duplicates, remove_elements


def get_prediction_all(df, input_mileage = 30):
    input_mileage_cluster = pd.cut(pd.Series(input_mileage), bins=bin_dict['mileage_bins'])
    out_df = df[df['mileage_cluster'] == str(input_mileage_cluster[0])]
    return list(out_df['product_name'])

def rename_tank_side(output):
    patterns = ['TANK SIDE COVER 1', 'TANK SIDE COVER 2']
    for pattern in patterns:
        match = re.search(pattern, output)
        if match:
            matched_string = match.group()
            output = matched_string
    return output

def get_parts_from_mileage(df, input_mileage = 10):
    result = get_prediction_all(df, input_mileage)
    result = [rename_tank_side(res) for res in result]
    result = replace_elements(result, mapping)
    count = dict(Counter(result))
    filtered_dict = {k: v for k, v in count.items() if k in valid_parts}
    sorted_dict = dict(sorted(filtered_dict.items(), key=lambda x: -x[1]))
    return sorted_dict


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
    output_list += list(out_1)[:3]


    for p in waiting_list:
        if len(output_list) >= max_num_suggestion:
            break
        elif p not in output_list:
            output_list.append(p)
    return output_list