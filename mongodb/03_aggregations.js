db = db.getSiblingDB("healthstats");

var MIN_POP = 1000000; // ignore tiny countries in rankings

var joinCountry = [
  { $lookup: { from: "countries", localField: "_id", foreignField: "iso_code", as: "country" } },
  { $unwind: "$country" },
];

function show(title, cursor, maxRows = 12) {
  const rows = cursor.toArray();
  print("\n--- " + title + " (" + rows.length + " rows, showing " + Math.min(rows.length, maxRows) + ") ---");
  printjson(rows.slice(0, maxRows));
}

// 1) Top 10 countries by cases per million
//    $group -> $lookup -> $unwind -> $match -> $project -> $sort -> $limit
show("1) Top countries by cases per million", db.daily_stats.aggregate([
  { $group: { _id: "$iso_code", total_cases: { $max: "$total_cases" }, total_deaths: { $max: "$total_deaths" } } },
  ...joinCountry,
  { $match: { "country.demographics.population": { $gte: MIN_POP } } },
  { $project: {
      _id: 0, iso_code: "$_id", country: "$country.location", total_cases: 1, total_deaths: 1,
      cases_per_million: { $round: [{ $multiply: [{ $divide: ["$total_cases", "$country.demographics.population"] }, 1000000] }, 0] },
  } },
  { $sort: { cases_per_million: -1 } },
  { $limit: 10 },
]));

// 2) Monthly cases and deaths for one country (change "PAK" to try another)
//    $match -> $group with $dateTrunc -> $sort -> $project
show("2) Monthly trend for PAK", db.daily_stats.aggregate([
  { $match: { iso_code: "PAK" } },
  { $group: {
      _id: { $dateTrunc: { date: "$date", unit: "month" } },
      new_cases: { $sum: "$new_cases" },
      new_deaths: { $sum: "$new_deaths" },
  } },
  { $sort: { _id: 1 } },
  { $project: {
      _id: 0,
      month: { $dateToString: { format: "%Y-%m", date: "$_id" } },
      new_cases: { $round: ["$new_cases", 0] },
      new_deaths: { $round: ["$new_deaths", 0] },
  } },
]), 15);

// 3) Case fatality rate by continent
//    $group -> $lookup -> $unwind -> $match -> $group -> $project -> $sort
show("3) Fatality rate by continent", db.daily_stats.aggregate([
  { $group: { _id: "$iso_code", total_cases: { $max: "$total_cases" }, total_deaths: { $max: "$total_deaths" } } },
  ...joinCountry,
  { $match: { "country.continent": { $ne: null } } },
  { $group: {
      _id: "$country.continent",
      countries: { $sum: 1 },
      total_cases: { $sum: "$total_cases" },
      total_deaths: { $sum: "$total_deaths" },
  } },
  { $project: {
      _id: 0, continent: "$_id", countries: 1, total_cases: 1, total_deaths: 1,
      fatality_rate_pct: { $cond: [
        { $gt: ["$total_cases", 0] },
        { $round: [{ $multiply: [{ $divide: ["$total_deaths", "$total_cases"] }, 100] }, 2] },
        null,
      ] },
  } },
  { $sort: { fatality_rate_pct: -1 } },
]));

// 4) 7-day moving average of new cases (window function)
//    $match -> $sort -> $setWindowFields -> $project
show("4) 7-day moving average for PAK", db.daily_stats.aggregate([
  { $match: { iso_code: "PAK" } },
  { $sort: { date: 1 } },
  { $setWindowFields: {
      partitionBy: "$iso_code",
      sortBy: { date: 1 },
      output: { avg_7day: { $avg: "$new_cases", window: { range: [-6, 0], unit: "day" } } },
  } },
  { $project: {
      _id: 0,
      date: { $dateToString: { format: "%Y-%m-%d", date: "$date" } },
      new_cases: 1,
      avg_7day: { $round: ["$avg_7day", 1] },
  } },
]), 10);

// 5) Vaccination coverage vs deaths per million ($lookup with a sub-pipeline)
//    $group -> $lookup(pipeline) -> $unwind -> $lookup -> $unwind -> $match -> $project -> $sort
show("5) Vaccination vs deaths per million", db.daily_stats.aggregate([
  { $group: { _id: "$iso_code", total_deaths: { $max: "$total_deaths" } } },
  { $lookup: {
      from: "vaccinations",
      let: { iso: "$_id" },
      pipeline: [
        { $match: { $expr: { $eq: ["$iso_code", "$$iso"] } } },
        { $group: { _id: null, fully_vaccinated: { $max: "$people_fully_vaccinated" } } },
      ],
      as: "vax",
  } },
  { $unwind: "$vax" },
  ...joinCountry,
  { $match: { "country.demographics.population": { $gte: MIN_POP }, "vax.fully_vaccinated": { $ne: null } } },
  { $project: {
      _id: 0, iso_code: "$_id", country: "$country.location", continent: "$country.continent",
      fully_vaccinated_pct: { $round: [{ $multiply: [{ $divide: ["$vax.fully_vaccinated", "$country.demographics.population"] }, 100] }, 1] },
      deaths_per_million: { $round: [{ $multiply: [{ $divide: ["$total_deaths", "$country.demographics.population"] }, 1000000] }, 0] },
  } },
  { $sort: { fully_vaccinated_pct: -1 } },
]));

// 6) Worst day (peak new cases) per country
//    $group with $top -> $lookup -> $unwind -> $match -> $project -> $sort -> $limit
show("6) Peak wave per country", db.daily_stats.aggregate([
  { $group: {
      _id: "$iso_code",
      peak: { $top: { sortBy: { new_cases: -1 }, output: { date: "$date", new_cases: "$new_cases" } } },
  } },
  ...joinCountry,
  { $match: { "country.demographics.population": { $gte: MIN_POP }, "peak.new_cases": { $ne: null } } },
  { $project: {
      _id: 0, iso_code: "$_id", country: "$country.location",
      peak_date: { $dateToString: { format: "%Y-%m-%d", date: "$peak.date" } },
      peak_new_cases: "$peak.new_cases",
      peak_per_million: { $round: [{ $multiply: [{ $divide: ["$peak.new_cases", "$country.demographics.population"] }, 1000000] }, 0] },
  } },
  { $sort: { peak_per_million: -1 } },
  { $limit: 10 },
]));