import pandas as pd
import pyodbc
import sys
from typing import List, Optional
from datetime import date
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
            UID=YamMot;
            PWD=PWDMS56rMC#!;"""
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

    def get_warranty_data_df(self) -> pd.DataFrame:
        """Return the current in-memory SQL warranty rows in model input columns."""
        return self.__get_warranty_df_from_db()

    def get_monthly_warranty_claim_counts(
        self,
        from_date: date,
        to_date_exclusive: date,
    ) -> List[dict]:
        """Fetch monthly claimed-part counts for the half-open date range [from, to)."""
        if from_date is None or to_date_exclusive is None:
            raise ValueError("Both from_date and to_date_exclusive are required")
        if to_date_exclusive <= from_date:
            raise ValueError("to_date_exclusive must be later than from_date")

        sql = """
            SELECT
                DATEFROMPARTS(YEAR(DWC.WCDate), MONTH(DWC.WCDate), 1) AS ClaimMonth,
                COUNT(*) AS ClaimCount
            FROM DealarWarrantyClaim DWC
            INNER JOIN DealarWarrantyClaimProduct DWCP
                ON DWC.DCWarrantyId = DWCP.DCWarrantyId
            WHERE DWC.Status = 1
              AND DWC.WCDate >= ?
              AND DWC.WCDate < ?
            GROUP BY YEAR(DWC.WCDate), MONTH(DWC.WCDate)
            ORDER BY YEAR(DWC.WCDate), MONTH(DWC.WCDate);
        """

        max_retries = 3
        retries = 0
        cursor = None

        while retries < max_retries:
            try:
                cursor = self.connection.cursor()
                cursor.execute(sql, (from_date, to_date_exclusive))
                rows = cursor.fetchall()
                cursor.close()
                cursor = None

                return [
                    {
                        "date": row[0].strftime("%Y-%m-%d"),
                        "ClaimCount": int(row[1] or 0),
                    }
                    for row in rows
                ]
            except Exception as e:
                if cursor:
                    cursor.close()
                    cursor = None
                print(
                    f"******* {retries + 1}. Failed to fetch monthly warranty claims: "
                    f"{e.__class__.__name__} | {e}"
                )
                time.sleep(1)
                self._reconnect_to_db()
                retries += 1

        raise DataRetrievalError("FAILED TO FETCH MONTHLY WARRANTY CLAIMS EVEN AFTER RETRYING")
    
    def get_sales_df_for_chassis(self, chassis: str) -> pd.DataFrame:
        try:
            sales_data = self._get_sales_data_of_chassis(chassis)
            df = self._convert_sales_data_to_df(sales_data)
            return df
        except Exception as e:
            print(f"Sales data fetch error: {e.__class__.__name__} | {e}")
            raise DataRetrievalError("Failed to retrieve data")

    def get_top_warranty_parts(
        self,
        limit: int = 30,
        from_date: Optional[date] = None,
        to_date: Optional[date] = None,
    ) -> List[dict]:
        """
        Live query to SQL Server: returns top N parts by warranty-claim count.

        Output:
          [{'partCode': '...', 'partName': '...', 'claimCount': 123}, ...]
        """
        try:
            limit = int(limit)
        except Exception:
            limit = 30
        limit = max(1, min(limit, 200))

        if from_date is None:
            raise ValueError("Missing required parameter: from_date")
        if to_date is None:
            to_date = date.today()
        if to_date < from_date:
            raise ValueError("Invalid date range: to_date must be >= from_date")

        sql = """
            DECLARE @limit INT = ?;
            DECLARE @from_date DATE = ?;
            DECLARE @to_date DATE = ?;
            SELECT TOP (@limit)
                ISNULL(P2.PartNo, OP2.SMSCode) AS PartCode,
                ISNULL(P2.ProductName, OP2.ProductName) AS PartName,
                COUNT(*) AS ClaimCount
            FROM DealarWarrantyClaim DWC2
            INNER JOIN DealarWarrantyClaimProduct D2
                ON DWC2.DCWarrantyId = D2.DCWarrantyId
            LEFT JOIN Product P2
                ON D2.ProductCode = P2.ProductCode
            LEFT JOIN OtherProduct OP2
                ON D2.ProductCode = CONVERT(VARCHAR, OP2.ProductCode)
            WHERE DWC2.Status = 1
              AND DWC2.WCDate >= @from_date
              AND DWC2.WCDate < DATEADD(day, 1, @to_date)
            GROUP BY
                ISNULL(P2.PartNo, OP2.SMSCode),
                ISNULL(P2.ProductName, OP2.ProductName)
            ORDER BY COUNT(*) DESC;
        """

        max_retries = 3
        retries = 0
        cursor = None

        while retries < max_retries:
            try:
                cursor = self.connection.cursor()
                cursor.execute(sql, (limit, from_date, to_date))
                rows = cursor.fetchall()
                cursor.close()
                cursor = None

                out: List[dict] = []
                for r in rows:
                    out.append(
                        {
                            "partCode": None if r[0] is None else str(r[0]),
                            "partName": None if r[1] is None else str(r[1]),
                            "claimCount": int(r[2]),
                        }
                    )
                return out
            except Exception as e:
                if cursor:
                    cursor.close()
                    cursor = None
                print(f"******* {retries + 1}. Failed to fetch top warranty parts: {e.__class__.__name__} | {e}")
                time.sleep(1)
                self._reconnect_to_db()
                retries += 1

        raise DataRetrievalError("FAILED TO FETCH TOP WARRANTY PARTS EVEN AFTER RETRYING")

    def get_top_warranty_parts_by_bike_model(
        self,
        limit: int = 30,
        from_date: Optional[date] = None,
        to_date: Optional[date] = None,
    ) -> List[dict]:
        """
        Live query to SQL Server: returns top N parts overall, broken down by bike model.

        Output (flat rows):
          [{'partCode': '...', 'partName': '...', 'bikeModel': '...', 'claimCount': 123}, ...]
        """
        try:
            limit = int(limit)
        except Exception:
            limit = 30
        limit = max(1, min(limit, 200))

        if from_date is None:
            raise ValueError("Missing required parameter: from_date")
        if to_date is None:
            to_date = date.today()
        if to_date < from_date:
            raise ValueError("Invalid date range: to_date must be >= from_date")

        # Note: bike model is derived from the bike product sold for the chassis (invoice details -> Product BP).
        sql = """
            DECLARE @limit_parts INT = ?;
            DECLARE @from_date DATE = ?;
            DECLARE @to_date DATE = ?;

            WITH Base AS (
                SELECT
                    ISNULL(P2.PartNo, OP2.SMSCode) AS PartCode,
                    ISNULL(P2.ProductName, OP2.ProductName) AS PartName,
                    BP.ProductName AS BikeModel
                FROM DealarWarrantyClaim DWC2
                INNER JOIN DealarWarrantyClaimProduct D2
                    ON DWC2.DCWarrantyId = D2.DCWarrantyId
                LEFT JOIN Product P2
                    ON D2.ProductCode = P2.ProductCode
                LEFT JOIN OtherProduct OP2
                    ON D2.ProductCode = CONVERT(VARCHAR, OP2.ProductCode)
                INNER JOIN DealarInvoiceDetails DID
                    ON DWC2.ChassisNo = DID.ChassisNo
                INNER JOIN Product BP
                    ON DID.ProductCode = BP.ProductCode
                WHERE DWC2.Status = 1
                  AND DWC2.WCDate >= @from_date
                  AND DWC2.WCDate < DATEADD(day, 1, @to_date)
            ),
            TopParts AS (
                SELECT TOP (@limit_parts)
                    PartCode,
                    PartName,
                    COUNT(*) AS TotalCount
                FROM Base
                GROUP BY PartCode, PartName
                ORDER BY COUNT(*) DESC
            )
            SELECT
                b.PartCode,
                b.PartName,
                b.BikeModel,
                COUNT(*) AS ClaimCount,
                tp.TotalCount AS TotalCount
            FROM Base b
            INNER JOIN TopParts tp
                ON b.PartCode = tp.PartCode
               AND b.PartName = tp.PartName
            GROUP BY b.PartCode, b.PartName, b.BikeModel, tp.TotalCount
            ORDER BY tp.TotalCount DESC, b.PartCode ASC, ClaimCount DESC, b.BikeModel ASC;
        """

        max_retries = 3
        retries = 0
        cursor = None

        while retries < max_retries:
            try:
                cursor = self.connection.cursor()
                cursor.execute(sql, (limit, from_date, to_date))
                rows = cursor.fetchall()
                cursor.close()
                cursor = None

                out: List[dict] = []
                for r in rows:
                    out.append(
                        {
                            "partCode": None if r[0] is None else str(r[0]),
                            "partName": None if r[1] is None else str(r[1]),
                            "bikeModel": None if r[2] is None else str(r[2]),
                            "claimCount": int(r[3]),
                            "totalCount": int(r[4]),
                        }
                    )
                return out
            except Exception as e:
                if cursor:
                    cursor.close()
                    cursor = None
                print(
                    f"******* {retries + 1}. Failed to fetch top warranty parts by bike model: {e.__class__.__name__} | {e}"
                )
                time.sleep(1)
                self._reconnect_to_db()
                retries += 1

        raise DataRetrievalError("FAILED TO FETCH TOP WARRANTY PARTS BY BIKE MODEL EVEN AFTER RETRYING")

    def get_top_warranty_parts_for_bike_model(
        self,
        bike_model: str,
        limit: int = 5,
        from_date: Optional[date] = None,
        to_date: Optional[date] = None,
    ) -> List[dict]:
        """
        Live query to SQL Server: returns top N parts (by claim count) for matching bike models.

        Args:
          bike_model: Bike model prefix (matched with LIKE @bike_model + '%')
          limit: top N parts (1..200)
          from_date: start date (inclusive)
          to_date: end date (inclusive). Defaults to today's date if not provided.

        Output:
          [{'bikeModel': '...', 'partCode': '...', 'partName': '...', 'claimCount': 123, 'partRank': 1}, ...]
        """
        bike_model_str = "" if bike_model is None else str(bike_model).strip()
        if not bike_model_str:
            raise ValueError("Missing required parameter: bike_model")

        try:
            limit = int(limit)
        except Exception:
            limit = 5
        limit = max(1, min(limit, 200))

        if from_date is None:
            raise ValueError("Missing required parameter: from_date")
        if to_date is None:
            to_date = date.today()
        if to_date < from_date:
            raise ValueError("Invalid date range: to_date must be >= from_date")

        sql = """
            DECLARE @limit INT = ?;
            DECLARE @from_date DATE = ?;
            DECLARE @to_date DATE = ?;
            DECLARE @bike_model NVARCHAR(255) = ?;

            WITH Agg AS (
                SELECT
                    BP.ProductName AS BikeModel,
                    ISNULL(P2.PartNo, OP2.SMSCode) AS PartCode,
                    ISNULL(P2.ProductName, OP2.ProductName) AS PartName,
                    COUNT(*) AS ClaimCount
                FROM DealarWarrantyClaim DWC2
                INNER JOIN DealarWarrantyClaimProduct D2
                    ON DWC2.DCWarrantyId = D2.DCWarrantyId
                LEFT JOIN Product P2
                    ON D2.ProductCode = P2.ProductCode
                LEFT JOIN OtherProduct OP2
                    ON D2.ProductCode = CONVERT(VARCHAR, OP2.ProductCode)
                INNER JOIN DealarInvoiceDetails DID
                    ON DWC2.ChassisNo = DID.ChassisNo
                INNER JOIN Product BP
                    ON DID.ProductCode = BP.ProductCode
                WHERE DWC2.Status = 1
                  AND BP.ProductName LIKE @bike_model + '%'
                  AND DWC2.WCDate >= @from_date
                  AND DWC2.WCDate < DATEADD(DAY, 1, @to_date)
                GROUP BY
                    BP.ProductName,
                    ISNULL(P2.PartNo, OP2.SMSCode),
                    ISNULL(P2.ProductName, OP2.ProductName)
            )
            SELECT TOP (@limit)
                BikeModel,
                PartCode,
                PartName,
                ClaimCount,
                ROW_NUMBER() OVER (
                    ORDER BY ClaimCount DESC, PartCode ASC
                ) AS PartRank
            FROM Agg
            ORDER BY ClaimCount DESC, PartCode ASC;
        """

        max_retries = 3
        retries = 0
        cursor = None

        while retries < max_retries:
            try:
                cursor = self.connection.cursor()
                # SQL applies prefix wildcard via: LIKE @bike_model + '%'
                cursor.execute(sql, (limit, from_date, to_date, bike_model_str))
                rows = cursor.fetchall()
                cursor.close()
                cursor = None

                out: List[dict] = []
                for r in rows:
                    out.append(
                        {
                            "bikeModel": None if r[0] is None else str(r[0]),
                            "partCode": None if r[1] is None else str(r[1]),
                            "partName": None if r[2] is None else str(r[2]),
                            "claimCount": int(r[3]),
                            "partRank": int(r[4]),
                        }
                    )
                return out
            except Exception as e:
                if cursor:
                    cursor.close()
                    cursor = None
                print(
                    f"******* {retries + 1}. Failed to fetch top warranty parts for bike model: {e.__class__.__name__} | {e}"
                )
                time.sleep(1)
                self._reconnect_to_db()
                retries += 1

        raise DataRetrievalError("FAILED TO FETCH TOP WARRANTY PARTS FOR BIKE MODEL EVEN AFTER RETRYING")

    def get_bike_model_failure_ratios(self, limit: int = 100) -> List[dict]:
        """
        Live query to SQL Server: parts failure ratio by bike model.

        Failure ratio definition (updated):
          TotalFailedChassis / TotalBikeSold

        Where:
          TotalFailedChassis = count of DISTINCT chassis numbers that had at least one claimed part.

        Output:
          [{
            'bikeCode': '...',
            'bikeName': '...',
            'totalBikeSold': 123,
            'totalFailedChassis': 45,
            'partsFailureRatio': 0.36585
          }, ...]
        """
        try:
            limit_int = int(limit)
        except Exception:
            limit_int = 100
        limit_int = max(1, min(limit_int, 500))

        sql = """
            DECLARE @limit INT = ?;

            ;WITH BikeSold AS (
                SELECT
                    BP.ProductCode AS BikeCode,
                    BP.ProductName AS BikeName,
                    COUNT(DISTINCT DID.ChassisNo) AS TotalBikeSold
                FROM DealarInvoiceMaster DIM
                INNER JOIN DealarInvoiceDetails DID
                    ON DIM.InvoiceID = DID.InvoiceID
                INNER JOIN Product BP
                    ON DID.ProductCode = BP.ProductCode
                WHERE BP.Business = 'C'
                GROUP BY
                    BP.ProductCode,
                    BP.ProductName
            ),
            FailedChassis AS (
                SELECT
                    BP.ProductCode AS BikeCode,
                    BP.ProductName AS BikeName,
                    COUNT(DISTINCT DWC.ChassisNo) AS TotalFailedChassis
                FROM DealarWarrantyClaim DWC
                INNER JOIN DealarWarrantyClaimProduct DWCP
                    ON DWC.DCWarrantyId = DWCP.DCWarrantyId
                INNER JOIN DealarInvoiceDetails DID
                    ON DWC.ChassisNo = DID.ChassisNo
                INNER JOIN Product BP
                    ON DID.ProductCode = BP.ProductCode
                WHERE DWC.Status = 1
                GROUP BY
                    BP.ProductCode,
                    BP.ProductName
            )
            SELECT TOP (@limit)
                BS.BikeCode,
                BS.BikeName,
                BS.TotalBikeSold,
                ISNULL(FC.TotalFailedChassis, 0) AS TotalFailedChassis,
                (
                    CAST(ISNULL(FC.TotalFailedChassis, 0) AS FLOAT)
                    / NULLIF(BS.TotalBikeSold, 0)
                ) AS PartsFailureRatio
            FROM BikeSold BS
            LEFT JOIN FailedChassis FC
                ON BS.BikeCode = FC.BikeCode
            WHERE (
                CAST(ISNULL(FC.TotalFailedChassis, 0) AS FLOAT)
                / NULLIF(BS.TotalBikeSold, 0)
            ) != 0
            ORDER BY PartsFailureRatio DESC;
        """

        max_retries = 3
        retries = 0
        cursor = None

        while retries < max_retries:
            try:
                cursor = self.connection.cursor()
                cursor.execute(sql, (limit_int,))
                rows = cursor.fetchall()
                cursor.close()
                cursor = None

                out: List[dict] = []
                for r in rows:
                    out.append(
                        {
                            "bikeCode": None if r[0] is None else str(r[0]),
                            "bikeName": None if r[1] is None else str(r[1]),
                            "totalBikeSold": int(r[2] or 0),
                            "totalFailedChassis": int(r[3] or 0),
                            "partsFailureRatio": None if r[4] is None else float(r[4]),
                        }
                    )
                return out
            except Exception as e:
                if cursor:
                    cursor.close()
                    cursor = None
                print(
                    f"******* {retries + 1}. Failed to fetch bike model failure ratios: {e.__class__.__name__} | {e}"
                )
                time.sleep(1)
                self._reconnect_to_db()
                retries += 1

        raise DataRetrievalError("FAILED TO FETCH BIKE MODEL FAILURE RATIOS EVEN AFTER RETRYING")

    def search_bike_names(
        self,
        query: str,
        limit: int = 20,
        offset: int = 0,
        min_len: int = 2,
    ) -> dict:
        """
        Live query to SQL Server: search distinct bike names from Product.ProductName.

        Args:
          query: user text (matched with LIKE %query%)
          limit: page size (1..200)
          offset: pagination offset (>=0)
          min_len: minimum query length to avoid full table scans

        Output:
          {
            'items': [{'bikeName': '...'}, ...],
            'totalRows': 1234,
            'limit': 20,
            'offset': 0,
            'query': '...'
          }
        """
        q = "" if query is None else str(query).strip()
        if len(q) < int(min_len):
            raise ValueError(f"Query too short. Provide at least {int(min_len)} characters.")

        try:
            limit_int = int(limit)
        except Exception:
            limit_int = 20
        limit_int = max(1, min(limit_int, 200))

        try:
            offset_int = int(offset)
        except Exception:
            offset_int = 0
        offset_int = max(0, offset_int)

        # Escape LIKE wildcards so user input behaves like "contains" search.
        # We'll use ESCAPE '\' in SQL.
        q_escaped = q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        pattern = f"%{q_escaped}%"

        sql = """
            DECLARE @limit INT = ?;
            DECLARE @offset INT = ?;
            DECLARE @pattern NVARCHAR(400) = ?;

            WITH Names AS (
                SELECT DISTINCT
                    LTRIM(RTRIM(ProductName)) AS BikeName
                FROM Product
                WHERE ProductName IS NOT NULL
                  AND LTRIM(RTRIM(ProductName)) <> ''
                  AND ProductName LIKE @pattern ESCAPE '\\'
            )
            SELECT
                BikeName,
                COUNT(*) OVER () AS TotalRows
            FROM Names
            ORDER BY BikeName ASC
            OFFSET @offset ROWS
            FETCH NEXT @limit ROWS ONLY;
        """

        max_retries = 3
        retries = 0
        cursor = None

        while retries < max_retries:
            try:
                cursor = self.connection.cursor()
                cursor.execute(sql, (limit_int, offset_int, pattern))
                rows = cursor.fetchall()
                cursor.close()
                cursor = None

                items: List[dict] = []
                total_rows = 0
                for r in rows:
                    items.append({"bikeName": None if r[0] is None else str(r[0])})
                    total_rows = int(r[1] or 0)

                return {
                    "items": items,
                    "totalRows": total_rows,
                    "limit": limit_int,
                    "offset": offset_int,
                    "query": q,
                }
            except Exception as e:
                if cursor:
                    cursor.close()
                    cursor = None
                print(f"******* {retries + 1}. Failed to search bike names: {e.__class__.__name__} | {e}")
                time.sleep(1)
                self._reconnect_to_db()
                retries += 1

        raise DataRetrievalError("FAILED TO SEARCH BIKE NAMES EVEN AFTER RETRYING")

    def get_all_bike_names(self) -> dict:
        """
        Live query to SQL Server: return all distinct bike names that appear in warranty claims.

        Output:
          {
            'items': [{'bikeName': '...'}, ...],
            'totalRows': 11506
          }
        """
        sql = """
            WITH Names AS (
                SELECT DISTINCT
                    LTRIM(RTRIM(BP.ProductName)) AS BikeName
                FROM DealarWarrantyClaim DWC
                INNER JOIN DealarInvoiceDetails DID
                    ON DWC.ChassisNo = DID.ChassisNo
                INNER JOIN Product BP
                    ON DID.ProductCode = BP.ProductCode
                INNER JOIN DealarInvoiceMaster DIM
                    ON DIM.InvoiceId = DID.InvoiceId
                WHERE DWC.Status = 1
                  AND BP.ProductName IS NOT NULL
                  AND LTRIM(RTRIM(BP.ProductName)) <> ''
            )
            SELECT BikeName
            FROM Names
            ORDER BY BikeName ASC;
        """

        max_retries = 3
        retries = 0
        cursor = None

        while retries < max_retries:
            try:
                cursor = self.connection.cursor()
                cursor.execute(sql)
                rows = cursor.fetchall()
                cursor.close()
                cursor = None

                items: List[dict] = []
                for r in rows:
                    items.append({"bikeName": None if r[0] is None else str(r[0])})

                return {"items": items, "totalRows": len(items)}
            except Exception as e:
                if cursor:
                    cursor.close()
                    cursor = None
                print(f"******* {retries + 1}. Failed to fetch all bike names: {e.__class__.__name__} | {e}")
                time.sleep(1)
                self._reconnect_to_db()
                retries += 1

        raise DataRetrievalError("FAILED TO FETCH ALL BIKE NAMES EVEN AFTER RETRYING")

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
