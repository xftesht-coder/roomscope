import { test } from "node:test";
import assert from "node:assert/strict";
import {
  validateProfile,
  compareProfiles,
  demoProfile,
} from "../assets/profiles.js";
test("demo pair has a measurable bass change; identical profiles have zero delta", () => {
  const a = demoProfile("A"),
    b = demoProfile("B");
  assert.equal(compareProfiles(a, a).rms, 0);
  const result = compareProfiles(a, b);
  assert.ok(result.rms > 0);
  assert.equal(result.bands.find((p) => p.frequency === 63).delta, -4);
});
test("preserves gain and round-trips profile data", () => {
  const a = demoProfile("A"),
    b = structuredClone(a);
  b.response.smoothed_db = b.response.smoothed_db.map((v) => v - 6);
  assert.equal(compareProfiles(a, b).rms, 6);
  assert.deepEqual(validateProfile(JSON.parse(JSON.stringify(a))), a);
});
test("rejects malformed, non-finite, duplicate and incompatible data", () => {
  const a = demoProfile();
  for (const invalid of [
    null,
    {},
    { ...a, response: { ...a.response, smoothed_db: [NaN] } },
    {
      ...a,
      response: { ...a.response, centers_hz: [20, 20], smoothed_db: [1, 2] },
    },
    { ...a, peq_filters: [{}] },
  ])
    assert.throws(() => validateProfile(invalid));
  const b = structuredClone(a);
  b.response.centers_hz.pop();
  b.response.smoothed_db.pop();
  assert.throws(() => compareProfiles(a, b));
  b.response.reference = "legacy-peak-normalized";
  assert.throws(() => compareProfiles(a, b));
});
test("legacy 0.2 remains importable but never silently mixes with 0.3", () => {
  const old = demoProfile();
  old.roomscope_version = "0.2";
  delete old.response.reference;
  assert.equal(
    validateProfile(old).response.reference,
    "legacy-peak-normalized",
  );
  assert.throws(() => compareProfiles(old, demoProfile()));
});
