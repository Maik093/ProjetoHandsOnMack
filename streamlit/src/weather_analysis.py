import pandas as pd

def normalize_rainfall(clima):
    original = clima["rainfall"]
    if pd.api.types.is_bool_dtype(original.dtype):
        rain = original.astype("boolean")
    elif pd.api.types.is_numeric_dtype(original.dtype):
        rain = original.astype("Float64").ne(0).astype("boolean")
        rain = rain.mask(original.isna(), pd.NA)
    else:
        mapping = {
            "true": True, "false": False, "1": True, "0": False,
            "yes": True, "no": False, "sim": True, "não": False, "nao": False,
        }
        norm = original.astype("string").str.strip().str.lower()
        rain = norm.map(mapping).astype("boolean")
    return rain

def seasonal_rain(clima):
    df = clima.copy()
    df["rainfall_bool"] = normalize_rainfall(df)
    out = (
        df.groupby("season")
        .agg(
            registros=("rainfall_bool", "size"),
            registros_validos=("rainfall_bool", "count"),
            registros_com_chuva=("rainfall_bool", "sum"),
        ).reset_index()
    )
    out["percentual_com_chuva"] = (
        out["registros_com_chuva"] / out["registros_validos"] * 100
    )
    return out

def descriptive(clima):
    cols = ["air_temp", "humidity", "pressure", "track_temp", "wind_direction", "wind_speed"]
    return clima[cols].describe(percentiles=[.05, .25, .50, .75, .95]).T.round(2)

def seasonal_weather(clima):
    return (
        clima.groupby("season")
        .agg(
            temperatura_ar_media=("air_temp", "mean"),
            temperatura_ar_min=("air_temp", "min"),
            temperatura_ar_max=("air_temp", "max"),
            temperatura_pista_media=("track_temp", "mean"),
            temperatura_pista_min=("track_temp", "min"),
            temperatura_pista_max=("track_temp", "max"),
            umidade_media=("humidity", "mean"),
            umidade_min=("humidity", "min"),
            umidade_max=("humidity", "max"),
            pressao_media=("pressure", "mean"),
            vento_medio=("wind_speed", "mean"),
            vento_max=("wind_speed", "max"),
        ).round(2).reset_index()
    )

def temperature_correlation(clima):
    df = clima[["air_temp", "track_temp"]].dropna()
    return {
        "pearson": df["air_temp"].corr(df["track_temp"], method="pearson"),
        "spearman": df["air_temp"].corr(df["track_temp"], method="spearman"),
        "n": len(df),
    }

def tyre_weather_context(clima, pneus_canonicos):
    rain = seasonal_rain(clima)
    wet = (
        pneus_canonicos.assign(
            composto_molhado=pneus_canonicos["compound"].isin(["INTERMEDIATE", "WET"])
        )
        .groupby("season")
        .agg(
            registros_pneu=("lap_number", "size"),
            registros_composto_molhado=("composto_molhado", "sum"),
        ).reset_index()
    )
    wet["pct_composto_molhado"] = wet["registros_composto_molhado"] / wet["registros_pneu"] * 100
    return rain.merge(
        wet, on="season", how="outer", validate="one_to_one"
    ).sort_values("season")
