import pandas as pd
import numpy as np
# import matplotlib.pyplot as plt
import datetime
import json


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
        self.warranty_df = pd.read_csv(f"{root_dir}data/warranty_df_db.csv")
        self.avg_mileage_cluster = pd.read_csv(f'{root_dir}cluster_data/avg_mileage_cluster.csv')
        self.day_count_cluster = pd.read_csv(f'{root_dir}cluster_data/day_count_cluster.csv')
        self.mileage_cluster = pd.read_csv(f'{root_dir}cluster_data/mileage_cluster.csv')
        self.bike_cluster = pd.read_csv(f'{root_dir}cluster_data/bike_code.csv')
        self.cleaned_warranty_df = self.get_warranty_df()
        self.bin_data = json.load(open(f'{root_dir}cluster_data/bin_dict.json'))
        self.mileage_bins = self.bin_data['mileage_bins']
        self.day_count_bins =  self.bin_data['day_count_bins']
        self.avg_mileage_bins =  self.bin_data['avg_mileage_bins']
        
    def get_info(self, CHESIS_NUMBER, MILEAGE):
        user_data = self.sale_df[self.sale_df['chassis_no']==CHESIS_NUMBER]
        self.data_dict ={}
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
        drop_column = ['service_type','dc_warranty_id','master_code','dealer_name','customer_name','total_cost']
        cleaned_warranty_df = self.warranty_df.drop(drop_column, axis=1)
        cleaned_warranty_df.dropna(inplace=True)
        cleaned_warranty_df['day_count'] = cleaned_warranty_df.apply(lambda row:count_date(row['warranty_date'],row['inv_date']),axis=1)
        cleaned_warranty_df['mileage'] = cleaned_warranty_df.apply(lambda row:convert_float(row['mileage']),axis=1)
        cleaned_warranty_df['avg_mileage'] = cleaned_warranty_df.apply(lambda row:average_mileage(row['mileage'],row['day_count']),axis=1)
        cleaned_warranty_df.dropna(inplace=True)
        return cleaned_warranty_df
    
    def get_job_card(self, CHESIS_NUMBER, MILEAGE, N=10):
        ret, user_info = self.get_info(CHESIS_NUMBER, MILEAGE)
        if ret:
            self.cluster_mileage = pd.cut(pd.Series(self.data_dict['mileage']), bins=self.mileage_bins)
            s1 = self.mileage_cluster[self.mileage_cluster['mileage_cluster']==str(self.cluster_mileage[0])]
            cluster_day_count = pd.cut(pd.Series(self.data_dict['day_count']), bins=self.day_count_bins)
            s2 = self.day_count_cluster[self.day_count_cluster['day_count_cluster']==str(cluster_day_count[0])]
            cluster_avg_mileage = pd.cut(pd.Series(self.data_dict['avg_mileage']), bins=self.avg_mileage_bins)
            s3 = self.avg_mileage_cluster[self.avg_mileage_cluster['avg_mileage_cluster']==str(cluster_avg_mileage[0])]
            s4 = self.bike_cluster[self.bike_cluster['bike_code'] == self.data_dict['product_code']]
            p1 = s1.iloc[0,1:].values
            p2 = s2.iloc[0,1:].values
            p3 = s3.iloc[0,1:].values
            p4 = s4.iloc[0,1:].values
            probabilities = list(np.multiply(np.multiply(p1,p2),np.multiply(p3,p4)))
            out_index = sorted(range(len(probabilities)), key=lambda k: -probabilities[k])
            all_parts_list = list(s1.iloc[0,1:].index)
            DATAS = []
            for i in range(N):
                DATAS.append([all_parts_list[out_index[i]], probabilities[out_index[i]]*1000000])
            return ret, user_info, pd.DataFrame(DATAS)

        else:
            return ret, [], pd.DataFrame([])


            
    def visualize(self):
        plt.figure(figsize=(10,3))
        plt.title('Based on Bike Model')
        self.bike_cluster[self.bike_cluster['bike_code']==self.data_dict['product_code']].iloc[0,1:].sort_values(ascending=False)[:10].plot.bar()
        plt.figure(figsize=(10,3))
        plt.title('Based on Mileage')
        self.mileage_cluster[self.mileage_cluster['mileage_cluster']==str(self.cluster_mileage[0])].iloc[0,1:].sort_values(ascending=False)[:10].plot.bar()