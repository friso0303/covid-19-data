import json
import requests
import pandas as pd


def main():

    DATA_URL = 'https://services3.arcgis.com/MF53hRPmwfLccHCj/ArcGIS/rest/services/COVID_vakcinavimas_chart_name/FeatureServer/0/query'
    PARAMS = {
        'f': 'json',
        'where': "municipality_code='00' AND vaccinated>0",
        'returnGeometry': False,
        'spatialRel': 'esriSpatialRelIntersects',
        'outFields': 'date,vaccine_name,dose_number,vaccinated',
        'resultOffset': 0,
        'resultRecordCount': 32000,
        'resultType': 'standard'
    }
    res = requests.get(DATA_URL, params=PARAMS)
    
    data = [elem["attributes"] for elem in json.loads(res.content)["features"]]

    df = pd.DataFrame.from_records(data)

    df["date"] = pd.to_datetime(df["date"], unit="ms")

    # Correction for vaccinations wrongly attributed to early December 2020
    df.loc[df.date < "2020-12-27", "date"] = pd.to_datetime("2020-12-27")

    # Data by vaccine
    vaccine_mapping = {
        "Pfizer-BioNTech": "Pfizer/BioNTech",
        "Moderna": "Moderna",
        "AstraZeneca": "Oxford/AstraZeneca",
        "Johnson & Johnson": "Johnson&Johnson"
    }
    assert set(df["vaccine_name"].unique()) == set(vaccine_mapping.keys())
    df = df.replace(vaccine_mapping)
    vax = (
        df.groupby(["date", "vaccine_name"], as_index=False)
        ["vaccinated"].sum()
        .sort_values("date")
        .rename(columns={"vaccine_name": "vaccine", "vaccinated": "total_vaccinations"})
    )
    vax["total_vaccinations"] = vax.groupby("vaccine", as_index=False)["total_vaccinations"].cumsum()
    vax["location"] = "Lithuania"
    vax.to_csv("output/by_manufacturer/Lithuania.csv", index=False)

    # Unpivot
    df = (
        df
        .groupby(["date", "dose_number",  "vaccine_name"], as_index=False)
        .sum()
        .pivot(index=["date", "vaccine_name"], columns="dose_number", values="vaccinated")
        .fillna(0)
        .reset_index()
        .rename(columns={
            "Pirma dozė": "people_vaccinated",
            "Antra dozė": "people_fully_vaccinated"
        })
        .sort_values("date")
    )

    # Total vaccinations
    df = df.assign(total_vaccinations=df.people_vaccinated + df.people_fully_vaccinated)

    # Single shot
    msk = df.vaccine_name=="Johnson & Johnson"
    df.loc[msk, "people_fully_vaccinated"] = df.loc[msk, "people_vaccinated"]

    # Group by date
    df = df.groupby("date").agg({
        "people_fully_vaccinated": sum,
        "people_vaccinated": sum,
        "total_vaccinations": sum,
        "vaccine_name": lambda x: ", ".join(sorted(x))
    }).rename(columns={"vaccine_name": "vaccine"}).reset_index()
    df = df.replace(0, pd.NA)

    # Cumsum
    df = df.assign(
        people_fully_vaccinated=df.people_fully_vaccinated.cumsum(),
        people_vaccinated=df.people_vaccinated.cumsum(),
        total_vaccinations=df.total_vaccinations.cumsum()
    )

    df.loc[:, "location"] = "Lithuania"
    df.loc[:, "source_url"] = "https://ls-osp-sdg.maps.arcgis.com/apps/opsdashboard/index.html#/b7063ad3f8c149d394be7f043dfce460"

    # df.loc[:, "vaccine"] = "Pfizer/BioNTech"
    # df.loc[df["date"] >= "2021-01-13", "vaccine"] = "Moderna, Pfizer/BioNTech"
    # df.loc[df["date"] >= "2021-02-07", "vaccine"] = "Moderna, Oxford/AstraZeneca, Pfizer/BioNTech"

    df.to_csv("output/Lithuania.csv", index=False)


if __name__ == "__main__":
    main()
