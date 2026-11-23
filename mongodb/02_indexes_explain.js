db = db.getSiblingDB("healthstats");

var query = { iso_code: "PAK", date: { $gte: ISODate("2021-01-01") } };

function summary(label) {
  const e = db.vaccinations.find(query).sort({ date: 1 }).explain("executionStats");
  const plan = e.queryPlanner.winningPlan.queryPlan || e.queryPlanner.winningPlan;
  const s = e.executionStats;
  print("\n=== " + label + " ===");
  printjson({
    winning_stage: plan.stage,
    nReturned: s.nReturned,
    totalKeysExamined: s.totalKeysExamined,
    totalDocsExamined: s.totalDocsExamined,
    executionTimeMillis: s.executionTimeMillis,
  });
}

// Start with no index on iso_code/date
try { db.vaccinations.dropIndex("iso_date_idx"); } catch (err) { /* index did not exist */ }

summary("BEFORE index (expect a collection scan, COLLSCAN)");

db.vaccinations.createIndex({ iso_code: 1, date: 1 }, { name: "iso_date_idx" });

summary("AFTER index (expect an index scan, IXSCAN)");

// ---- The other indexes used by the project ----
db.hospital_stats.createIndex({ iso_code: 1, date: 1 }, { name: "iso_date_idx" });
db.countries.createIndex({ continent: 1 }, { name: "continent_idx" });
db.users_reports.createIndex({ iso_code: 1 }, { name: "report_country_idx" });
db.users_reports.createIndex({ title: "text", body: "text" }, { name: "reports_text_idx" });

print("\nIndexes on vaccinations:");
printjson(db.vaccinations.getIndexes());