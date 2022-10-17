import pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime
pd.set_option('display.max_columns', None)
from jobcard import *
import math

number_top_problems = 250
minimum_proba_fill = 0.00001

sale_df = pd.read_csv("./data/sale_df_db.csv")
warranty_df = pd.read_csv("./data/warranty_df_db.csv")

drop_column = ['service_type','dc_warranty_id','master_code','dealer_name','customer_name','total_cost']
cleaned_warranty_df = warranty_df.drop(drop_column, axis=1)
cleaned_warranty_df.dropna(inplace=True)
cleaned_warranty_df['day_count'] = cleaned_warranty_df.apply(lambda row:count_date(row['warranty_date'],row['inv_date']),axis=1)
cleaned_warranty_df['mileage'] = cleaned_warranty_df.apply(lambda row:convert_float(row['mileage']),axis=1)
cleaned_warranty_df['avg_mileage'] = cleaned_warranty_df.apply(lambda row:average_mileage(row['mileage'],row['day_count']),axis=1)
cleaned_warranty_df.dropna(inplace=True)


mileage_bins = []
day_count_bins = []
avg_mileage_bins = []
for q in range(0,110,10):
    if q==100:
        mileage_bins.append(10*int(cleaned_warranty_df['mileage'].quantile(q/100)))
        day_count_bins.append(10*int(cleaned_warranty_df['day_count'].quantile(q/100)))
        avg_mileage_bins.append(10*int(cleaned_warranty_df['avg_mileage'].quantile(q/100)))
    else:
        mileage_bins.append(int(cleaned_warranty_df['mileage'].quantile(q/100)))
        day_count_bins.append(int(cleaned_warranty_df['day_count'].quantile(q/100)))
        avg_mileage_bins.append(int(cleaned_warranty_df['avg_mileage'].quantile(q/100)))


bin_dict = {
            'mileage_bins' :  mileage_bins,
            'day_count_bins' : day_count_bins,
            'avg_mileage_bins' :  avg_mileage_bins
            }
with open("./cluster_data/bin_dict.json", "w") as outfile:
    json.dump(bin_dict, outfile)

matrix_df = pd.DataFrame()

matrix_df['bike_code'] = cleaned_warranty_df['bike_code']
matrix_df['mileage_cluster'] = pd.cut(cleaned_warranty_df['mileage'],bins=mileage_bins)
matrix_df['day_count_cluster'] = pd.cut(cleaned_warranty_df['day_count'],bins=day_count_bins)
matrix_df['avg_mileage_cluster'] = pd.cut(cleaned_warranty_df['avg_mileage'],bins=avg_mileage_bins)
matrix_df['product_name'] = cleaned_warranty_df['product_name']

matrix_df.dropna(inplace=True)
selected_problems = list(matrix_df['product_name'].value_counts()[:number_top_problems].index)

features = ['mileage_cluster', 'day_count_cluster', 'avg_mileage_cluster', 'bike_code']

for feature in features:
    mileage_cluster_number = len(matrix_df[feature].unique())
    test_matrix = pd.DataFrame(columns=[feature]+selected_problems)

    print(f'Total {feature} : {mileage_cluster_number}')
    for index in range(mileage_cluster_number):
        cluster_name = matrix_df[feature].unique()[index]
        selected_matrix = matrix_df[matrix_df[feature] == cluster_name]
        test_matrix.loc[index,feature] = cluster_name
        cols = list(selected_matrix['product_name'].value_counts().index)
        vals = list(selected_matrix['product_name'].value_counts().values)
        for i in range(len(selected_matrix['product_name'].value_counts())):
            if cols[i] in selected_problems:
                test_matrix.loc[index,cols[i]]=vals[i]/sum(vals)
                        

    if feature=='bike_code':
        test_matrix = test_matrix.fillna(0.0)
    else:
        test_matrix = test_matrix.fillna(minimum_proba_fill)
    test_matrix.to_csv('./cluster_data/'+feature+'.csv', sep=',', encoding='utf-8', index=False)


