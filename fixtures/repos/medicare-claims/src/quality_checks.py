from pathlib import Path

import pandera as pa
import pandas as pd

from parquet_io import read_parquet_df


def run_quality_checks(silver_path: Path) -> None:
    df = read_parquet_df(silver_path)

    schema = pa.DataFrameSchema(
        {
            "npi": pa.Column(str, nullable=False, checks=pa.Check.str_length(10, 10)),
            "provider_type": pa.Column(str, nullable=False),
            "provider_state": pa.Column(str, nullable=False, checks=pa.Check.str_length(2, 2)),
            "tot_mdcr_pymt_amt": pa.Column(float, nullable=True, checks=pa.Check.ge(0)),
            "tot_benes": pa.Column(float, nullable=True, checks=pa.Check.ge(0)),
            "tot_srvcs": pa.Column(float, nullable=True, checks=pa.Check.ge(0)),
            "data_year": pa.Column(int, nullable=False),
        },
        coerce=True,
        strict=False,
    )

    schema.validate(df, lazy=True)


if __name__ == "__main__":
    run_quality_checks(Path("data/silver/claims_enriched.parquet"))
