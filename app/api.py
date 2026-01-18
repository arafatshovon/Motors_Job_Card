from drf_spectacular.utils import OpenApiParameter, OpenApiTypes, extend_schema
from rest_framework.decorators import api_view
from rest_framework.response import Response

from typing import Optional

from app.db_management import db_manager
from app.views import jobquery


def _parse_months_back(query_params) -> Optional[int]:
    """
    Supported inputs (optional):
      - years=1
      - months=6
      - period=1y / 2y / 6m / 18m

    Returns:
      - int months_back (>= 1) or None if not provided
    """
    period = query_params.get("period")
    years = query_params.get("years")
    months = query_params.get("months")

    if period:
        s = str(period).strip().lower().replace(" ", "")
        if s.endswith("y"):
            n = int(s[:-1])
            return max(1, n * 12)
        if s.endswith("m"):
            n = int(s[:-1])
            return max(1, n)
        raise ValueError("Invalid 'period'. Use formats like '1y' or '6m'.")

    if years is None and months is None:
        return None

    y = 0 if years is None else int(years)
    m = 0 if months is None else int(months)
    total = (y * 12) + m
    return max(1, total)


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
    description="Top warranty-claimed parts (partCode, partName, claimCount), queried live from SQL Server.",
    parameters=[
        OpenApiParameter(
            name="limit",
            type=OpenApiTypes.INT,
            required=False,
            description="Number of items to return (default 30, max 200).",
        ),
        OpenApiParameter(
            name="years",
            type=OpenApiTypes.INT,
            required=False,
            description="Filter to last N years (e.g. years=2). Can be combined with months.",
        ),
        OpenApiParameter(
            name="months",
            type=OpenApiTypes.INT,
            required=False,
            description="Filter to last N months (e.g. months=6). Can be combined with years.",
        ),
        OpenApiParameter(
            name="period",
            type=OpenApiTypes.STR,
            required=False,
            description="Filter using a single value like '1y' or '18m'. Overrides years/months if provided.",
        ),
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

    try:
        months_back = _parse_months_back(request.query_params)
        data = db_manager.get_top_warranty_parts(limit=limit, months_back=months_back)
        return Response({"ret": True, "data": data, "error": None})
    except ValueError as e:
        return Response({"ret": False, "data": [], "error": str(e)}, status=400)
    except Exception as e:
        return Response(
            {"ret": False, "data": [], "error": f"{e.__class__.__name__}: {e}"},
            status=500,
        )


@extend_schema(
    operation_id="top_warranty_parts_by_bike_model",
    description=(
        "Top warranty-claimed parts overall, broken down by bike model (bikeModel + claimCount per part), "
        "queried live from SQL Server."
    ),
    parameters=[
        OpenApiParameter(
            name="limit",
            type=OpenApiTypes.INT,
            required=False,
            description="Top N parts overall (default 30, max 200).",
        ),
        OpenApiParameter(
            name="years",
            type=OpenApiTypes.INT,
            required=False,
            description="Filter to last N years (e.g. years=2). Can be combined with months.",
        ),
        OpenApiParameter(
            name="months",
            type=OpenApiTypes.INT,
            required=False,
            description="Filter to last N months (e.g. months=6). Can be combined with years.",
        ),
        OpenApiParameter(
            name="period",
            type=OpenApiTypes.STR,
            required=False,
            description="Filter using a single value like '1y' or '18m'. Overrides years/months if provided.",
        ),
    ],
    responses={200: OpenApiTypes.OBJECT},
)
@api_view(["GET"])
def top_warranty_parts_by_bike_model_api(request):
    limit_raw = request.query_params.get("limit", "30")
    try:
        limit = int(limit_raw)
    except Exception:
        return Response(
            {"ret": False, "data": [], "error": f"Invalid 'limit' query param: {limit_raw}"},
            status=400,
        )

    try:
        months_back = _parse_months_back(request.query_params)
        data = db_manager.get_top_warranty_parts_by_bike_model(limit=limit, months_back=months_back)
        return Response({"ret": True, "data": data, "error": None})
    except ValueError as e:
        return Response({"ret": False, "data": [], "error": str(e)}, status=400)
    except Exception as e:
        return Response(
            {"ret": False, "data": [], "error": f"{e.__class__.__name__}: {e}"},
            status=500,
        )


