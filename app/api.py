from drf_spectacular.utils import OpenApiParameter, OpenApiTypes, extend_schema
from rest_framework.decorators import api_view
from rest_framework.response import Response

from app.db_management import db_manager
from app.views import jobquery


@extend_schema(
    operation_id="checkout_suggestions",
    description="Get suggested parts for a given chassis and mileage.",
    parameters=[
        OpenApiParameter(name="chassis", type=OpenApiTypes.STR, required=True),
        OpenApiParameter(name="mileage", type=OpenApiTypes.INT, required=True),
    ],
    responses={200: OpenApiTypes.OBJECT},
)
@api_view(["GET"])
def checkout_api(request):
    # jobquery() expects a Django HttpRequest; DRF wraps it as request._request
    django_request = getattr(request, "_request", request)
    data = jobquery(django_request, method="GET")
    return Response(data)


@extend_schema(
    operation_id="top_warranty_parts",
    description="Top warranty-claimed parts (partCode, partName, claimCount).",
    parameters=[
        OpenApiParameter(
            name="limit",
            type=OpenApiTypes.INT,
            required=False,
            description="Number of items to return (default 30, max 200).",
        )
    ],
    responses={200: OpenApiTypes.OBJECT},
)
@api_view(["GET"])
def top_warranty_parts_api(request):
    limit_raw = request.query_params.get("limit", "30")
    try:
        limit = int(limit_raw)
    except Exception:
        return Response(
            {"ret": False, "data": [], "error": f"Invalid 'limit' query param: {limit_raw}"},
            status=400,
        )

    limit = max(1, min(limit, 200))

    df = db_manager.get_converted_warranty_df()
    if df is None or getattr(df, "empty", True):
        return Response({"ret": True, "data": [], "error": None})

    cols = {"part_code", "product_name"}
    if not cols.issubset(set(df.columns)):
        return Response(
            {
                "ret": False,
                "data": [],
                "error": f"Warranty dataframe missing required columns: {sorted(cols)}",
            },
            status=500,
        )

    top_df = (
        df[["part_code", "product_name"]]
        .dropna()
        .groupby(["part_code", "product_name"], as_index=False)
        .size()
        .rename(columns={"size": "claimCount"})
        .sort_values(["claimCount", "part_code"], ascending=[False, True])
        .head(limit)
    )

    data = [
        {
            "partCode": str(row["part_code"]),
            "partName": str(row["product_name"]),
            "claimCount": int(row["claimCount"]),
        }
        for _, row in top_df.iterrows()
    ]

    return Response({"ret": True, "data": data, "error": None})


