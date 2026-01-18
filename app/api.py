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
        rows = db_manager.get_top_warranty_parts_by_bike_model(limit=limit, months_back=months_back)

        # Transform flat rows into:
        # [
        #   {partCode, partName, totalCount, byBike: {bikeModel: claimCount}},
        #   ...
        # ]
        grouped = {}
        order = []
        for r in rows:
            key = (r.get("partCode"), r.get("partName"))
            if key not in grouped:
                grouped[key] = {
                    "partCode": r.get("partCode"),
                    "partName": r.get("partName"),
                    "totalCount": int(r.get("totalCount") or 0),
                    "byBike": {},
                }
                order.append(key)

            bike_model = r.get("bikeModel") or "Unknown"
            claim_count = int(r.get("claimCount") or 0)

            # If bike model repeats (shouldn't), sum it.
            prev = int(grouped[key]["byBike"].get(bike_model, 0))
            grouped[key]["byBike"][bike_model] = prev + claim_count

        data = [grouped[k] for k in order]
        return Response({"ret": True, "data": data, "error": None})
    except ValueError as e:
        return Response({"ret": False, "data": [], "error": str(e)}, status=400)
    except Exception as e:
        return Response(
            {"ret": False, "data": [], "error": f"{e.__class__.__name__}: {e}"},
            status=500,
        )


@extend_schema(
    operation_id="top_warranty_parts_for_bike_model",
    description=(
        "Top warranty-claimed parts for a single bike model (bikeModel + partCode + partName + claimCount + rank), "
        "queried live from SQL Server."
    ),
    parameters=[
        OpenApiParameter(
            name="bike_model",
            type=OpenApiTypes.STR,
            required=True,
            description="Bike model name (matches Product.ProductName from invoice details).",
        ),
        OpenApiParameter(
            name="limit",
            type=OpenApiTypes.INT,
            required=False,
            description="Top N parts to return (default 5, max 200).",
        ),
        OpenApiParameter(
            name="years",
            type=OpenApiTypes.INT,
            required=False,
            description="Filter to last N years (e.g. years=1). Can be combined with months.",
        ),
        OpenApiParameter(
            name="months",
            type=OpenApiTypes.INT,
            required=False,
            description="Filter to last N months (e.g. months=28). Can be combined with years.",
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
def top_warranty_parts_for_bike_model_api(request):
    bike_model = (request.query_params.get("bike_model") or "").strip()
    if not bike_model:
        return Response(
            {"ret": False, "data": [], "error": "Missing required query param: bike_model"},
            status=400,
        )

    limit_raw = request.query_params.get("limit", "5")
    try:
        limit = int(limit_raw)
    except Exception:
        return Response(
            {"ret": False, "data": [], "error": f"Invalid 'limit' query param: {limit_raw}"},
            status=400,
        )

    try:
        months_back = _parse_months_back(request.query_params)
        data = db_manager.get_top_warranty_parts_for_bike_model(
            bike_model=bike_model,
            limit=limit,
            months_back=months_back,
        )
        return Response({"ret": True, "data": data, "error": None})
    except ValueError as e:
        return Response({"ret": False, "data": [], "error": str(e)}, status=400)
    except Exception as e:
        return Response(
            {"ret": False, "data": [], "error": f"{e.__class__.__name__}: {e}"},
            status=500,
        )


@extend_schema(
    operation_id="search_bike_names",
    description="Search bike model names (Product.ProductName) for typeahead/autocomplete.",
    parameters=[
        OpenApiParameter(
            name="query",
            type=OpenApiTypes.STR,
            required=True,
            description="User input; matched using LIKE %query% (minimum 2 chars).",
        ),
        OpenApiParameter(
            name="limit",
            type=OpenApiTypes.INT,
            required=False,
            description="Page size (default 20, max 200).",
        ),
        OpenApiParameter(
            name="offset",
            type=OpenApiTypes.INT,
            required=False,
            description="Pagination offset (default 0).",
        ),
    ],
    responses={200: OpenApiTypes.OBJECT},
)
@api_view(["GET"])
def search_bike_names_api(request):
    query = (request.query_params.get("query") or "").strip()
    limit_raw = request.query_params.get("limit", "20")
    offset_raw = request.query_params.get("offset", "0")

    try:
        limit = int(limit_raw)
    except Exception:
        return Response(
            {"ret": False, "data": None, "error": f"Invalid 'limit' query param: {limit_raw}"},
            status=400,
        )

    try:
        offset = int(offset_raw)
    except Exception:
        return Response(
            {"ret": False, "data": None, "error": f"Invalid 'offset' query param: {offset_raw}"},
            status=400,
        )

    try:
        data = db_manager.search_bike_names(query=query, limit=limit, offset=offset, min_len=2)
        return Response({"ret": True, "data": data, "error": None})
    except ValueError as e:
        return Response({"ret": False, "data": None, "error": str(e)}, status=400)
    except Exception as e:
        return Response(
            {"ret": False, "data": None, "error": f"{e.__class__.__name__}: {e}"},
            status=500,
        )


