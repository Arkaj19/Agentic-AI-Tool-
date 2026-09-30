# MARC Mapping Rules: ECC → S/4HANA (Plant Data)

**Object:** Material master, plant data (ECC table MARC → S/4 migration structure S_MARC)
**Version:** v1 (demo)
**Scope:** Plant (WERKS) mapping only. All other S_MARC fields keep their standard template mapping.

---

## 1. Source

- The source is the ECC MARC extract stored in SharePoint (e.g. `MARC_DAP 8.10.26.XLSX`).
- One row in the extract is one material at one ECC plant.
- The material number is in the column "Material" (MATNR), and the ECC plant is in the column "Plant" (WERKS).

## 2. Split plants

A split plant is an ECC plant that becomes **two** S/4 plants. Every ECC row for that plant is copied once for each target plant. The copies are identical except for the plant.

| ECC plant | S/4 plants |
|---|---|
| 1021 | US27 and US30 |
| 1028 | US28 and US30 |
| 1030 | US32 and US33 |

Rules:
1. For plant **1021**, create one row for plant **US27** and one row for plant **US30**.
2. For plant **1028**, create one row for plant **US28** and one row for plant **US30**.
3. For plant **1030**, create one row for plant **US32** and one row for plant **US33**.

## 3. Other plants (one-to-one)

These ECC plants map to exactly one S/4 plant. Each ECC row produces one S/4 row.

| ECC plant | S/4 plant |
|---|---|
| 1025 | US29 |
| 1029 | CA02 |

Rules:
4. For plant **1025**, replace the plant with **US29**.
5. For plant **1029**, replace the plant with **CA02**.

## 4. Plants without a rule

6. If an ECC row has a plant not listed in sections 2 or 3, do **not** guess a target plant. Keep the row's ECC plant value, mark the row as **unmapped**, and report it for a decision.
7. Unmapped rows are not written to the S/4 load file until someone approves a mapping for that plant.

## 5. Expected results (for validation)

8. For each split plant, the number of S/4 rows must be exactly **2 ×** the number of ECC rows for that plant.
9. For each one-to-one plant, the number of S/4 rows must **equal** the number of ECC rows for that plant.
10. Every S/4 row must trace back to one ECC row (the same material and source plant). No S/4 row may exist without an ECC source.
11. Every material in a split plant must appear in **both** of its target plants.
12. The S/4 plant (WERKS) must never be blank.
