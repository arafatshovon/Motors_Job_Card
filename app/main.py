import pandas as pd
from jobcard import JobCard

# CHESIS_NUMBER = input('Enter CHESIS_NUMBER:')
# MILEAGE = input('Enter MILEAGE:')

# print(CHESIS_NUMBER, MILEAGE)
# print(type(CHESIS_NUMBER), type(MILEAGE))

CHESIS_NUMBER = 'RG642003173'
MILEAGE = 400

JC = JobCard()
user_data, DATAS = JC.get_job_card(CHESIS_NUMBER, MILEAGE,N=10)
# print(user_data)
print(pd.DataFrame.from_dict([user_data]))
print('========================================')

print(DATAS)
