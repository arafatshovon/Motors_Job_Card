"""Shared mapped-model eligibility for warranty reports."""


def mapped_claims_ctes(groups, *, include_date_filter=False):
    """Return mapped qualifying claims and bound mapping parameters.

    The caller supplies @from_date/@to_date when date filtering is enabled.
    Chassis numbers remain available so failure ratios can count bikes rather
    than summing the claim counts of individual parts.
    """
    pairs = [(model, group) for group, models in groups.items() for model in models]
    values = ", ".join(
        "(CAST(? AS NVARCHAR(255)), CAST(? AS NVARCHAR(255)))" for _ in pairs
    )
    date_filter = """
          AND DWC.WCDate >= @from_date
          AND DWC.WCDate < DATEADD(DAY, 1, @to_date)
    """ if include_date_filter else ""
    sql = f"""
        ModelMapping AS (
            SELECT RawModel, MappedModel
            FROM (VALUES {values}) AS M(RawModel, MappedModel)
        ),
        Claims AS (
            SELECT DISTINCT
                DWC.DCWarrantyId,
                DWC.ChassisNo,
                D.ProductCode,
                MM.MappedModel AS BikeModel
            FROM DealarWarrantyClaim DWC
            INNER JOIN DealarWarrantyClaimProduct D
                ON D.DCWarrantyId = DWC.DCWarrantyId
            INNER JOIN ViewtblJobCardDetailSparepartWork SP
                ON SP.JobCardNo = DWC.JobCardNo AND SP.ItemCode = D.ProductCode
            INNER JOIN DealarInvoiceDetails DID
                ON DID.ChassisNo = DWC.ChassisNo
            INNER JOIN Product BP
                ON BP.ProductCode = DID.ProductCode
            INNER JOIN ModelMapping MM
                ON LTRIM(RTRIM(BP.ProductName)) = MM.RawModel
            WHERE DWC.Status = 1
              AND DWC.ChassisNo <> ''
              AND ISNULL(D.UnitPrice, SP.WarrantyPrice) * D.Quantity > 0
              {date_filter}
        )
    """
    return sql, tuple(value for pair in pairs for value in pair)


def bike_model_failure_ratio_sql(groups):
    """Count all-time unique sold/failed chassis across each entire group.

    Sold means an invoice detail with an existing invoice master and a bike
    product (Business = 'C'), following the existing report's sales definition.
    No invoice status, return, or sale-date rules are inferred here.
    """
    claims_sql, mapping_params = mapped_claims_ctes(groups)
    sql = f"""
        DECLARE @limit INT = ?;

        ;WITH {claims_sql},
        BikeSold AS (
            SELECT
                MM.MappedModel AS BikeName,
                COUNT(DISTINCT DID.ChassisNo) AS TotalBikeSold
            FROM DealarInvoiceMaster DIM
            INNER JOIN DealarInvoiceDetails DID ON DIM.InvoiceID = DID.InvoiceID
            INNER JOIN Product BP ON DID.ProductCode = BP.ProductCode
            INNER JOIN ModelMapping MM ON LTRIM(RTRIM(BP.ProductName)) = MM.RawModel
            WHERE BP.Business = 'C'
              AND LTRIM(RTRIM(DID.ChassisNo)) <> ''
            GROUP BY MM.MappedModel
        ),
        FailedChassis AS (
            SELECT BikeModel, COUNT(DISTINCT ChassisNo) AS TotalFailedChassis
            FROM Claims
            GROUP BY BikeModel
        )
        SELECT TOP (@limit)
            CAST(NULL AS NVARCHAR(255)) AS BikeCode,
            BS.BikeName,
            BS.TotalBikeSold,
            ISNULL(FC.TotalFailedChassis, 0) AS TotalFailedChassis,
            CAST(ISNULL(FC.TotalFailedChassis, 0) AS FLOAT)
                / NULLIF(BS.TotalBikeSold, 0) AS PartsFailureRatio
        FROM BikeSold BS
        LEFT JOIN FailedChassis FC ON BS.BikeName = FC.BikeModel
        ORDER BY PartsFailureRatio DESC, BS.BikeName;
    """
    return sql, mapping_params
