db = db.getSiblingDB("healthstats");

// ---- The 5 collections and their sizes ----
print("Collections:", db.getCollectionNames());
["countries", "daily_stats", "vaccinations", "hospital_stats", "users_reports"].forEach((name) => {
  print(name.padEnd(16), db[name].countDocuments());
});

// ---- EMBEDDING: demographics live inside the country document ----
printjson(db.countries.findOne({ iso_code: "PAK" }, { _id: 0 }));

// ---- REFERENCING: daily rows point to the country through iso_code ----
printjson(
  db.daily_stats.find({ iso_code: "PAK" }, { _id: 0 }).sort({ date: 1 }).limit(3).toArray()
);

// ---- Joining the referenced data back together with $lookup ----
printjson(
  db.countries
    .aggregate([
      { $match: { iso_code: "PAK" } },
      { $lookup: { from: "vaccinations", localField: "iso_code", foreignField: "iso_code", as: "vax" } },
      { $project: { _id: 0, location: 1, demographics: 1, vaccination_rows: { $size: "$vax" } } },
    ])
    .toArray()
);

// ================= CRUD on users_reports =================

// ---- CREATE ----
var created = db.users_reports.insertOne({
  iso_code: "PAK",
  author: "class_demo",
  title: "Mongo shell demo report",
  body: "This report was inserted from mongosh.",
  status: "open",
  created_at: new Date(),
});
var id = created.insertedId;
print("Inserted _id:", id);

// ---- READ ----
printjson(db.users_reports.findOne({ _id: id }));
printjson(
  db.users_reports
    .find({ iso_code: "PAK", status: "open" }, { title: 1, author: 1, status: 1 })
    .sort({ _id: -1 })
    .limit(5)
    .toArray()
);

// ---- UPDATE ----
db.users_reports.updateOne({ _id: id }, { $set: { status: "closed", updated_at: new Date() } });
printjson(db.users_reports.findOne({ _id: id }));

// ---- Bulk create / update / delete ----
db.users_reports.insertMany([
  { iso_code: "USA", author: "class_demo", title: "Demo A", body: "Bulk insert A", status: "open" },
  { iso_code: "USA", author: "class_demo", title: "Demo B", body: "Bulk insert B", status: "open" },
]);
print("updateMany modified:", db.users_reports.updateMany({ author: "class_demo" }, { $set: { status: "in_review" } }).modifiedCount);

// ---- DELETE (cleans up everything this script created) ----
print("deleteOne deleted:", db.users_reports.deleteOne({ _id: id }).deletedCount);
print("deleteMany deleted:", db.users_reports.deleteMany({ author: "class_demo" }).deletedCount);