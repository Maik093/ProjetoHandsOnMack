import pandas as pd

def canonical_tyres(pneus, driver_mapping):
    mapping = driver_mapping.loc[
        driver_mapping["match_status"].eq("MATCH_OK"),
        ["season", "fastf1_driver_id", "jolpica_driver_id", "match_status"]
    ].drop_duplicates(["season", "fastf1_driver_id"])
    df = pneus.merge(
        mapping,
        left_on=["season", "driver_id"],
        right_on=["season", "fastf1_driver_id"],
        how="left",
        validate="many_to_one",
    )
    return df

def stint_validation(pneus_canonicos):
    comp = (
        pneus_canonicos.groupby(
            ["season", "session", "jolpica_driver_id", "stint"],
            dropna=False
        )
        .agg(
            quantidade_compostos=("compound", "nunique"),
            primeira_volta=("lap_number", "min"),
            ultima_volta=("lap_number", "max"),
            registros=("lap_number", "size"),
        ).reset_index()
    )
    continuity = (
        pneus_canonicos.groupby(
            ["season", "session", "jolpica_driver_id", "stint", "compound"],
            dropna=False
        )
        .agg(
            primeira_volta=("lap_number", "min"),
            ultima_volta=("lap_number", "max"),
            voltas_observadas=("lap_number", "nunique"),
        ).reset_index()
    )
    continuity["voltas_esperadas"] = continuity["ultima_volta"] - continuity["primeira_volta"] + 1
    continuity["voltas_ausentes"] = continuity["voltas_esperadas"] - continuity["voltas_observadas"]

    tyre_life = (
        pneus_canonicos.groupby(
            ["season", "session", "jolpica_driver_id", "stint", "compound"],
            dropna=False
        )
        .agg(
            primeira_volta=("lap_number", "min"),
            ultima_volta=("lap_number", "max"),
            voltas_observadas=("lap_number", "nunique"),
            tyre_life_inicial=("tyre_life", "min"),
            tyre_life_final=("tyre_life", "max"),
            registros_tyre_life=("tyre_life", "count"),
        ).reset_index()
    )
    return comp, continuity, tyre_life

def compound_distribution(pneus_canonicos):
    out = (
        pneus_canonicos.groupby("compound")
        .agg(registros_volta=("lap_number", "size"), temporadas=("season", "nunique"))
        .reset_index()
    )
    out["percentual"] = out["registros_volta"] / out["registros_volta"].sum() * 100
    return out.sort_values("registros_volta", ascending=False)

def compound_by_season(pneus_canonicos):
    out = (
        pneus_canonicos.groupby(["season", "compound"])
        .agg(registros_volta=("lap_number", "size")).reset_index()
    )
    out["percentual_temporada"] = (
        out["registros_volta"]
        / out.groupby("season")["registros_volta"].transform("sum") * 100
    )
    return out

def stint_summary(tyre_life):
    return (
        tyre_life.groupby("compound")
        .agg(
            quantidade_stints=("stint", "size"),
            voltas_media=("voltas_observadas", "mean"),
            voltas_mediana=("voltas_observadas", "median"),
            voltas_p25=("voltas_observadas", lambda x: x.quantile(.25)),
            voltas_p75=("voltas_observadas", lambda x: x.quantile(.75)),
            maior_stint=("voltas_observadas", "max"),
            tyre_life_final_mediano=("tyre_life_final", "median"),
        ).round(2).reset_index().sort_values("quantidade_stints", ascending=False)
    )

def strategies(tyre_life):
    ordered = tyre_life.sort_values(
        ["season", "session", "jolpica_driver_id", "stint"]
    )
    by_driver = (
        ordered.groupby(["season", "session", "jolpica_driver_id"])
        .agg(
            quantidade_stints=("stint", "nunique"),
            sequencia_compostos=("compound", lambda x: " → ".join(x.astype(str))),
            compostos_distintos=("compound", "nunique"),
            voltas_observadas=("voltas_observadas", "sum"),
        ).reset_index()
    )
    freq = (
        by_driver.groupby(["season", "sequencia_compostos"])
        .agg(pilotos=("jolpica_driver_id", "nunique")).reset_index()
        .sort_values(["season", "pilotos"], ascending=[True, False])
    )
    return by_driver, freq

def tyre_rhythm(pneus_canonicos, voltas_contexto):
    df = pneus_canonicos.merge(
        voltas_contexto[
            [
                "season", "round", "driver_id", "lap", "lap_time_seconds",
                "pit_stop", "evento_coletivo_extremo", "volta_comparavel",
                "delta_contexto_volta_pct"
            ]
        ],
        left_on=["season", "jolpica_driver_id", "lap_number"],
        right_on=["season", "driver_id", "lap"],
        how="left",
    )
    comparable = df[
        df["volta_comparavel"].astype("boolean").fillna(False)
        & df["delta_contexto_volta_pct"].notna()
    ].copy()
    return df, comparable

def rhythm_by_compound(comparable):
    return (
        comparable.groupby("compound")
        .agg(
            voltas=("lap_number", "size"),
            pilotos=("jolpica_driver_id", "nunique"),
            temporadas=("season", "nunique"),
            delta_medio_pct=("delta_contexto_volta_pct", "mean"),
            delta_mediano_pct=("delta_contexto_volta_pct", "median"),
            p25=("delta_contexto_volta_pct", lambda x: x.quantile(.25)),
            p75=("delta_contexto_volta_pct", lambda x: x.quantile(.75)),
        ).round(3).reset_index().sort_values("delta_mediano_pct")
    )

def tyre_life_rhythm(comparable):
    df = comparable.copy()
    df["faixa_tyre_life"] = pd.cut(
        df["tyre_life"],
        bins=[0, 5, 10, 15, 20, 30, 40, float("inf")],
        labels=["1-5", "6-10", "11-15", "16-20", "21-30", "31-40", "41+"]
    )
    return (
        df.groupby(["compound", "faixa_tyre_life"], observed=True)
        .agg(
            voltas=("lap_number", "size"),
            pilotos=("jolpica_driver_id", "nunique"),
            temporadas=("season", "nunique"),
            delta_mediano_pct=("delta_contexto_volta_pct", "median"),
            delta_medio_pct=("delta_contexto_volta_pct", "mean"),
        ).round(3).reset_index()
    )

def within_stint(comparable, tyre_life):
    starts = tyre_life[
        ["season", "session", "jolpica_driver_id", "stint", "compound", "primeira_volta"]
    ].drop_duplicates()
    df = comparable.merge(
        starts,
        on=["season", "session", "jolpica_driver_id", "stint", "compound"],
        how="left", validate="many_to_one"
    )
    df["volta_no_stint"] = df["lap_number"] - df["primeira_volta"] + 1
    return df
