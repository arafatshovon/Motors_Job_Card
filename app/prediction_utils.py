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
from catboost import CatBoostRegressor

# Paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEST_DIR = os.path.join(BASE_DIR, 'test')
CLUSTER_DATA_DIR = os.path.join(BASE_DIR, 'cluster_data')

# Model + metadata are stored in cluster_data inside the container
MODEL_PATH = os.path.join(CLUSTER_DATA_DIR, 'catboost_enhanced_model.cbm')
METADATA_PATH = os.path.join(CLUSTER_DATA_DIR, 'model_metadata.pkl')
WARRANTY_DATA_PATH = os.path.join(CLUSTER_DATA_DIR, 'warranty_data.csv')
ENHANCED_DATA_PATH = os.path.join(CLUSTER_DATA_DIR, 'df_monthly_enhanced_filled.csv')

# Bike model mapping
BIKE_MODEL_MAPPING = {
    "Aerox155": ["Aerox155 Grey Vermillion PGD", "Aerox155 Metallic Black SMX", "Aerox155 Racing Blue DPBMY", "Aerox155 Silver WMC"],
    "Alpha": ["Alpha Marble Black"],
    "FAZER FI V 2.0": ["FAZER FI V 2.0 Marble White 2WS300BWC1", "FAZER FI V 2.0 Ravine Black 2WS200SMX"],
    "FZ V3": ["FZ V3 Metric Black SMX", "FZ V3 Racing Blue DPBMY"],
    "FZ-X": ["FZ-X (BYJ1) Dark Matt Blue MFG", "FZ-X (BYJ1) Matt Black MFG", "FZ-X (BYJ1) Matt Copper MFG", "FZ-X (BYJ1) Matt Titan MFG", "FZ-X (Matt Copper)", "FZ-X (Metallic Blue)", "FZ-X Matt Black MBL2", "FZ-X Matt Copper MDOM3", "FZ-X Metallic Blue BMC"],
    "FZ25": ["FZ25 (250CC)"],
    "FZN 250": ["FZN 250 (DF81) Black", "FZN 250 (DF81) Racing Blue", "FZN 250 (DF81) White"],
    "FZS DD": ["FZS DD Armada Blue CKD", "FZS DD Armada Blue MFG", "FZS DD Black Metallic MFG", "FZS DD Dark knight MFG", "FZS DD Dark Night CKD", "FZS DD Grey Metallic MFG", "FZS DD Matt Green CKD", "FZS DD Matt Grey Metallic MFG"],
    "FZS FI V 2.0": ["FZS FI V 2.0 (SE) Matt Green 2GS300MBL2", "FZS FI V 2.0 (SE) Matt Green 2GS700MBL2", "FZS FI V 2.0 Hurricane Grey 2GS600MNM3", "FZS FI V 2.0 Knight Red 2GS600MDRM4", "FZS FI V 2.0 Lighting Cyan 2GS600CM6", "FZS FI V 2.0 Opal White 2GS600BWC1", "FZS FI V 2.0 Viper Black 2GS400SMX"],
    "FZS V-2.0 DD": ["FZS V-2.0 DD Armada Blue MDPBM1"],
    "FZS V2": ["Fzs DD V2.0 Dark Knight", "Fzs DD V2.0 Matt Green", "FZS v2-Dark Night 2GS900010A MBL2"],
    "FZS V3": ["FZS V3 (BDY5) Dark Matt Blue", "FZS V3 (BDY5) Matt Red", "FZS V3 (BDY6) Majesty Red", "FZS V3 (BDY6) Metallic Black", "FZS V3 (BDY6) Metallic Grey", "FZS V3 Dark Matt Blue MDPBM1", "FZS V3 Gray & Cyan Blue MNM3", "FZS V3 Matt Black MBL2"],
    "FZS V3.0": ["FZS V3.0 Dark Matt Blue CKD", "FZS V3.0 Dark Matt Blue MFG", "FZS V3.0 Dark Matt Blue MFG (MDPBM1)", "FZS V3.0 Grey & Cyan Blue CKD", "FZS V3.0 Matt Black CKD", "FZS V3.0 Matt Black MFG", "FZS V3.0 Matt Black MFG (MBL2)", "FZS V3.0 Matt Red MFG", "FZS V3.0 Metallic Red CKD", "FZS V3.0 Metallic Red MFG", "FZS V3.0 Vintage Green MFG", "FZS V3.0 White CKD"],
    "FZS V4": ["FZS V4 (DE91) Dark Matt Blue", "FZS V4 (DE91) Matt Black", "FZS V4 (DE92) Ice Fluo Vermillion", "FZS V4 (DE92) Majesty Red", "FZS V4 (DE92) Matt Black", "FZS V4 (DE92) Metallic Grey", "FZS V4 (DE92) Racing Blue", "FZS V4 (DE92) Sparkle Green"],
    "Fascino": ["Fascino Unite White"],
    "Fazer": ["Fazer Burning Red VRC1", "Fazer Midnight Black SMX"],
    "Fazer FZH150": ["Fazer FZH150 (DH21) Black", "Fazer FZH150 (DH21) Blue", "Fazer FZH150 (DH21) Red"],
    "MT 15": ["MT 15 ABS India Black SMX", "MT 15 ABS India Blue MDPBM1"],
    "MT15 V2": ["MT15 V2 Cyan Storm PGD", "MT15 V2 Ice Fluo Vermillion MLNM4", "MT15 V2 Metallic Black SMX", "MT15 V2 Racing Blue DPBMY"],
    "N Max": ["N Max Scooter Grey MNM3"],
    "R15 V3": ["R15 V3 Dark Knight MBL2", "R15 V3 MotoGP SMX", "R15 V3 Racing Blue DPBMY", "R15 V3 Thunder Grey MNM3"],
    "R15 V3.0": ["R15 V3.0 Black SMX", "R15 V3.0 Blue DPBMC", "R15 V3.0 Movistar DPBMC", "R15 V3.0 Yellow YM6"],
    "R15 V4": ["R15 V4 (BPDF00) Intensity White", "R15 V4 Dark Knight LGB", "R15 V4 Metallic Red VRC1", "R15 V4 Racing Blue DPBMY"],
    "R15M": ["R15M (BPDD00) Metallic Grey", "R15M (Metallic Grey BPDD00)", "R15M (Metallic Grey)", "R15M Metallic Grey WMC"],
    "Ray ZR": ["Ray ZR SR 125 FI Blue DPBMY", "Ray ZR SR 125 FI Green NHG", "Ray ZR SR Blue DPBMY", "Ray ZR Street Rally (Red) B2V1000-010A M"],
    "RayZR Street Rally": ["RayZR Street Rally-DPBMY(Blue)", "RayZR Street Rally-MNM3(Red/Gray)"],
    "SALUTO Disc": ["SALUTO (Disc) Glory Green 2LP800YB", "SALUTO (Disc) Matt Green 2LPB00MBL2", "SALUTO (Disc) Smoky Black 2LP800MNM3", "SALUTO (Disc) Sparky Cyan 2LP800CM6", "Saluto Disc AB MFG", "Saluto Disc MG CKD", "Saluto Disc MG MFG", "Saluto Disc SC CKD", "Saluto Disc SC MFG"],
    "SALUTO Drum": ["SALUTO (Drum) Victory Red 2LP400DRMK", "SALUTO (Drum) Victory Red 2LP500DRMK"],
    "SZRR": ["SZRR (SE) Matt Green 2PY500MBL2", "SZRR Beast Black 2PY400SMX", "SZRR Predator Cyan 2PY400CM6"],
    "Saluto": ["Saluto UBS Armada Blue MFG", "Saluto UBS Dark Purplish Blue MFG", "Saluto UBS Matt Black MFG", "Saluto UBS Pastel Dark Grey MFG", "Saluto UBS Sparkle Green MFG"],
    "XSR155": ["XSR155 (Matt Black)", "XSR155 (Matt Green Metallic)", "XSR155 (Radical White)", "XSR155 (White Metallic)"]
}

# Create reverse mapping
BIKE_VARIANT_TO_MODEL = {}
for base_model, variants in BIKE_MODEL_MAPPING.items():
    for variant in variants:
        BIKE_VARIANT_TO_MODEL[variant] = base_model


def get_bike_model(bike_name: str) -> str:
    """Map bike variant name to base model."""
    if pd.isna(bike_name):
        return 'Unknown'
    return BIKE_VARIANT_TO_MODEL.get(bike_name, 'Other')


def preprocess_warranty_data(warranty_data_path: str = None, save_path: str = None) -> pd.DataFrame:
    """
    Preprocess warranty_data.csv into df_monthly_enhanced_filled.

    Args:
        warranty_data_path: Path to warranty_data.csv (default: TEST_DIR/warranty_data.csv)
        save_path: Path to save the processed data (default: CLUSTER_DATA_DIR/df_monthly_enhanced_filled.csv)

    Returns:
        DataFrame with monthly enhanced features
    """
    if warranty_data_path is None:
        warranty_data_path = WARRANTY_DATA_PATH
    if save_path is None:
        save_path = ENHANCED_DATA_PATH

    # Load warranty data
    warranty_data_full = pd.read_csv(warranty_data_path)

    # Rename column if needed
    if 'InvoiceDetails' in warranty_data_full.columns:
        warranty_data_full = warranty_data_full.rename(columns={'InvoiceDetails': 'InvoiceDate'})

    # Add bike model
    warranty_data_full['BikeModel'] = warranty_data_full['BikeName'].apply(get_bike_model)

    # Create enhanced dataset
    warranty_enhanced = warranty_data_full.copy()

    # Convert dates
    warranty_enhanced['WCDate'] = pd.to_datetime(warranty_enhanced['WCDate'])
    warranty_enhanced['InvoiceDate'] = pd.to_datetime(warranty_enhanced['InvoiceDate'])

    # Calculate bike age in months
    warranty_enhanced['BikeAgeMonths'] = (
        (warranty_enhanced['WCDate'] - warranty_enhanced['InvoiceDate']).dt.days / 30.44
    ).round(0)

    # Clean Mileage
    warranty_enhanced['Mileage'] = warranty_enhanced['Mileage'].astype(str).str.replace(r'[^\d.]', '', regex=True)
    warranty_enhanced['Mileage'] = pd.to_numeric(warranty_enhanced['Mileage'], errors='coerce').fillna(0)

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

    # Fill missing months
    df_monthly_enhanced_filled = (
        df_monthly_enhanced
        .groupby(["ProductName", "BikeModel", "RegionName"], group_keys=False)
        .apply(_fill_missing_months_enhanced)
    )

    # Add lag and rolling features
    df_monthly_enhanced_filled = _add_lag_and_rolling_features(df_monthly_enhanced_filled)

    # Drop rows with NaN values
    df_model_enhanced = df_monthly_enhanced_filled.dropna().reset_index(drop=True)

    # Save to cluster_data
    os.makedirs(os.path.dirname(save_path), exist_ok=True)
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
    cat_features: list = None
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
    future_dates = pd.date_range(start=latest_date + pd.DateOffset(months=1), periods=n_months, freq='MS')

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

    # Load enhanced data
    if not os.path.exists(ENHANCED_DATA_PATH):
        df_enhanced = preprocess_warranty_data()
    else:
        df_enhanced = pd.read_csv(ENHANCED_DATA_PATH)
        df_enhanced['date'] = pd.to_datetime(df_enhanced['date'])

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


def get_detailed_predictions(n_months: int = 6, top_n_bike_models: int = 20, top_n_parts: int = 20) -> dict:
    """
    Get detailed predictions DataFrame in Gradio-compatible format.

    Returns:
        Dictionary with columns and data lists
    """
    # Load model and metadata
    model, metadata = load_model_and_metadata()
    feature_columns = metadata['feature_columns']
    cat_features = metadata['categorical_features']

    # Load enhanced data
    if not os.path.exists(ENHANCED_DATA_PATH):
        df_enhanced = preprocess_warranty_data()
    else:
        df_enhanced = pd.read_csv(ENHANCED_DATA_PATH)
        df_enhanced['date'] = pd.to_datetime(df_enhanced['date'])

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

    # Select columns for output
    output_columns = ['date', 'ProductName', 'BikeModel', 'RegionName', 'PredictedClaimCount']
    output_df = predictions_df[output_columns].copy()
    output_df['date'] = output_df['date'].dt.strftime('%Y-%m-%d')
    output_df['PredictedClaimCount'] = output_df['PredictedClaimCount'].round(2)

    return {
        'columns': output_df.columns.tolist(),
        'data': output_df.values.tolist()
    }
