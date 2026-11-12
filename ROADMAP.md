# Groundwater evidence package and coverage map

Planning baseline: 12 November 2026. Scope: Jharkhand and Odisha, India.

## 1. What the input reports establish

Reviewed:

- [Groundwater Desk Study](input_reports/Groundwater_Desk_Study_Jharkhand_Odisha.docx),
  especially sections 2, 5-6, 9-10 and the reference list.
- [Groundwater Relief Desk Study](input_reports/Groundwater_Relief_Jharkhand_Odisha_Desk_Study.docx),
  especially sections 3, 7, 9, 11-12 and appendices A-C.

Both are dated 11 November 2026 and substantially overlap. Treat them as two
discovery documents, not two independent groundwater datasets. Neither replaces
inspection of the underlying reports, sample tables or portal exports.

Their common priorities are:

1. CGWB station-level chemistry and groundwater levels as the quantitative core.
2. CGWB district brochures and NAQUIM reports for aquifer context and well tables.
3. GSI/BHUKOSH geology, with NGDR mineral-exploration boreholes kept separate from
   groundwater wells.
4. State monitoring and JJM drinking-water surveillance as distinct networks.
5. Targeted field studies to fill geographic, seasonal and parameter gaps.
6. Requests for missing coordinates, lithologs, construction, screened intervals
   and pumping tests.

### Coverage cautions and differences to resolve

- The reports list 24 Jharkhand districts and 30 Odisha districts, but claim only
  27 legacy Odisha brochure links. The all-district matrix is not proof of 30
  acquired brochures. Reconcile each district against actual publications.
- D/R/Q describe routes to reports, subsurface records and quality data; they
  do not establish station density, tested parameters or usable coordinates.
  The second report also uses E for exploration summaries explicitly identified.
  Counts and depth/yield ranges are not individual georeferenced well logs.
- Ranchi's 2022 report names six blocks. Koderma NAQUIM 2.0 concerns selected
  water-stressed areas. Angul-Dhenkanal is an industrial-area study. Do not shade
  whole districts as fully surveyed on that basis.
- Reconcile aliases and historical boundaries, including Balangir/Bolangir,
  Keonjhar/Kendujhar, Subarnapur/Sonepur and Odisha/Orissa. Retain source spellings.
- The second report supplies a Puri DOI missing from the first; Sahibganj still
  lacks a specific paper identifier. Both need bibliographic verification.
- The Sukinda DOI leads to a journal article, not a standalone downloadable
  chemistry CSV. Extractable tables and coordinates still need inspection.
- A recent publication date does not mean recent sampling: store both.

## 2. Desired deliverable

A recipient should be able to open a short guide, explore geographic coverage,
click through to the relevant report or dataset, and download documented tables
without understanding the processing code.

Proposed package layout, to create during implementation:

```text
package/
  START_HERE.html            guide, limitations, map and download links
  catalogue/
    sources.csv             one record per publication/dataset
    files.csv               one record per original or derived file
    coverage.csv            source-to-district/block relationships
    data_dictionary.csv
  raw/<source_id>/           unchanged originals, preserving filenames
  data/
    stations_wells.csv
    samples.csv
    results.csv
    water_levels.csv
    lithology.csv           when available, not fabricated
    hydraulics.csv          when available
  spatial/
    coverage.geojson
    stations.geojson
    evidence.gpkg           optional analyst-friendly GIS package
  reports/
    coverage_summary.pdf
    limitations_and_qa.md
  map/
    index.html
  manifest.csv              file paths, sizes and SHA-256 checksums
```

Keep source storage separate from release eligibility: a lawfully obtained paper
may be usable privately but not redistributable. Public releases include permitted
files and citations/official links for the remainder. Do not include credentials,
personal source-owner details or restricted well locations. Inspect rights and
sensitivity before uploading anything to a hosting or mapping service.

CSV and GeoJSON are the interchange formats; do not build a database service
before the first useful package exists. Generate the map and catalogue from the
same records so their links and coverage cannot drift apart.

## 3. Phased roadmap

The actionable backlog is [tasks.csv](planning/tasks.csv). Owners are proposed
roles, not assigned people. Effort estimates are active work, excluding portal
access and agency response delays.

| Phase | Tasks | Output and completion gate | Approximate effort |
| --- | --- | --- | --- |
| 0: Foundation | T01-T03 | Register/schema, district crosswalk, acquisition and redistribution rules; every listed source has a stable ID and explicit status. | 1-2 days |
| 1: Small acquisition pilot | T04-T06 | One CGWB chemistry export with metadata from each state if accessible; 2-3 contextual PDFs; one literature paper inspected; blocked items documented rather than silently omitted. | 2-4 days |
| 2: First useful data package | T07-T09 | Traceable pilot CSVs, verified coverage geometries and a QA summary; raw values preserved and unresolved locations flagged. | 3-5 days |
| 3: First shareable map | T10-T11 | District/block report coverage, station locations and linked files; one recipient successfully opens a report and downloads its CSV. | 2-4 days |
| 4: Expand and fill gaps | T12-T15 | Broader official archive, additional evidence streams and targeted requests; measurable coverage gaps reduced. | Incremental batches |
| 5: Release and maintenance | T16-T17 | Rights-reviewed package, checksum manifest, tested hosted links and download bundle; versioned updates. | 1-2 days per release |

### First acquisition pilot

Recommended starting contexts, not a commitment to field sites:

- **Koderma/Chandwara:** hard-rock setting, a 2024 NAQUIM 2.0 source and a local
  hydrochemistry paper; verify their actual spatial overlap.
- **Balasore:** coastal setting, a 2017 NAQUIM source and Remuna/Balasore literature;
  useful for testing how depth and season limitations are displayed.
- **Sukinda/Jajpur:** an accessible article to trial literature-table extraction.
  This is supplementary, not a replacement for official monitoring.

Acquire state exports first where practical, but clean/map only the pilot subset.
Keep the first map primarily about evidence availability, not contaminant risk.
If CGWB downloads remain blocked, manually supplied official exports/PDFs can
advance the pipeline; the outstanding access task remains open.

### Ready next session

1. T01-T03: finalize the small catalogue and acquisition rules.
2. T04-T05: try official exports and retrieve the pilot reports, with manual
   handoff for blocked routes.
3. T06: obtain one paper and inspect tables, supplements, coordinates and rights.
4. T07-T11: turn this small batch into a complete package-and-map demonstration
   before attempting all districts.

## 4. Source discovery and manual acquisition

[source_queue.csv](planning/source_queue.csv) seeds the queue with the reports'
18 explicit NAQUIM publication pages, five example legacy brochures, national
and state entry points, and literature candidates. It is not an exhaustive
publication inventory. Row notes distinguish report claims from current checks.

### Limited live checks on 12 November 2026

- CGWB quality page and Koderma publication page: web retrieval failed; bounded
  curl retries timed out after 40 seconds. **Blocked from this environment**, not
  evidence that the sources do not exist.
- [Sukinda v1](https://zenodo.org/records/15747324): reachable; lists a single PDF
  and describes 64 post-monsoon 2023 sampling locations.
- [Latest Sukinda version](https://zenodo.org/records/15771123): reachable, v2
  dated 27 June 2025; also lists a single PDF. Pin v2 when acquiring, retain the
  original cited DOI and inspect reuse terms. No sample tables were extracted.
- Puri and Chandwara DOI routes: redirected to publisher pages but retrieval
  returned HTTP 406. Titles, supplements and extractable data remain unverified.
- No external dataset or PDF has been archived in this planning pass.

### Manual paper handoff

Prioritize Chandwara, Balasore/Remuna and then Palamu; Puri and Sahibganj need
reference verification. Boudh and the regional Odisha study are next-stage
gap fillers.

For each paper the user obtains, provide the PDF plus any supplementary
CSV/XLSX/ZIP, DOI or official URL, acquisition date, and known reuse terms.
During ingestion, preserve the original files under their source ID; record
whether the study collected its own samples or reused CGWB data. Do not assume
that every article includes sample-level tables or coordinates.

Use normal institutional/library access, official open-access copies or author
requests. Do not bypass paywalls or authentication. If sharing rights are unclear,
include a citation and link rather than the PDF in the recipient package.

For agency requests, specify pilot districts/blocks, date range, requested CSV/
GIS format, agency well IDs, coordinates/CRS, construction and screened intervals,
lithology, pumping tests, sample dates, units, qualifiers and redistribution terms.
See section 10 of the first report and section 11 of the second for request wording.

## 5. Coverage model and data quality

Track three independent dimensions:

1. **Acquisition:** identified, access-checked, downloaded, extraction complete,
   QA-reviewed; blocked and unavailable are explicit outcomes.
2. **Geographic evidence:** district context, named blocks, actual study footprint,
   station points or unknown extent. A report's district name is not its footprint.
3. **Usable observations:** stations, samples, parameters, years/seasons,
   coordinate quality, depth/screen availability and evidence stream.

Use source-to-area rows because one report can cover multiple districts/blocks
and one district can have many reports. If only district context is known, show
that limitation; never invent a site point at a district centroid.

Minimum traceability:

- Sources: publisher, title, publication and sampling dates, URL/DOI, access,
  rights, citation and limitations.
- Files: source ID, original name, local path, retrieval date, filters and checksum.
- Observations: stable project IDs plus unmodified agency IDs, source file,
  page/table/row, original value/unit/qualifier and normalized value where valid.
- Locations: coordinates, CRS, precision, admin codes, boundary version and
  location-confidence flag. Unlocated records remain in the catalogue.

QA gates: coordinate order and state/block checks, dates, units, impossible
values, null versus non-detect versus zero, duplicate candidates, cross-source
overlap, and depth/aquifer confidence. Never merge wells solely by place name or
coordinates. Keep CGWB, NAQUIM campaigns, state monitoring, JJM surveillance and
research campaigns distinguishable. Mineral boreholes remain their own layer.

Summaries must separately count sources, distinct wells, samples and results;
multiple parameters on one sample must not inflate station coverage. Coverage
of an analyte means it was tested, not that contamination was absent. Defer
interpolated risk surfaces and aquifer attribution until the data justify them.

## 6. Map recommendation

**Recommended direction:** portable CSV/GeoJSON package plus a lightweight static
Leaflet map. Use QGIS for spatial preparation and optional analyst delivery.
Keep the choice provisional until T10 tests the pilot with a recipient.

| Option | Appropriate use | Main trade-off |
| --- | --- | --- |
| Google My Maps | Quick small overview, familiar link sharing, curated points and district shapes. | Limited imports and filtering; separate file permissions/links; weak fit for detailed multi-year sample exploration. |
| Static Leaflet map | Linked catalogue/files, distinct evidence layers, status/year/parameter filters; deployable on approved static hosting. | Requires a small maintained build; performance must be tested against actual point counts. |
| QGIS project / GeoPackage | Detailed GIS analysis and offline analyst handoff. | Requires GIS software; not the primary nontechnical recipient experience. |

Google **My Maps**, rather than ordinary Google Maps, is the relevant option.
[Google's import guidance](https://support.google.com/mymaps/answer/3024836?hl=en)
supports CSV/KML and CSV WKT geometry but says not to import files with more than
2,000 rows. A small district overview can fit; the complete observation archive
should remain outside the map. Use coordinates/verified geometry rather than
automatic village-name geocoding.

First-map layers:

- District/block boundaries with independently selectable acquisition and
  verified report-extent indicators.
- Verified station/well points, styled by evidence stream; unknown locations
  accessible through the catalogue.
- Counts and date/parameter coverage derived from QA-reviewed observations.
- Report-only evidence and missing/requested subsurface records.

Popups link to the source, permitted local download, derived CSV, citation,
sampling/publication dates and location/depth caveats. Include a searchable
catalogue/table alternative and a legend defining each status.

Sharing choices are still open: approved public hosting versus restricted access,
and browser-online versus offline use. Do not upload until these are resolved.
An online basemap needs network access; an offline bundle must use permitted
bundled assets or a no-basemap boundary view. Test both map and file access as a
recipient, not just as the owner.

## 7. Release definition of done

- Every included file has provenance, a checksum and a redistribution decision.
- Each cleaned observation is traceable to the original and passes or carries
  explicit QA flags; unresolved records are not silently discarded.
- Map coverage agrees with catalogue/CSV counts and does not imply unsampled
  areas are safe or complete.
- Every popup/download link works in the chosen hosted or offline mode.
- A nontechnical recipient can find an area, understand its evidence gaps, open
  one report and download its data without running Python or installing QGIS.
- Include version/date, data dictionary, methods/limitations, rights/attribution
  and an update log. Keep broken-link and manual-request queues for later batches.
