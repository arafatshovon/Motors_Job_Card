import pandas as pd
import pyodbc
import sys


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


def connect_to_db():
    odbc_driver = '{ODBC Driver 17 for SQL Server}'
    native_driver = '{SQL Server Native Client 11.0}'
    driver = native_driver
    connection = None
    if sys.platform == 'linux':
        driver = odbc_driver
    else:
        driver = native_driver
    connection = pyodbc.connect(
        f"""Driver={driver};
        Server=192.168.100.25,1433;
        Trusted_Connection=no;
        Database=MotorMC;
        UID=sa;
        PWD=dataport;"""
    )
    return connection


def get_warranty_data_from_db():
    connection = connect_to_db()
    cursor = connection.cursor()
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
    
    data = cursor.fetchall()
    rows = []
    for customer in data:
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
    warranty_df.to_csv("./data/warranty_df_db.csv", index=None)
    converted_df = convert_df_mileage(warranty_df, bin_dict)
    converted_df.dropna(inplace=True)
    converted_df.to_csv("./data/warranty_converted_df_db.csv", index=None)
    print('warranty data saved')
    return warranty_df


def get_sale_data_from_db():
    connection = connect_to_db()
    cursor = connection.cursor()
    cursor.execute("Select T1.InvoiceID, T1.InvoiceDate, T1.InvoiceNo, C.CustomerCode AS DealerCode, "
                   "C.CustomerName AS DealerName, (C.Add1 + ' ' + C.Add2) DealerAddress, "
                   "T1.MasterCode, T1.CustomerCode, T1.CustomerName, T1.OccupationId, "
                   "ISNULL(DATEDIFF(day, T1.InvoiceDate, GetDate()), '100') InvoiceDiffInDays, "
                   "ISNULL(T1.DateOfBirth, '1900-01-01') DateOfBirth1, "
                   "ISNULL(DATEDIFF(day, T1.DateOfBirth, GetDate()), '36500') AgeInDays, "
                   "T2.ProductCode, T2.ProductName, T2.UnitPrice, T2.ChassisNo, "
                   "T2.EngineNo, T2.Color, T3.PackSize, T3.Model, T4.RegionName "
                   "From DealarInvoiceMaster T1 "
                   "Inner Join DealarInvoiceDetails T2 ON T1.InvoiceID = T2.InvoiceID "
                   "Inner Join Product T3 ON T2.ProductCode = T3.ProductCode "
                   "Left Join UserCustomer T4 ON T1.MasterCode = T4.CustomerCode "
                   "LEFT JOIN Customer C ON T1.MasterCode = C.CustomerCode "
                   "WHERE T2.ProductCode in ("
                   "'C015','C032','C033','C034','C035','C036','C048','C059','C078','C079','C083','C084','C085',"
                   "'C095','C096','C097','C098','C099','C115','C116','C117','C125', "
                   "'C127','C128','C129','C136','C068','C069','C070','C086','C100','C101','C102','C112','C002',"
                   "'C004','C006','C028','C037','C038','C039','C041','C089','C090', "
                   "'C113','C114','C122','C087','C088','C110','C111','C108','C109','C130','C132')"
                   "ORDER BY T1.InvoiceDate DESC")
    data = cursor.fetchall()
    rows = []
    for customer in data:
        row = []
        for item in customer:
            row.append(item)
        rows.append(row)
    column_names = ['invoice_id', 'invoice_date', 'invoice_no', 'dealer_code', 'dealer_name',
                    'dealer_address', 'master_code', 'customer_code', 'customer_name', 'occupation_id',
                    'invoice_diff_in_days', 'date_of_birth', 'age_in_days', 'product_code', 'product_name',
                    'unit_price', 'chassis_no', 'engine_no', 'color', 'pack_size', 'model', 'region_name']
    sale_df = pd.DataFrame(rows, columns=column_names)
    sale_df.to_csv("./data/sale_df_db.csv", index=None)
    print('sale data saved')
    return sale_df


warranty_df = get_warranty_data_from_db()
sale_df = get_sale_data_from_db()

