import pandas as pd
import pyodbc
import sys
from typing import List
from datetime import datetime, timedelta
from threading import Thread
import time
import pytz
from traceback import format_exc

class DataRetrievalError(Exception):
    pass

bin_dict = {"mileage_bins": [0, 5, 100, 500, 1500, 3000, 4500, 6000, 9000, 15000, 50000, 100000000],
             "day_count_bins": [-500, 31, 84, 131, 182, 230, 276, 325, 377, 496, 19960, 100000000],
             "avg_mileage_bins": [-1, 8, 14, 18, 21, 25, 28, 31, 36, 43, 296260, 100000000]}


def convert_int(string):
    digits = ""
    for char in string:
        if char.isdigit():
            digits += char
    return int(digits)


def convert_df_mileage(df, bin_dict):
    mileage_int = []
    mileage_list = list(df['mileage'])
    for i in range(len(mileage_list)):
        try:
            mileage_int.append(int(mileage_list[i]))
        except:
            mileage_int.append(-1)

    if len(mileage_int) == len(df):
        df['mileage'] = mileage_int

    df['mileage_cluster'] = pd.cut(df['mileage'], bins=bin_dict['mileage_bins']).astype('object')

    return df


class DBManager:
    x = 0

    def __init__(self, server: str = "192.168.100.25", port: int = 1433, database: str = "MotorMC", force_driver = None):
        self._server = server
        self._port = port
        self._database = database
        self._force_driver = force_driver

        self.connection = self._connect_to_db(server, port, database, force_driver)
        self.load_and_prepare_data_from_db()
        
    def _connect_to_db(self, server, port, database, force_driver):
        odbc_driver = '{ODBC Driver 17 for SQL Server}'
        native_driver = '{SQL Server Native Client 11.0}'
        driver = native_driver
        connection = None
        if sys.platform == 'linux':
            driver = odbc_driver
        else:
            driver = native_driver

        if force_driver:
            driver = force_driver

        connection = pyodbc.connect(
            f"""Driver={driver};
            Server={server},{port};
            Trusted_Connection=no;
            Database={database};
            UID=sa;
            PWD=dataport;"""
        )

        print("********** DB Connected **********")

        return connection
    
    def _reconnect_to_db(self):
        if self.connection:
            self.connection.close()

        self.connection = self._connect_to_db(self._server, self._port, self._database, self._force_driver)

    def _load_warranty_data(self):
        max_retries = 3
        retries = 0
        success = False

        cursor = None

        while not success and retries < max_retries:
            try:
                cursor = self.connection.cursor()

                print("============== Running Query For Warranty Data ===============")

                cursor.execute(
                    "SELECT UC.RegionName, 'Warranty Claim' ServiceType,    DWC.DCWarrantyId, "
                    "Convert(Varchar(10),DWC.WCDate,120) AS WCDate, "
                    "Convert(Varchar(10),DWC.OccuranceDate,120) AS OccuranceDate, "
                    "DWC.MasterCode, C.CustomerName AS DealarName, "
                    "DIM.CustomerName, BP.ProductCode AS BikeCode, BP.ProductName AS BikeName, DWC.ChassisNo, "
                    "Convert(Varchar(10),DIM.InvoiceDate,120) AS InvoiceDate, "
                    "DWC.Mileage, DWC.ProblemDetails AS ProblemDetails, "
                    "P.ProductCode AS ProductCode, "
                    "P.ProductName AS ProductName, "
                    "P.UnitPrice + P.ServiceCharge AS TotalCost "
                    "FROM DealarWarrantyClaim DWC "
                    "LEFT JOIN UserCustomer UC ON DWC.MasterCode = UC.CustomerCode AND UserType = 'SE' "
                    "LEFT JOIN Customer C ON DWC.MasterCode = C.CustomerCode "
                    "INNER JOIN DealarInvoiceDetails DID ON DWC.ChassisNo = DID.ChassisNo "
                    "INNER JOIN Product BP ON DID.ProductCode = BP.ProductCode "
                    "INNER JOIN DealarInvoiceMaster DIM ON DIM.InvoiceId = DID.InvoiceId "
                    "LEFT JOIN (SELECT DCWarrantyId, ISNULL(P.PartNo, OP.SMSCode) ProductCode,ISNULL(P.ProductName, "
                    "OP.ProductName) ProductName,(D.UnitPrice * Quantity) UnitPrice,ServiceCharge "
                    "FROM DealarWarrantyClaimProduct D "
                    "LEFT JOIN Product P  ON D.ProductCode = P.ProductCode "
                    "LEFT JOIN OtherProduct OP ON D.ProductCode = CONVERT(VARCHAR, OP.ProductCode)) P "
                    "ON DWC.DCWarrantyId = P.DCWarrantyId "
                    "WHERE Status = 1")
                
                print("============== Query Completed For Warranty Data ===============")
                
                self._warranty_data = cursor.fetchall()

                print("============== Warranty Data Loaded ===============")

                cursor.close()
                cursor = None
                
                success = True
            except Exception as e:
                if cursor:
                    cursor.close()

                print(f"******* {retries + 1}. Failed to fetch warranty data: {e.__class__.__name__} | {e}")

                time.sleep(1)
                self._reconnect_to_db()
                retries += 1

                print("Retrying...")

        if not success:
            raise Exception("******* FAILED TO FETCH WARRANTY DATA EVEN AFTER RETRYING *******")

    def _get_sales_data_of_chassis(self, chassis: str) -> pyodbc.Row:
        max_retries = 3
        retries = 0
        success = False

        cursor = None

        while not success and retries < max_retries:
            try:
                cursor = self.connection.cursor()

                cursor.execute(f"""
                                    Select T1.InvoiceID, T1.InvoiceDate, T1.InvoiceNo, C.CustomerCode AS DealerCode, 
                                    C.CustomerName AS DealerName, (C.Add1 + ' ' + C.Add2) DealerAddress, 
                                    T1.MasterCode, T1.CustomerCode, T1.CustomerName, T1.OccupationId, 
                                    ISNULL(DATEDIFF(day, T1.InvoiceDate, GetDate()), '100') InvoiceDiffInDays, 
                                    ISNULL(T1.DateOfBirth, '1900-01-01') DateOfBirth1, 
                                    ISNULL(DATEDIFF(day, T1.DateOfBirth, GetDate()), '36500') AgeInDays, 
                                    T2.ProductCode, T2.ProductName, T2.UnitPrice, T2.ChassisNo, 
                                    T2.EngineNo, T2.Color, T3.PackSize, T3.Model, T4.RegionName 
                                    From DealarInvoiceMaster T1 
                                    Inner Join DealarInvoiceDetails T2 ON T1.InvoiceID = T2.InvoiceID 
                                    Inner Join Product T3 ON T2.ProductCode = T3.ProductCode 
                                    Left Join UserCustomer T4 ON T1.MasterCode = T4.CustomerCode 
                                    LEFT JOIN Customer C ON T1.MasterCode = C.CustomerCode 
                                    WHERE T2.ChassisNo = '{chassis}';
                            """)
            

                data = cursor.fetchone()
                cursor.close()
                cursor = None

                success = True
            except Exception as e:
                if cursor:
                    cursor.close()

                print(f"******* {retries + 1}. Failed to fetch sales data: {e.__class__.__name__} | {e}")

                time.sleep(1)
                self._reconnect_to_db()
                retries += 1

                print("Retrying...")

        if success:
            return data
        else:
            raise Exception("******* FAILED TO FETCH SALES DATA EVEN AFTER RETRYING *******")
        

    def __get_warranty_df_from_db(self) -> pd.DataFrame: 
        rows = []
        for customer in self._warranty_data:
            row = []
            for item in customer:
                row.append(item)
            rows.append(row)

        column_names = [
            'region', 'service_type', 'dc_warranty_id', 'warranty_date', 'occurrence_date', 'master_code',
            'dealer_name',
            'customer_name', 'bike_code', 'bike_model', 'chassis_no', 'inv_date', 'mileage', 'problem',
            'part_code', 'product_name', 'total_cost'
        ]

        warranty_df = pd.DataFrame(rows, columns=column_names)

        return warranty_df
    
    def _convert_warranty_data_to_df(self):
        warranty_df = self.__get_warranty_df_from_db()
        self.converted_warranty_df = convert_df_mileage(warranty_df, bin_dict)
        self.converted_warranty_df.dropna(inplace=True)

    def _convert_sales_data_to_df(self, sales_data: pyodbc.Row):
        if sales_data:
            row = []
            for item in sales_data:
                row.append(item)

            column_names = ['invoice_id', 'invoice_date', 'invoice_no', 'dealer_code', 'dealer_name',
                            'dealer_address', 'master_code', 'customer_code', 'customer_name', 'occupation_id',
                            'invoice_diff_in_days', 'date_of_birth', 'age_in_days', 'product_code', 'product_name',
                            'unit_price', 'chassis_no', 'engine_no', 'color', 'pack_size', 'model', 'region_name']
            
            return pd.DataFrame([row], columns=column_names)
        else:
            return pd.DataFrame()

    def get_converted_warranty_df(self) -> pd.DataFrame:
        return self.converted_warranty_df
    
    def get_sales_df_for_chassis(self, chassis: str) -> pd.DataFrame:
        try:
            sales_data = self._get_sales_data_of_chassis(chassis)
            df = self._convert_sales_data_to_df(sales_data)
            return df
        except Exception as e:
            print(f"Sales data fetch error: {e.__class__.__name__} | {e}")
            raise DataRetrievalError("Failed to retrieve data")

    def load_and_prepare_data_from_db(self):
        try:
            self._load_warranty_data()
            self._convert_warranty_data_to_df()

            print("********** Data Loaded **********")
        except Exception as e:
            print(f"Failed to load data from db: {e}")
            print("============ Handled Exception ============")
            print(format_exc())

    # def increment_var(self):
    #     self.x += 1
    #     print("Var Value: ", self.x)


db_manager = DBManager()

bst = pytz.timezone('Asia/Dhaka')

def job():
    # db_manager.increment_var()
    db_manager.load_and_prepare_data_from_db()
    print(f"Data loaded and prepared at {datetime.now(bst)}")

def get_seconds_until_midnight():
    now = datetime.now(bst)
    midnight = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    return (midnight - now).seconds

def db_scheduler():
    while True:
        seconds_until_midnight = get_seconds_until_midnight()
        time.sleep(seconds_until_midnight)
        job()
        time.sleep(120)


t = Thread(target=db_scheduler, daemon=True)
t.start()