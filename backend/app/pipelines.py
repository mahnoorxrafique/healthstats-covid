"""
The 6 aggregation pipelines used by the dashboard.
Each function returns a pipeline (a list of stages) for db.<collection>.aggregate().
"""

MIN_POPULATION = 1_000_000  # ignore tiny countries so rankings are meaningful


def _join_country():
    """$lookup stage: attach the matching document from `countries`."""
    return [
        {
            "$lookup": {
                "from": "countries",
                "localField": "_id",
                "foreignField": "iso_code",
                "as": "country",
            }
        },
        {"$unwind": "$country"},
    ]


# 1) Top countries by total cases per million people  (run on daily_stats)
#    Stages: $group, $lookup, $unwind, $match, $project, $sort, $limit
def top_countries(limit=10):
    return [
        {
            "$group": {
                "_id": "$iso_code",
                "total_cases": {"$max": "$total_cases"},
                "total_deaths": {"$max": "$total_deaths"},
            }
        },
        *_join_country(),
        {"$match": {"country.demographics.population": {"$gte": MIN_POPULATION}}},
        {
            "$project": {
                "_id": 0,
                "iso_code": "$_id",
                "country": "$country.location",
                "total_cases": 1,
                "total_deaths": 1,
                "cases_per_million": {
                    "$round": [
                        {
                            "$multiply": [
                                {"$divide": ["$total_cases", "$country.demographics.population"]},
                                1_000_000,
                            ]
                        },
                        0,
                    ]
                },
            }
        },
        {"$sort": {"cases_per_million": -1}},
        {"$limit": limit},
    ]


# 2) Monthly cases and deaths for one country  (run on daily_stats)
#    Stages: $match, $group with $dateTrunc, $sort, $project
def monthly_trend(iso_code):
    return [
        {"$match": {"iso_code": iso_code}},
        {
            "$group": {
                "_id": {"$dateTrunc": {"date": "$date", "unit": "month"}},
                "new_cases": {"$sum": "$new_cases"},
                "new_deaths": {"$sum": "$new_deaths"},
            }
        },
        {"$sort": {"_id": 1}},
        {
            "$project": {
                "_id": 0,
                "month": {"$dateToString": {"format": "%Y-%m", "date": "$_id"}},
                "new_cases": {"$round": ["$new_cases", 0]},
                "new_deaths": {"$round": ["$new_deaths", 0]},
            }
        },
    ]


# 3) Case fatality rate per continent  (run on daily_stats)
#    Stages: $group, $lookup, $unwind, $match, $group, $project, $sort
def continent_fatality():
    return [
        {
            "$group": {
                "_id": "$iso_code",
                "total_cases": {"$max": "$total_cases"},
                "total_deaths": {"$max": "$total_deaths"},
            }
        },
        *_join_country(),
        {"$match": {"country.continent": {"$ne": None}}},
        {
            "$group": {
                "_id": "$country.continent",
                "countries": {"$sum": 1},
                "total_cases": {"$sum": "$total_cases"},
                "total_deaths": {"$sum": "$total_deaths"},
            }
        },
        {
            "$project": {
                "_id": 0,
                "continent": "$_id",
                "countries": 1,
                "total_cases": 1,
                "total_deaths": 1,
                "fatality_rate_pct": {
                    "$cond": [
                        {"$gt": ["$total_cases", 0]},
                        {
                            "$round": [
                                {"$multiply": [{"$divide": ["$total_deaths", "$total_cases"]}, 100]},
                                2,
                            ]
                        },
                        None,
                    ]
                },
            }
        },
        {"$sort": {"fatality_rate_pct": -1}},
    ]


# 4) 7-day moving average of new cases for one country  (run on daily_stats)
#    Stages: $match, $sort, $setWindowFields, $project
def moving_average(iso_code):
    return [
        {"$match": {"iso_code": iso_code}},
        {"$sort": {"date": 1}},
        {
            "$setWindowFields": {
                "partitionBy": "$iso_code",
                "sortBy": {"date": 1},
                "output": {
                    "avg_7day": {
                        "$avg": "$new_cases",
                        "window": {"range": [-6, 0], "unit": "day"},
                    }
                },
            }
        },
        {
            "$project": {
                "_id": 0,
                "date": {"$dateToString": {"format": "%Y-%m-%d", "date": "$date"}},
                "new_cases": 1,
                "avg_7day": {"$round": ["$avg_7day", 1]},
            }
        },
    ]


# 5) Vaccination coverage vs deaths per million  (run on daily_stats)
#    Stages: $group, $lookup (with sub-pipeline into vaccinations), $unwind,
#            $lookup, $unwind, $match, $project, $sort
def vaccination_vs_deaths():
    return [
        {"$group": {"_id": "$iso_code", "total_deaths": {"$max": "$total_deaths"}}},
        {
            "$lookup": {
                "from": "vaccinations",
                "let": {"iso": "$_id"},
                "pipeline": [
                    {"$match": {"$expr": {"$eq": ["$iso_code", "$$iso"]}}},
                    {
                        "$group": {
                            "_id": None,
                            "fully_vaccinated": {"$max": "$people_fully_vaccinated"},
                        }
                    },
                ],
                "as": "vax",
            }
        },
        {"$unwind": "$vax"},
        *_join_country(),
        {
            "$match": {
                "country.demographics.population": {"$gte": MIN_POPULATION},
                "vax.fully_vaccinated": {"$ne": None},
            }
        },
        {
            "$project": {
                "_id": 0,
                "iso_code": "$_id",
                "country": "$country.location",
                "continent": "$country.continent",
                "fully_vaccinated_pct": {
                    "$round": [
                        {
                            "$multiply": [
                                {
                                    "$divide": [
                                        "$vax.fully_vaccinated",
                                        "$country.demographics.population",
                                    ]
                                },
                                100,
                            ]
                        },
                        1,
                    ]
                },
                "deaths_per_million": {
                    "$round": [
                        {
                            "$multiply": [
                                {"$divide": ["$total_deaths", "$country.demographics.population"]},
                                1_000_000,
                            ]
                        },
                        0,
                    ]
                },
            }
        },
        {"$sort": {"fully_vaccinated_pct": -1}},
    ]


# 6) Peak wave: the day with the most new cases in each country  (run on daily_stats)
#    Stages: $group with $top, $lookup, $unwind, $match, $project, $sort, $limit
def peak_waves(limit=10):
    return [
        {
            "$group": {
                "_id": "$iso_code",
                "peak": {
                    "$top": {
                        "sortBy": {"new_cases": -1},
                        "output": {"date": "$date", "new_cases": "$new_cases"},
                    }
                },
            }
        },
        *_join_country(),
        {
            "$match": {
                "country.demographics.population": {"$gte": MIN_POPULATION},
                "peak.new_cases": {"$ne": None},
            }
        },
        {
            "$project": {
                "_id": 0,
                "iso_code": "$_id",
                "country": "$country.location",
                "peak_date": {"$dateToString": {"format": "%Y-%m-%d", "date": "$peak.date"}},
                "peak_new_cases": "$peak.new_cases",
                "peak_per_million": {
                    "$round": [
                        {
                            "$multiply": [
                                {"$divide": ["$peak.new_cases", "$country.demographics.population"]},
                                1_000_000,
                            ]
                        },
                        0,
                    ]
                },
            }
        },
        {"$sort": {"peak_per_million": -1}},
        {"$limit": limit},
    ]
