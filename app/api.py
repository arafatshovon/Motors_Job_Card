from drf_spectacular.utils import OpenApiParameter, OpenApiTypes, extend_schema
from rest_framework.decorators import api_view
from rest_framework.response import Response

from typing import Optional
from datetime import date
from dateutil.relativedelta import relativedelta
from django.utils import timezone

from app.db_management import db_manager
from app.views import jobquery
from app.prediction_utils import get_predictions_for_next_months, get_detailed_predictions


def _parse_date_range(query_params):
    """
    Required:
      - from_date=YYYY-MM-DD
    Optional:
      - to_date=YYYY-MM-DD (defaults to today)
    """
    from_raw = (query_params.get("from_date") or "").strip()
    if not from_raw:
        raise ValueError("Missing required query param: from_date (YYYY-MM-DD)")

    to_raw = (query_params.get("to_date") or "").strip()
    if not to_raw:
        to_raw = date.today().isoformat()

    try:
        from_d = date.fromisoformat(from_raw)
    except Exception:
        raise ValueError(f"Invalid from_date: {from_raw}. Expected YYYY-MM-DD")

    try:
        to_d = date.fromisoformat(to_raw)
    except Exception:
        raise ValueError(f"Invalid to_date: {to_raw}. Expected YYYY-MM-DD")

    if to_d < from_d:
        raise ValueError("Invalid date range: to_date must be >= from_date")

    return from_d, to_d


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
            name="from_date",
            type=OpenApiTypes.DATE,
            required=True,
            description="Start date (inclusive) in YYYY-MM-DD format.",
        ),
        OpenApiParameter(
            name="to_date",
            type=OpenApiTypes.DATE,
            required=False,
            description="End date (inclusive) in YYYY-MM-DD format. Defaults to today's date.",
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
        from_date, to_date = _parse_date_range(request.query_params)
        data = db_manager.get_top_warranty_parts(limit=limit, from_date=from_date, to_date=to_date)
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
            name="from_date",
            type=OpenApiTypes.DATE,
            required=True,
            description="Start date (inclusive) in YYYY-MM-DD format.",
        ),
        OpenApiParameter(
            name="to_date",
            type=OpenApiTypes.DATE,
            required=False,
            description="End date (inclusive) in YYYY-MM-DD format. Defaults to today's date.",
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
        from_date, to_date = _parse_date_range(request.query_params)
        rows = db_manager.get_top_warranty_parts_by_bike_model(limit=limit, from_date=from_date, to_date=to_date)

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
            name="from_date",
            type=OpenApiTypes.DATE,
            required=True,
            description="Start date (inclusive) in YYYY-MM-DD format.",
        ),
        OpenApiParameter(
            name="to_date",
            type=OpenApiTypes.DATE,
            required=False,
            description="End date (inclusive) in YYYY-MM-DD format. Defaults to today's date.",
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
        from_date, to_date = _parse_date_range(request.query_params)
        data = db_manager.get_top_warranty_parts_for_bike_model(
            bike_model=bike_model,
            limit=limit,
            from_date=from_date,
            to_date=to_date,
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
    operation_id="warranty_failure_ratio_by_bike_model",
    description=(
        "Bike model failure ratio based on parts claimed vs bikes sold, queried live from SQL Server. "
        "Returns (bikeCode, bikeName, totalBikeSold, totalPartsClaimed, partsFailureRatio)."
    ),
    parameters=[
        OpenApiParameter(
            name="limit",
            type=OpenApiTypes.INT,
            required=False,
            description="Number of bike models to return (default 100, max 500).",
        ),
    ],
    responses={200: OpenApiTypes.OBJECT},
)
@api_view(["GET"])
def warranty_failure_ratio_by_bike_model_api(request):
    limit_raw = request.query_params.get("limit", "100")
    try:
        limit = int(limit_raw)
    except Exception:
        return Response(
            {"ret": False, "data": [], "error": f"Invalid 'limit' query param: {limit_raw}"},
            status=400,
        )

    try:
        data = db_manager.get_bike_model_failure_ratios(limit=limit)
        return Response({"ret": True, "data": data, "error": None})
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


@extend_schema(
    operation_id="all_bike_names",
    description="Return all distinct bike model names (Product.ProductName). No input required.",
    responses={200: OpenApiTypes.OBJECT},
)
@api_view(["GET"])
def all_bike_names_api(request):
    try:
        data = db_manager.get_all_bike_names()
        return Response({"ret": True, "data": data, "error": None})
    except Exception as e:
        return Response(
            {"ret": False, "data": None, "error": f"{e.__class__.__name__}: {e}"},
            status=500,
        )


@extend_schema(
    operation_id="predict_warranty_parts",
    description=(
        "Predict warranty parts failures for the next N months using CatBoost model. "
        "Returns aggregated predictions by month, by part, and by bike model. "
        "Uses top N bike models and top N parts for prediction."
    ),
    parameters=[
        OpenApiParameter(
            name="months",
            type=OpenApiTypes.INT,
            required=False,
            description="Number of months to forecast (default 6, max 12).",
        ),
        OpenApiParameter(
            name="top_bike_models",
            type=OpenApiTypes.INT,
            required=False,
            description="Number of top bike models to include (default 20, max 50).",
        ),
        OpenApiParameter(
            name="top_parts",
            type=OpenApiTypes.INT,
            required=False,
            description="Number of top parts to include (default 20, max 50).",
        ),
    ],
    responses={200: OpenApiTypes.OBJECT},
)
@api_view(["GET"])
def predict_warranty_parts_api(request):
    """
    Predict warranty parts failures for the next N months.

    Returns:
        {
            "ret": True/False,
            "data": {
                "monthly": {"columns": [...], "data": [[...], ...]},
                "by_part": {"columns": [...], "data": [[...], ...]},
                "by_bike_model": {"columns": [...], "data": [[...], ...]},
                "total_predicted": float,
                "forecast_period": {"start": "YYYY-MM-DD", "end": "YYYY-MM-DD"}
            },
            "error": None or error message
        }
    """
    # Parse parameters
    months_raw = request.query_params.get("months", "6")
    top_bike_models_raw = request.query_params.get("top_bike_models", "20")
    top_parts_raw = request.query_params.get("top_parts", "20")

    try:
        months = min(int(months_raw), 12)
    except Exception:
        return Response(
            {"ret": False, "data": None, "error": f"Invalid 'months' query param: {months_raw}"},
            status=400,
        )

    try:
        top_bike_models = min(int(top_bike_models_raw), 50)
    except Exception:
        return Response(
            {"ret": False, "data": None, "error": f"Invalid 'top_bike_models' query param: {top_bike_models_raw}"},
            status=400,
        )

    try:
        top_parts = min(int(top_parts_raw), 50)
    except Exception:
        return Response(
            {"ret": False, "data": None, "error": f"Invalid 'top_parts' query param: {top_parts_raw}"},
            status=400,
        )

    try:
        data = get_predictions_for_next_months(
            n_months=months,
            top_n_bike_models=top_bike_models,
            top_n_parts=top_parts
        )
        return Response({"ret": True, "data": data, "error": None})
    except FileNotFoundError as e:
        return Response(
            {"ret": False, "data": None, "error": f"Model or data not found: {e}"},
            status=404,
        )
    except Exception as e:
        return Response(
            {"ret": False, "data": None, "error": f"{e.__class__.__name__}: {e}"},
            status=500,
        )


@extend_schema(
    operation_id="predict_warranty_parts_detailed",
    description=(
        "Get detailed warranty parts failure predictions for each combination of "
        "ProductName, BikeModel, and RegionName, with live monthly actuals for the five "
        "completed months before the current month. Forecasts begin in the current month."
    ),
    parameters=[
        OpenApiParameter(
            name="months",
            type=OpenApiTypes.INT,
            required=False,
            description="Number of months to forecast (default 6, max 12).",
        ),
        OpenApiParameter(
            name="top_bike_models",
            type=OpenApiTypes.INT,
            required=False,
            description="Number of top bike models to include (default 20, max 50).",
        ),
        OpenApiParameter(
            name="top_parts",
            type=OpenApiTypes.INT,
            required=False,
            description="Number of top parts to include (default 20, max 50).",
        ),
    ],
    responses={200: OpenApiTypes.OBJECT},
)
@api_view(["GET"])
def predict_warranty_parts_detailed_api(request):
    """
    Get detailed predictions for each combination.

    Returns:
        {
            "ret": True/False,
            "data": {
                "columns": ["date", "ProductName", "BikeModel", "RegionName", "PredictedClaimCount"],
                "data": [[...], [...], ...]
            },
            "error": None or error message
        }
    """
    months_raw = request.query_params.get("months", "6")
    top_bike_models_raw = request.query_params.get("top_bike_models", "20")
    top_parts_raw = request.query_params.get("top_parts", "20")

    try:
        months = max(1, min(int(months_raw), 12))
    except Exception:
        return Response(
            {"ret": False, "data": None, "error": f"Invalid 'months' query param: {months_raw}"},
            status=400,
        )

    try:
        top_bike_models = min(int(top_bike_models_raw), 50)
    except Exception:
        return Response(
            {"ret": False, "data": None, "error": f"Invalid 'top_bike_models' query param: {top_bike_models_raw}"},
            status=400,
        )

    try:
        top_parts = min(int(top_parts_raw), 50)
    except Exception:
        return Response(
            {"ret": False, "data": None, "error": f"Invalid 'top_parts' query param: {top_parts_raw}"},
            status=400,
        )

    try:
        current_month_start = timezone.localdate().replace(day=1)
        history_start = current_month_start - relativedelta(months=5)
        history_rows = db_manager.get_monthly_warranty_claim_counts(
            from_date=history_start,
            to_date_exclusive=current_month_start,
        )

        data = get_detailed_predictions(
            n_months=months,
            top_n_bike_models=top_bike_models,
            top_n_parts=top_parts,
            source_df=db_manager.get_warranty_data_df(),
            forecast_start=current_month_start,
        )
        data["historical"] = {
            "columns": ["date", "ClaimCount"],
            "data": [[row["date"], row["ClaimCount"]] for row in history_rows],
        }
        data["history_period"] = {
            "start": history_start.isoformat(),
            "end": (current_month_start - relativedelta(days=1)).isoformat(),
        }
        data["forecast_period"] = {
            "start": current_month_start.isoformat(),
            "end": (current_month_start + relativedelta(months=months - 1)).isoformat(),
        }
        return Response({"ret": True, "data": data, "error": None})
    except FileNotFoundError as e:
        return Response(
            {"ret": False, "data": None, "error": f"Model or data not found: {e}"},
            status=404,
        )
    except Exception as e:
        return Response(
            {"ret": False, "data": None, "error": f"{e.__class__.__name__}: {e}"},
            status=500,
        )
