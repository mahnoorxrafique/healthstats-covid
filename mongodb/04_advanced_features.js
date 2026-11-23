db = db.getSiblingDB("healthstats");

// ---- Time-series collection ----
// daily_stats was created like this (backend/scripts/load_data.py does it):
//
// db.createCollection("daily_stats", {
//   timeseries: { timeField: "date", metaField: "iso_code", granularity: "hours" }
// });
//
// Proof that it is a time-series collection (look for type: "timeseries"):
printjson(db.getCollectionInfos({ name: "daily_stats" }));

// Time-range query: one week of data for one country
printjson(
  db.daily_stats
    .find(
      { iso_code: "PAK", date: { $gte: ISODate("2021-03-01"), $lt: ISODate("2021-03-08") } },
      { _id: 0, iso_code: 1, date: 1, new_cases: 1, new_deaths: 1 }
    )
    .sort({ date: 1 })
    .toArray()
);

// Monthly rollup using the time-series friendly $dateTrunc
printjson(
  db.daily_stats
    .aggregate([
      { $match: { iso_code: "PAK", date: { $gte: ISODate("2021-01-01"), $lt: ISODate("2021-07-01") } } },
      { $group: { _id: { $dateTrunc: { date: "$date", unit: "month" } }, new_cases: { $sum: "$new_cases" } } },
      { $sort: { _id: 1 } },
    ])
    .toArray()
);

// ---- Text search ----
// Needs a text index on title + body (created here if it is missing)
db.users_reports.createIndex({ title: "text", body: "text" }, { name: "reports_text_idx" });

// Add a couple of searchable reports
db.users_reports.insertMany([
  { iso_code: "PAK", author: "class_demo", title: "Vaccination drive", body: "Free vaccination camp opened this week.", status: "open" },
  { iso_code: "IND", author: "class_demo", title: "Hospital capacity", body: "ICU beds are filling up in the city.", status: "open" },
]);

// Search and rank by relevance
printjson(
  db.users_reports
    .find({ $text: { $search: "vaccination" } }, { title: 1, iso_code: 1, score: { $meta: "textScore" } })
    .sort({ score: { $meta: "textScore" } })
    .toArray()
);

// Clean up the demo reports
print("Cleaned up:", db.users_reports.deleteMany({ author: "class_demo" }).deletedCount);