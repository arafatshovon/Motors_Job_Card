"""
Warranty Parts Prediction Utilities

This module provides functions for:
1. Preprocessing warranty data into monthly enhanced features
2. Making batch recursive forecasts using trained CatBoost model
"""

import os
import pickle
import numpy as np
import pandas as pd
from itertools import product
from app.bike_model_mapping import load_bike_model_mapping

# Paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEST_DIR = os.path.join(BASE_DIR, 'test')
CLUSTER_DATA_DIR = os.path.join(BASE_DIR, 'cluster_data')

# Model + metadata are stored in cluster_data inside the container
MODEL_PATH = os.path.join(CLUSTER_DATA_DIR, 'catboost_enhanced_model.cbm')
METADATA_PATH = os.path.join(CLUSTER_DATA_DIR, 'model_metadata.pkl')
WARRANTY_DATA_PATH = os.path.join(CLUSTER_DATA_DIR, 'warranty_data.csv')
ENHANCED_DATA_PATH = os.path.join(CLUSTER_DATA_DIR, 'df_monthly_enhanced_filled.csv')

# Use the same authoritative mapping as the warranty reports and dashboard.
BIKE_MODEL_MAPPING = load_bike_model_mapping()
BIKE_VARIANT_TO_MODEL = {
    " ".join(variant.split()).casefold(): model
    for model, variants in BIKE_MODEL_MAPPING.items()
    for variant in variants
}


def get_bike_model(bike_name: str):
    """Resolve a detailed variant to Motors' mapped name; unmapped names stay absent."""
    if pd.isna(bike_name):
        return None
    normalized = " ".join(str(bike_name).split()).casefold()
    return BIKE_VARIANT_TO_MODEL.get(normalized)


def preprocess_warranty_data(
    warranty_data_path: str = None,
    save_path: str = None,
    source_df: pd.DataFrame = None,
    end_exclusive=None,
) -> pd.DataFrame:
    """
    Preprocess warranty_data.csv into df_monthly_enhanced_filled.

    Args:
        warranty_data_path: Path to warranty_data.csv (default: cluster_data/warranty_data.csv)
        save_path: Optional path to save the processed data. CSV input defaults to the
            enhanced-data path; DataFrame input is processed in memory by default.
        source_df: Optional live warranty rows from the database.
        end_exclusive: Optional exclusive cutoff date for warranty dates.

    Returns:
        DataFrame with monthly enhanced features
    """
    if source_df is None:
        if warranty_data_path is None:
            warranty_data_path = WARRANTY_DATA_PATH
        if save_path is None:
            save_path = ENHANCED_DATA_PATH
        warranty_data_full = pd.read_csv(warranty_data_path)
    else:
        warranty_data_full = source_df.copy()

    # Map the DBManager field names to the names used by the model's training data.
    source_columns = {str(column).lower(): column for column in warranty_data_full.columns}
    column_aliases = {
        "RegionName": "region",
        "WCDate": "warranty_date",
        "ProductCode": "part_code",
        "ProductName": "product_name",
        "BikeName": "bike_model",
        "InvoiceDate": "inv_date",
        "Mileage": "mileage",
        "TotalCost": "total_cost",
    }
    for target, alias in column_aliases.items():
        if target not in warranty_data_full.columns and alias in source_columns:
            warranty_data_full = warranty_data_full.rename(
                columns={source_columns[alias]: target}
            )

    # Rename column if needed
    if 'InvoiceDetails' in warranty_data_full.columns and 'InvoiceDate' not in warranty_data_full.columns:
        warranty_data_full = warranty_data_full.rename(columns={'InvoiceDetails': 'InvoiceDate'})

    # Rebuild group membership from detailed names, even if an old BikeModel is
    # present. Old aggregated groups cannot be reliably split into the new groups.
    if 'BikeName' not in warranty_data_full.columns:
        raise ValueError("Warranty data must include detailed BikeName values for Motors model mapping")
    warranty_data_full['BikeModel'] = warranty_data_full['BikeName'].apply(get_bike_model)
    warranty_data_full = warranty_data_full.dropna(subset=['BikeModel'])
    if warranty_data_full.empty:
        raise ValueError("No warranty rows match the Motors bike model mapping")

    # Create enhanced dataset
    warranty_enhanced = warranty_data_full.copy()

    # Convert dates
    warranty_enhanced['WCDate'] = pd.to_datetime(warranty_enhanced['WCDate'], errors='coerce')
    warranty_enhanced['InvoiceDate'] = pd.to_datetime(warranty_enhanced['InvoiceDate'], errors='coerce')
    if end_exclusive is not None:
        warranty_enhanced = warranty_enhanced[
            warranty_enhanced['WCDate'] < pd.Timestamp(end_exclusive)
        ]
    warranty_enhanced = warranty_enhanced.dropna(
        subset=['WCDate', 'InvoiceDate', 'ProductCode', 'ProductName', 'BikeModel', 'RegionName']
    )

    # Calculate bike age in months
    warranty_enhanced['BikeAgeMonths'] = (
        (warranty_enhanced['WCDate'] - warranty_enhanced['InvoiceDate']).dt.days / 30.44
    ).round(0)

    # Clean Mileage
    warranty_enhanced['Mileage'] = warranty_enhanced['Mileage'].astype(str).str.replace(r'[^\d.]', '', regex=True)
    warranty_enhanced['Mileage'] = pd.to_numeric(warranty_enhanced['Mileage'], errors='coerce').fillna(0)
    warranty_enhanced['TotalCost'] = pd.to_numeric(
        warranty_enhanced['TotalCost'], errors='coerce'
    ).fillna(0)

    # Extract time features
    warranty_enhanced['year'] = warranty_enhanced['WCDate'].dt.year
    warranty_enhanced['month'] = warranty_enhanced['WCDate'].dt.month
    warranty_enhanced['quarter'] = warranty_enhanced['WCDate'].dt.quarter
    warranty_enhanced['is_holiday_season'] = warranty_enhanced['month'].isin([12, 1]).astype(int)

    # Keep relevant columns
    enhanced_columns = ['RegionName', 'WCDate', 'ProductCode', 'ProductName',
                       'BikeModel', 'year', 'month', 'quarter',
                       'is_holiday_season', 'BikeAgeMonths', 'Mileage', 'TotalCost']

    warranty_enhanced = warranty_enhanced[enhanced_columns].copy()
    warranty_enhanced = warranty_enhanced.sort_values(by='WCDate')

    # Group by ProductName, BikeModel, RegionName, year, month
    df_monthly_enhanced = (
        warranty_enhanced
        .groupby(["ProductName", "BikeModel", "RegionName", "year", "month"])
        .agg({
            'ProductCode': 'count',
            'BikeAgeMonths': 'mean',
            'Mileage': 'mean',
            'TotalCost': 'mean',
            'quarter': 'first',
            'is_holiday_season': 'first'
        })
        .reset_index()
        .rename(columns={'ProductCode': 'ClaimCount'})
    )

    df_monthly_enhanced["date"] = pd.to_datetime(
        df_monthly_enhanced["year"].astype(str) + "-" +
        df_monthly_enhanced["month"].astype(str) + "-01"
    )

    # Fill each time series explicitly. Pandas 3 excludes grouping columns from
    # DataFrameGroupBy.apply, but the fill function needs those columns to restore
    # the series labels after reindexing.
    group_columns = ["ProductName", "BikeModel", "RegionName"]
    filled_groups = []
    for group_keys, group_df in df_monthly_enhanced.groupby(group_columns, sort=False):
        filled_group = _fill_missing_months_enhanced(group_df.copy())
        for column, value in zip(group_columns, group_keys):
            filled_group[column] = value
        filled_groups.append(filled_group)

    if filled_groups:
        df_monthly_enhanced_filled = pd.concat(filled_groups, ignore_index=True)
    else:
        df_monthly_enhanced_filled = df_monthly_enhanced.copy()

    # Add lag and rolling features
    df_monthly_enhanced_filled = _add_lag_and_rolling_features(df_monthly_enhanced_filled)

    # Drop rows with NaN values
    df_model_enhanced = df_monthly_enhanced_filled.dropna().reset_index(drop=True)

    # Save CSV-based preprocessing as before; live DB preprocessing stays in memory.
    if save_path:
        save_directory = os.path.dirname(save_path)
        if save_directory:
            os.makedirs(save_directory, exist_ok=True)
        df_model_enhanced.to_csv(save_path, index=False)

    return df_model_enhanced


def _fill_missing_months_enhanced(group: pd.DataFrame) -> pd.DataFrame:
    """Fill missing months for a group."""
    if len(group) < 2:
        return group

    full_range = pd.date_range(
        start=group["date"].min(),
        end=group["date"].max(),
        freq="MS"
    )

    group = (
        group
        .set_index("date")
        .reindex(full_range)
        .rename_axis("date")
        .reset_index()
    )

    # Fill categorical columns
    for col in ["ProductName", "BikeModel", "RegionName"]:
        first_val = group[col].dropna().iloc[0] if len(group[col].dropna()) > 0 else 'Unknown'
        group[col] = group[col].fillna(first_val)

    # Fill numerical columns
    group["ClaimCount"] = group["ClaimCount"].fillna(0)
    group["BikeAgeMonths"] = group["BikeAgeMonths"].ffill().fillna(0)
    group["Mileage"] = group["Mileage"].ffill().fillna(0)
    group["TotalCost"] = group["TotalCost"].ffill().fillna(0)

    # Recreate time features
    group["year"] = group["date"].dt.year
    group["month"] = group["date"].dt.month
    group["quarter"] = group["date"].dt.quarter
    group["is_holiday_season"] = group["month"].isin([12, 1]).astype(int)

    return group


def _add_lag_and_rolling_features(df: pd.DataFrame) -> pd.DataFrame:
    """Add lag and rolling features to the DataFrame."""
    df = df.copy()

    # Lag features
    LAGS = [1, 2, 3, 6]
    for lag in LAGS:
        df[f"lag_{lag}"] = (
            df.groupby(["ProductName", "BikeModel", "RegionName"])["ClaimCount"]
            .shift(lag)
        )

    # Rolling features
    WINDOWS = [2, 3, 6]
    for window in WINDOWS:
        df[f"roll_mean_{window}"] = (
            df.groupby(["ProductName", "BikeModel", "RegionName"])["ClaimCount"]
            .shift(1).rolling(window).mean()
        )
        df[f"roll_std_{window}"] = (
            df.groupby(["ProductName", "BikeModel", "RegionName"])["ClaimCount"]
            .shift(1).rolling(window).std()
        )
        df[f"roll_max_{window}"] = (
            df.groupby(["ProductName", "BikeModel", "RegionName"])["ClaimCount"]
            .shift(1).rolling(window).max()
        )

    # EMA
    df['ema_3'] = (
        df.groupby(["ProductName", "BikeModel", "RegionName"])["ClaimCount"]
        .shift(1).ewm(span=3, adjust=False).mean()
    )

    # Expanding mean
    df['expanding_mean'] = (
        df.groupby(["ProductName", "BikeModel", "RegionName"])["ClaimCount"]
        .shift(1).expanding().mean()
    )

    return df


def load_model_and_metadata():
    """Load the trained CatBoost model and metadata."""
    if not os.path.exists(MODEL_PATH):
        raise FileNotFoundError(f"Model not found at {MODEL_PATH}")
    if not os.path.exists(METADATA_PATH):
        raise FileNotFoundError(f"Metadata not found at {METADATA_PATH}")

    from catboost import CatBoostRegressor

    model = CatBoostRegressor()
    model.load_model(MODEL_PATH)

    with open(METADATA_PATH, 'rb') as f:
        metadata = pickle.load(f)

    return model, metadata


def batch_recursive_forecast(
    model,
    df_historical: pd.DataFrame,
    bike_models: list,
    parts: list,
    regions: list,
    n_months: int = 6,
    feature_columns: list = None,
    cat_features: list = None,
    forecast_start=None,
) -> pd.DataFrame:
    """
    Efficiently forecast using batch prediction with vectorized operations.

    Args:
        model: Trained CatBoost model
        df_historical: Historical data with enhanced features
        bike_models: List of bike models to forecast
        parts: List of parts to forecast
        regions: List of regions to forecast
        n_months: Number of months to forecast
        feature_columns: List of feature columns
        cat_features: List of categorical feature names

    Returns:
        DataFrame with predictions
    """
    latest_date = df_historical['date'].max()
    if forecast_start is None:
        forecast_start = latest_date + pd.DateOffset(months=1)
    else:
        forecast_start = pd.Timestamp(forecast_start).to_period('M').to_timestamp()
    future_dates = pd.date_range(start=forecast_start, periods=n_months, freq='MS')

    # Get last data for each combination
    last_data = (
        df_historical
        .sort_values('date')
        .groupby(['ProductName', 'BikeModel', 'RegionName'])
        .last()
        .reset_index()
    )

    # Get claim history
    claim_history = (
        df_historical
        .sort_values('date')
        .groupby(['ProductName', 'BikeModel', 'RegionName'])
        .apply(lambda x: x['ClaimCount'].values[-6:].tolist(), include_groups=False)
        .reset_index()
        .rename(columns={0: 'recent_claims'})
    )

    # Merge
    combo_data = last_data.merge(claim_history, on=['ProductName', 'BikeModel', 'RegionName'], how='left')

    all_predictions = []

    for month_idx, future_date in enumerate(future_dates):
        year = future_date.year
        month = future_date.month
        quarter = (month - 1) // 3 + 1
        is_holiday = 1 if month in [12, 1] else 0

        rows = []
        for _, row in combo_data.iterrows():
            recent = row['recent_claims'] if isinstance(row['recent_claims'], list) else [0] * 6
            while len(recent) < 6:
                recent = [0] + recent

            feature_row = {
                'date': future_date,
                'ProductName': row['ProductName'],
                'BikeModel': row['BikeModel'],
                'RegionName': row['RegionName'],
                'year': year,
                'month': month,
                'quarter': quarter,
                'is_holiday_season': is_holiday,
                'BikeAgeMonths': row['BikeAgeMonths'] + month_idx + 1,
                'Mileage': row['Mileage'],
                'TotalCost': row['TotalCost'],
                'lag_1': recent[-1],
                'lag_2': recent[-2] if len(recent) >= 2 else 0,
                'lag_3': recent[-3] if len(recent) >= 3 else 0,
                'lag_6': recent[-6] if len(recent) >= 6 else 0,
                'roll_mean_2': np.mean(recent[-2:]),
                'roll_std_2': np.std(recent[-2:]),
                'roll_max_2': np.max(recent[-2:]),
                'roll_mean_3': np.mean(recent[-3:]),
                'roll_std_3': np.std(recent[-3:]),
                'roll_max_3': np.max(recent[-3:]),
                'roll_mean_6': np.mean(recent[-6:]),
                'roll_std_6': np.std(recent[-6:]),
                'roll_max_6': np.max(recent[-6:]),
                'ema_3': recent[-1] * 0.5 + recent[-2] * 0.25 + recent[-3] * 0.125 if len(recent) >= 3 else recent[-1],
                'expanding_mean': np.mean(recent)
            }
            rows.append(feature_row)

        # Batch prediction
        X_batch = pd.DataFrame(rows)[feature_columns]
        for col in cat_features:
            X_batch[col] = X_batch[col].astype('category')

        # Ensure datetime features are numeric if not categorical
        for col in X_batch.columns:
            if col in cat_features:
                continue
            if pd.api.types.is_datetime64_any_dtype(X_batch[col]):
                X_batch[col] = X_batch[col].astype('int64')
            elif X_batch[col].dtype == object:
                parsed = pd.to_datetime(X_batch[col], errors='coerce')
                if pd.api.types.is_datetime64_any_dtype(parsed):
                    X_batch[col] = parsed.astype('int64')

        predictions = model.predict(X_batch)
        predictions = np.maximum(0, predictions)

        for i, row in enumerate(rows):
            row['PredictedClaimCount'] = predictions[i]
            all_predictions.append(row.copy())

        # Update claim history for next iteration
        for i, (idx, row) in enumerate(combo_data.iterrows()):
            recent = row['recent_claims'] if isinstance(row['recent_claims'], list) else [0] * 6
            recent = recent.copy()
            recent.append(predictions[i])
            if len(recent) > 6:
                recent = recent[-6:]
            combo_data.at[idx, 'recent_claims'] = recent

    return pd.DataFrame(all_predictions)


def get_predictions_for_next_months(n_months: int = 6, top_n_bike_models: int = 20, top_n_parts: int = 20) -> dict:
    """
    Generate predictions for the next n months.

    Args:
        n_months: Number of months to forecast
        top_n_bike_models: Number of top bike models to include
        top_n_parts: Number of top parts to include

    Returns:
        Dictionary with columns and data for Gradio
    """
    # Load model and metadata
    model, metadata = load_model_and_metadata()
    feature_columns = metadata['feature_columns']
    cat_features = metadata['categorical_features']

    # Rebuild from raw variant names. The legacy enhanced CSV contains old
    # aggregated names and must not be used as a mapping source.
    df_enhanced = preprocess_warranty_data()
    if df_enhanced.empty:
        raise ValueError("No mapped warranty history is available for prediction")

    # Get top bike models and parts
    top_bike_models = (
        df_enhanced.groupby('BikeModel')['ClaimCount']
        .sum().sort_values(ascending=False)
        .head(top_n_bike_models).index.tolist()
    )

    top_parts = (
        df_enhanced.groupby('ProductName')['ClaimCount']
        .sum().sort_values(ascending=False)
        .head(top_n_parts).index.tolist()
    )

    all_regions = df_enhanced['RegionName'].unique().tolist()

    # Filter data
    df_filtered = df_enhanced[
        (df_enhanced['BikeModel'].isin(top_bike_models)) &
        (df_enhanced['ProductName'].isin(top_parts))
    ].copy()

    # Generate predictions
    predictions_df = batch_recursive_forecast(
        model=model,
        df_historical=df_filtered,
        bike_models=top_bike_models,
        parts=top_parts,
        regions=all_regions,
        n_months=n_months,
        feature_columns=feature_columns,
        cat_features=cat_features
    )

    # Aggregate by month
    monthly_predictions = (
        predictions_df
        .groupby('date')['PredictedClaimCount']
        .sum()
        .reset_index()
    )
    monthly_predictions['date'] = monthly_predictions['date'].dt.strftime('%Y-%m-%d')

    # Aggregate by part
    parts_predictions = (
        predictions_df
        .groupby('ProductName')['PredictedClaimCount']
        .sum()
        .sort_values(ascending=False)
        .reset_index()
    )

    # Aggregate by bike model
    bike_model_predictions = (
        predictions_df
        .groupby('BikeModel')['PredictedClaimCount']
        .sum()
        .sort_values(ascending=False)
        .reset_index()
    )

    # Prepare response
    result = {
        'monthly': {
            'columns': monthly_predictions.columns.tolist(),
            'data': monthly_predictions.values.tolist()
        },
        'by_part': {
            'columns': parts_predictions.columns.tolist(),
            'data': parts_predictions.values.tolist()
        },
        'by_bike_model': {
            'columns': bike_model_predictions.columns.tolist(),
            'data': bike_model_predictions.values.tolist()
        },
        'total_predicted': float(predictions_df['PredictedClaimCount'].sum()),
        'forecast_period': {
            'start': predictions_df['date'].min().strftime('%Y-%m-%d'),
            'end': predictions_df['date'].max().strftime('%Y-%m-%d')
        }
    }

    return result


def get_detailed_predictions(
    n_months: int = 6,
    top_n_bike_models: int = 20,
    top_n_parts: int = 20,
    source_df: pd.DataFrame = None,
    forecast_start=None,
) -> dict:
    """
    Get detailed predictions DataFrame in Gradio-compatible format.

    Returns:
        Dictionary with columns and data lists
    """
    # Load model and metadata
    model, metadata = load_model_and_metadata()
    feature_columns = metadata['feature_columns']
    cat_features = metadata['categorical_features']

    # Both live rows and the CSV fallback must be mapped from raw BikeName.
    # Never reuse the old enhanced CSV: merged old groups cannot be split again.
    df_enhanced = preprocess_warranty_data(
        source_df=source_df,
        end_exclusive=forecast_start,
    )

    if forecast_start is not None:
        forecast_start = pd.Timestamp(forecast_start).to_period('M').to_timestamp()
        df_enhanced = df_enhanced[df_enhanced['date'] < forecast_start].copy()
    if df_enhanced.empty:
        raise ValueError("No historical warranty data is available before the forecast start month")

    # Get top bike models and parts
    top_bike_models = (
        df_enhanced.groupby('BikeModel')['ClaimCount']
        .sum().sort_values(ascending=False)
        .head(top_n_bike_models).index.tolist()
    )

    top_parts = (
        df_enhanced.groupby('ProductName')['ClaimCount']
        .sum().sort_values(ascending=False)
        .head(top_n_parts).index.tolist()
    )

    all_regions = df_enhanced['RegionName'].unique().tolist()

    # Filter data
    df_filtered = df_enhanced[
        (df_enhanced['BikeModel'].isin(top_bike_models)) &
        (df_enhanced['ProductName'].isin(top_parts))
    ].copy()

    # Generate predictions
    predictions_df = batch_recursive_forecast(
        model=model,
        df_historical=df_filtered,
        bike_models=top_bike_models,
        parts=top_parts,
        regions=all_regions,
        n_months=n_months,
        feature_columns=feature_columns,
        cat_features=cat_features,
        forecast_start=forecast_start,
    )

    # Select columns for output
    output_columns = ['date', 'ProductName', 'BikeModel', 'RegionName', 'PredictedClaimCount']
    output_df = predictions_df[output_columns].copy()
    output_df['date'] = output_df['date'].dt.strftime('%Y-%m-%d')
    output_df['PredictedClaimCount'] = output_df['PredictedClaimCount'].round(2)

    return {
        'columns': output_df.columns.tolist(),
        'data': output_df.values.tolist()
    }
