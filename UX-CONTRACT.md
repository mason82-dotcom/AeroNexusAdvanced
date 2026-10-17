# Result raster UX contract

Owner: AeroNexusAdvanced result catalog, route `/results`.

Primary workflow: place completed local GeoTIFFs → explicitly scan → search and
select → inspect metadata → view tiles → adjust display without altering sources.
The scan button explains the local folder workflow; refresh reads only the catalog.
Search has a clear action, empty result feedback and 50-item pagination. Every
control has a visible label; repeated filename buttons expose selection state.

No previous layer survives selection changes or failed statistics. Superseded
catalog/statistics/tile callbacks cannot replace the newest selection. A failed
catalog request clears selection. Invalid display bounds leave the current layer
visible and report the validation error. Tile failures offer retry and explain
rescanning changed files. Missing optional dependencies leave the catalog usable.

Scans are explicit, read source files only, replace metadata atomically, report
rejections and preserve the old catalog on directory/limit failure. No upload,
remote URL, source deletion, automatic conversion, mission or drone commands.
No source filesystem paths or credentials appear in the browser.

Verification: actual raster fixtures and API policy tests; Node runtime tests for
response ordering, failed loads, tile settings and text insertion. Actual browser
layout and Pi dataset performance must be checked on the target deployment.
