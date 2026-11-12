"""Link manually downloaded CGWB repository PDFs to their catalogue rows.

CGWB serves every publication as ``<unix-timestamp><random>file.pdf``, so the
download id is lost once the file is on disk. The mapping below was built by
hand on 2026-11-12 from (a) the upload timestamp embedded in the filename, which
matches the repository ``posted_on`` date, and (b) the cover-page text of each
PDF, matched against the repository title/abstract in
``planning/cgwb_search_results.csv``. The four PDFs with no extractable text
(620, 188, 189, 724) were opened and confirmed by the user on 2026-11-12. Any
future entry whose basis starts with ``inferred`` is flagged in the catalogue
until eyeballed.

Running the script writes ``planning/cgwb_file_mapping.csv``, fills
``local_globs``/``access_status``/``retrieved_on`` in ``catalogue/sources.csv``
and the ``filename``/``size_bytes``/``sha256``/``status``/``fetched_on`` columns
of the search manifest. It is idempotent.
"""

import csv
import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SOURCES = ROOT / "catalogue" / "sources.csv"
MANIFEST = ROOT / "planning" / "cgwb_search_results.csv"
MAPPING = ROOT / "planning" / "cgwb_file_mapping.csv"
RETRIEVED_ON = "2026-11-12"

# download_id -> (state folder, filename, match basis)
MAPPING_TABLE = {
    # Jharkhand (state_id=20)
    "620": ("jharkhand", "17426441461176943713file.pdf", "user opened PDF 2026-11-12: fluoride assessment MoU document (8 p, scanned); upload 2025-03-22 vs listing 2023-06-21"),
    "795": ("jharkhand", "16881183111215462003file.pdf", "cover text 'GROUND WATER YEAR BOOK, JHARKHAND (2013 - 2014)'"),
    "798": ("jharkhand", "16881193291825295275file.pdf", "cover text '(2014 - 2015)'"),
    "799": ("jharkhand", "16881195631547889010file.pdf", "cover text '(2015 - 2016)'"),
    "800": ("jharkhand", "1688119787790349540file.pdf", "cover text '(2016 - 2017)'"),
    "801": ("jharkhand", "1688120050219830895file.pdf", "cover text '(2017 - 2018)'"),
    "803": ("jharkhand", "1688120491583827956file.pdf", "cover text '(2018 - 2019)'"),
    "807": ("jharkhand", "16883635771293620594file.pdf", "cover text '(2019 - 2020)'"),
    "808": ("jharkhand", "16883640181392337147file.pdf", "cover text '(2020 - 2021)'"),
    "809": ("jharkhand", "16883646811420506028file.pdf", "cover text '(2021 - 2022)'"),
    "1187": ("jharkhand", "17032368101008159940file.pdf", "only file uploaded 2023-12-22; user opened PDF 2026-11-12: cover shows 2022-2023"),
    "1224": ("jharkhand", "1705645164800451300file.pdf", "cover text 'Dynamic Ground Water Resources, 2023 Jharkhand'"),
    "1269": ("jharkhand", "17080019611535236779file.pdf", "already registered"),
    "1427": ("jharkhand", "17422958481075728240file.pdf", "cover text 'Dynamic Ground Water Resources & Ground Water Quality of Jharkhand, 2024'"),
    "1450": ("jharkhand", "174289713485198787file.pdf", "cover text 'Chatra District'"),
    "1451": ("jharkhand", "1742896617131797286file.pdf", "cover text 'Parts of Ranchi, Khunti and Lohardagga'; 3 byte-identical files assigned to 1451/1452/1453 in upload order"),
    "1452": ("jharkhand", "1742896698840549400file.pdf", "cover text 'Parts of Ranchi, Khunti and Lohardagga'; byte-identical to 1451"),
    "1453": ("jharkhand", "1742896774438615621file.pdf", "cover text 'Parts of Ranchi, Khunti and Lohardagga'; byte-identical to 1451"),
    "1454": ("jharkhand", "17428970048797555file.pdf", "cover text 'GODDA DISTRICT'"),
    "1455": ("jharkhand", "17428970982011537063file.pdf", "cover text 'DUMKA DISTRICT'"),
    "1456": ("jharkhand", "17428972291140179875file.pdf", "cover text 'JAMTARA DISTRICT'"),
    "1457": ("jharkhand", "17428973141828476552file.pdf", "cover text 'Latehar District'"),
    "1458": ("jharkhand", "17428974641475200877file.pdf", "cover text 'Lohardaga District'"),
    "1459": ("jharkhand", "1742897675857410277file.pdf", "cover text 'SAHEBGANJ DISTRICTS'"),
    "1460": ("jharkhand", "17428979271611617479file.pdf", "cover text 'Parts of Bokaro, Ramgarh and Dhanbad'"),
    "1461": ("jharkhand", "1742898071122257815file.pdf", "cover text 'PAKUR DISTRICT'"),
    "1462": ("jharkhand", "17428981951316805745file.pdf", "cover text 'Dhanbad District'"),
    "1463": ("jharkhand", "1742898326822481999file.pdf", "cover text 'Deoghar District'"),
    "1464": ("jharkhand", "1742903721155216150file.pdf", "cover text 'Simdega District'"),
    "1465": ("jharkhand", "1742904204377087425file.pdf", "cover text 'Giridih District'"),
    "1466": ("jharkhand", "17429061551754801177file.pdf", "cover text 'Rania and Arki Blocks of Khunti District'"),
    "1467": ("jharkhand", "17429062961833952866file.pdf", "cover text 'West Singhbhum District'"),
    "1468": ("jharkhand", "17429063872050802488file.pdf", "cover text 'Chandrapura and Nawadih Blocks of Bokaro District'"),
    "1469": ("jharkhand", "1742906473133768011file.pdf", "cover text 'GARHWA DISTRICT'"),
    "1470": ("jharkhand", "17429065431096659301file.pdf", "cover text 'GUMLA DISTRICT'"),
    "1471": ("jharkhand", "1742906715357970024file.pdf", "cover text 'Khelri, Lapung, Silli, Rahe, Tamar and Sonahatu Blocks of Ranchi District'"),
    "1472": ("jharkhand", "17429067931057333748file.pdf", "cover text 'KODERMA DISTRICT'"),
    "1530": ("jharkhand", "17435853171791994209file.pdf", "cover text 'DYNAMIC GROUND WATER RESOURCE OF JHARKHAND, 2024'"),
    "1637": ("jharkhand", "17503321441975958541file.pdf", "cover text 'Koderma, Jainagar and Domchanch Blocks'"),
    "1706": ("jharkhand", "17545522261025354986file.pdf", "already registered"),
    "1725": ("jharkhand", "1754566965122933083file.pdf", "cover text 'Ground Water Year Book (2023 - 2024)'"),
    "1769": ("jharkhand", "1764586210492251315file.pdf", "cover text 'District Recharge Plan, Bokaro District, Jharkhand'"),
    "1834": ("jharkhand", "1766744919555415344file.pdf", "cover text 'Dynamic Ground Water Resources, Ground Water Level & Ground Water Quality of Jharkhand, 2025'"),
    "1874": ("jharkhand", "17670935511780785901file.pdf", "already registered"),
    "1910": ("jharkhand", "1767181607477914259file.pdf", "already registered"),
    "1965": ("jharkhand", "17721776681497997423file.pdf", "cover text 'Aquifer Management Plan Lesliganj, Medininagar, Satbarwa, Pandwa'"),
    "2013": ("jharkhand", "177426555049545610file.pdf", "cover text 'Ground Water Yearbook (2024-2025)'"),
    "2108": ("jharkhand", "17781481351671file.pdf", "cover text 'DYNAMIC GROUND WATER RESOURCES OF JHARKHAND, 2025'"),
    # Odisha (state_id=21)
    "95": ("odisha", "16841298301259145660file.pdf", "cover text 'DEOGARH DISTRICT'; upload 2023-05-15 vs listing 2023-05-12"),
    "96": ("odisha", "168412980446032596file.pdf", "cover text 'KORAPUT DISTRICT'"),
    "97": ("odisha", "1684129772499408807file.pdf", "cover text 'MAYURBHANJ DISTRICT'; listing abstract 'multidisciplinary study wherein...' found on p.2 of PDF"),
    "101": ("odisha", "16841297431877544328file.pdf", "cover text 'SAMBALPUR DISTRICT'; listing abstract 'disposition of aquifers up to 200-meter depth' found in PDF objectives"),
    "105": ("odisha", "16841298801410823551file.pdf", "cover text 'SUNDARGARH DISTRICT'"),
    "184": ("odisha", "1684752856556026480file.pdf", "cover text 'JAJPUR DISTRICT'; only file uploaded 2023-05-22"),
    "188": ("odisha", "1684822444742784076file.pdf", "user opened PDF 2026-11-12: 36 p of annexure tables (scanned, landscape); the shorter of two files uploaded 2023-05-23"),
    "189": ("odisha", "1684823667368996251file.pdf", "user opened PDF 2026-11-12: Kandhamal district aquifer mapping main report (118 p, scanned); the longer of two files uploaded 2023-05-23"),
    "202": ("odisha", "16996077851936652351file.pdf", "cover text 'CUTTACK DISTRICT'; upload 2023-11-10 vs listing 2023-05-24"),
    "724": ("odisha", "1687924620841769750file.pdf", "user opened PDF 2026-11-12: cover shows 'GROUND WATER YEAR BOOK 2013-2014' (scanned, no text); only yearbook uploaded 2023-06-28 left after 2016-17..2021-22 matched"),
    "725": ("odisha", "1687925280410439253file.pdf", "cover text 'GROUND WATER YEAR BOOK 2017-2018'"),
    "727": ("odisha", "16879271941631230004file.pdf", "cover text 'GROUND WATER YEAR BOOK 2016-2017'"),
    "733": ("odisha", "16879324231614740340file.pdf", "cover text 'GROUND WATER YEAR BOOK 2020-2021'"),
    "735": ("odisha", "16879328491125982303file.pdf", "'2021-2022' on p.2 (cover text garbled)"),
    "736": ("odisha", "16879330951765419040file.pdf", "cover text 'GROUND WATER YEAR BOOK 2019-2020'"),
    "738": ("odisha", "16879333401775971667file.pdf", "cover text 'GROUND WATER YEAR BOOK 2018-2019'"),
    "1008": ("odisha", "1699530368692993571file.pdf", "cover text 'Bargarh District'"),
    "1010": ("odisha", "16995310131009178312file.pdf", "cover text 'BALASORE DISTRICT'"),
    "1034": ("odisha", "1699595413716596133file.pdf", "cover text 'Rayagada District'"),
    "1040": ("odisha", "16995968961433467042file.pdf", "cover text 'Nuapada District'"),
    "1045": ("odisha", "1699598003629634222file.pdf", "cover text 'NABARANGPUR DISTRICT'"),
    "1047": ("odisha", "1699598494700618043file.pdf", "cover text 'Malkangiri District'"),
    "1049": ("odisha", "1699599717468052275file.pdf", "cover text 'KHURDA DISTRICT'"),
    "1053": ("odisha", "1699601046511342431file.pdf", "cover text 'Kendrapara District'"),
    "1058": ("odisha", "1699602417333026401file.pdf", "cover text 'Balangir District'"),
    "1059": ("odisha", "169960662666082483file.pdf", "cover text 'Kalahandi District'"),
    "1061": ("odisha", "1699607312257306978file.pdf", "cover text 'BOUDH DISTRICT'"),
    "1063": ("odisha", "16996079341503516201file.pdf", "cover text 'BHADRAK DISTRICT'"),
    "1065": ("odisha", "16996088351110878713file.pdf", "cover text 'DHENKANAL DISTRICT'"),
    "1068": ("odisha", "1699611700661942919file.pdf", "cover text 'Gajapati District'"),
    "1070": ("odisha", "1699857196382865695file.pdf", "cover text 'JAGATSINGHPUR DISTRICT'"),
    "1071": ("odisha", "16998580901773663071file.pdf", "cover text 'JHARSUGUDA DISTRICT'"),
    "1072": ("odisha", "1699860887552249206file.pdf", "cover text 'NAYAGARH DISTRICT'"),
    "1073": ("odisha", "16998614591076746895file.pdf", "cover text 'PURI DISTRICT'"),
    "1076": ("odisha", "16999374611067196500file.pdf", "cover text 'KEONJHAR DISTRICT'"),
    "1083": ("odisha", "16999403721574527770file.pdf", "cover text 'SUVARNAPUR DISTRICT'"),
    "1086": ("odisha", "1699943716888112989file.pdf", "cover text 'Ganjam District'"),
    "1194": ("odisha", "17032377922110720458file.pdf", "cover text 'GROUND WATER YEAR BOOK 2022-23'"),
    "1235": ("odisha", "17056472262075998320file.pdf", "cover text 'Dynamic Ground Water Resources, 2023 Odisha'"),
    "1272": ("odisha", "1708002328801055551file.pdf", "cover text 'Groundwater Quality Year Book of the Odisha State 2022-2023'"),
    "1289": ("odisha", "1708416817399257460file.pdf", "cover text 'DYNAMIC GROUND WATER RESOURCES OF ODISHA, 2023'"),
    "1383": ("odisha", "17412385051448745588file.pdf", "cover text 'AQUIFER MAPPING REPORT ANGUL DISTRICT'"),
    "1430": ("odisha", "17422959471471187603file.pdf", "cover text 'Dynamic Ground Water Resources & Ground Water Quality of Odisha, 2024'"),
    "1540": ("odisha", "17435864691666329414file.pdf", "cover text 'DYNAMIC GROUND WATER RESOURCES OF ODISHA, 2024'"),
    "1575": ("odisha", "17450225221876453832file.pdf", "cover text 'Bologarh Block (Khordha District) and Nayagarh Block'"),
    "1580": ("odisha", "17450235572049643371file.pdf", "cover text 'Parts of Jharsuguda and Sambalpur Districts'"),
    "1581": ("odisha", "1745023689734460327file.pdf", "cover text 'Sambalpur Urban Agglomerate'"),
    "1582": ("odisha", "17450238421920854510file.pdf", "cover text 'Balasore Sadar and Remuna Blocks'"),
    "1689": ("odisha", "17544663891445002841file.pdf", "cover text 'GROUND WATER YEAR BOOK 2023-2024'"),
    "1713": ("odisha", "1754556047435701823file.pdf", "cover text 'Groundwater Quality Year Book of Odisha State 2023-2024'"),
    "1766": ("odisha", "1764585701644043650file.pdf", "cover text 'Recommended Artificial Recharge Structures, Odisha'"),
    "1841": ("odisha", "1766746072441391182file.pdf", "cover text 'Dynamic Ground Water Resources, Ground Water Level & Ground Water Quality of Odisha, 2025'"),
    "1862": ("odisha", "17670924571291795295file.pdf", "cover text 'Groundwater Quality Year Book of Odisha State AAP 2024-25'"),
    "1898": ("odisha", "1767178819230598877file.pdf", "content: Odisha station table with Arsenic ppb; only file uploaded 2025-12-31"),
    "1951": ("odisha", "17721701312038819526file.pdf", "cover text 'Industrial area of Angul Dhenkanal District'"),
    "1990": ("odisha", "17724444981562079717file.pdf", "cover text 'Sukinda Mining Area, Jajpur District'"),
    "2021": ("odisha", "1774431893399826946file.pdf", "only file uploaded 2026-03-25; user opened PDF 2026-11-12: cover shows 2024-2025"),
    "2129": ("odisha", "17781486374796file.pdf", "cover text 'DYNAMIC GROUND WATER RESOURCES OF ODISHA, 2025'"),
}

# Facts learned from the PDF covers that fix generic repository listings.
TITLE_FIXES = {
    "97": {
        "title": "AQUIFER MAPPING AND MANAGEMENT OF GROUND WATER RESOURCES MAYURBHANJ DISTRICT, ODISHA",
        "area": "Odisha:Mayurbhanj",
        "priority": "P0",
        "description": "NAQUIM aquifer mapping and management plan report for Mayurbhanj district (Subarnarekha basin focus district), CGWB South Eastern Region, 156 pages. Repository listing title was generic; district resolved from the PDF cover.",
    },
    "101": {
        "title": "AQUIFER MAPPING AND MANAGEMENT OF GROUND WATER RESOURCES SAMBALPUR DISTRICT, ODISHA",
        "area": "Odisha:Sambalpur",
        "description": "NAQUIM aquifer mapping and management plan report for Sambalpur district, CGWB South Eastern Region, 114 pages. Repository listing title was generic; district resolved from the PDF cover.",
    },
    "189": {
        "title": "AQUIFER MAPPING AND MANAGEMENT OF GROUND WATER RESOURCES, KANDHAMAL DISTRICT, ODISHA",
    },
}

OLD_LIMIT = "Not yet downloaded; content, year and footprint to be verified against the PDF"
NEW_LIMIT = "Content, year and footprint not yet verified against the PDF"
INFERRED_LIMIT = "File-to-listing match inferred (no extractable text)"
TAG_MARKER = "Portal filename "


def strip_limit(limitations: str, item: str) -> str:
    return "; ".join(p for p in limitations.split("; ") if p and p != item)


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_csv(path: Path, rows: list[dict[str, str]], columns: list[str]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    with SOURCES.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        src_cols = list(reader.fieldnames)
        sources = list(reader)
    with MANIFEST.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        man_cols = list(reader.fieldnames)
        manifest = list(reader)

    by_id = {}
    for row in sources:
        url = row["url"]
        if "cgwbpnm/" in url and url.rsplit("/", 1)[1].isdigit():
            by_id[url.rsplit("/", 1)[1]] = row

    mapping_rows = []
    for did, (state, filename, basis) in MAPPING_TABLE.items():
        rel = f"downloaded_data/cgwb/{state}/{filename}"
        path = ROOT / rel
        if not path.is_file():
            raise SystemExit(f"missing file for download id {did}: {rel}")
        row = by_id[did]
        digest = sha256_of(path)
        size = path.stat().st_size

        row["local_globs"] = rel
        if row["access_status"] != "downloaded":
            row["access_status"] = "downloaded"
            row["retrieved_on"] = RETRIEVED_ON
            row["access_detail"] = (
                f"manual curl download by user {RETRIEVED_ON} from https://cgwb.gov.in/cgwbpnm/download/{did}; "
                f"detail page https://cgwb.gov.in/cgwbpnm/publication-detail/{did}; "
                "cgwb.gov.in times out from development environment"
            )
            row["limitations"] = row["limitations"].replace(OLD_LIMIT, NEW_LIMIT)
        # Match-basis note and inferred flag are regenerated every run so that
        # confirming a match in MAPPING_TABLE propagates to the catalogue.
        # Rows registered by hand before this script keep their curated notes.
        if basis != "already registered":
            notes = row["notes"]
            marker = f"{TAG_MARKER}{filename} retained; matched to download id {did} by "
            if marker in notes:
                notes = notes[: notes.index(marker)].rstrip()
            tag = f"{marker}{basis}."
            row["limitations"] = strip_limit(row["limitations"], INFERRED_LIMIT)
            if "inferred" in basis:
                tag += " Mapping inferred, verify by opening the PDF."
                row["limitations"] = (row["limitations"] + "; " if row["limitations"] else "") + INFERRED_LIMIT
            row["notes"] = (notes + " " if notes else "") + tag
        for key, value in TITLE_FIXES.get(did, {}).items():
            row[key] = value

        mapping_rows.append({
            "download_id": did, "source_id": row["source_id"], "state": state,
            "local_path": rel, "size_bytes": str(size), "sha256": digest, "match_basis": basis,
        })
        for m in manifest:
            if m["download_id"] == did:
                m.update(filename=filename, size_bytes=str(size), sha256=digest,
                         status="downloaded", fetched_on=RETRIEVED_ON)

    unmapped = [m["download_id"] for m in manifest if m["status"] != "downloaded"]
    if unmapped:
        raise SystemExit(f"manifest ids without a file: {unmapped}")

    write_csv(SOURCES, sources, src_cols)
    write_csv(MANIFEST, manifest, man_cols)
    write_csv(MAPPING, mapping_rows,
              ["download_id", "source_id", "state", "local_path", "size_bytes", "sha256", "match_basis"])
    print(f"mapped {len(mapping_rows)} files; sources.csv, manifest and {MAPPING.name} updated")


if __name__ == "__main__":
    main()
