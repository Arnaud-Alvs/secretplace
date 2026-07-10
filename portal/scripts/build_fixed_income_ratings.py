# -*- coding: utf-8 -*-
"""
build_fixed_income_ratings.py
==============================

Rafraichit les donnees de fixed_income.html en se basant sur la meme logique
que le fichier Excel_Fixed_Income_Search_4.xlsm utilise par la recherche.

SOURCE DE VERITE : Excel_Fixed_Income_Search_4.xlsm, feuille "Data"
  Table 1 (colonnes A-D) = maintenue a la main par l'equipe :
     A = Ticker Bloomberg
     B = Status (Recommended / Followed)
     C = Rating VALIDE par l'equipe (ce rating ecrase Bloomberg)
     D = Country ISO 2 lettres (ex: "CH" pour Holcim meme si l'ISIN est XS)

  Table 2 (colonnes M-P) = mapping pays :
     M = ISO code -> N = Country -> O = Region -> P = Sub-Region

DONNEES DE MARCHE : RISK_OBL.csv (export Bloomberg)
  - Prix, yields, spreads, duration, dates, coupon, etc.
  - Le TICKER (col O) sert de cle de jointure avec la table Excel
  - Fallback de rating si le ticker n'est pas dans la table Excel

LOGIQUE APPLIQUEE POUR CHAQUE OBLIGATION DU BLOC _BD :
  1) On recupere le ticker Bloomberg via RISK_OBL.csv (cle = ISIN)
  2) Si le ticker est dans la Table 1 du fichier Excel :
       - Rating   = Data!C (override manuel)
       - Country  = Data!D (override manuel, ex: CH pour Holcim)
       - Status   = Data!B (Recommended/Followed)
  3) Sinon (fallback) :
       - Rating   = RTG_SP, sinon RTG_SP_LT_FC_ISSUER_CREDIT (suffixe "u" retire)
       - Country  = BB_COUNTRY_CODE traduit en ISO, sinon prefixe ISIN
  4) Region/Sub-Region (toujours via la Table 2) :
       - Si country_iso trouve dans Table 2 -> on applique ses region/sub-region
  5) FILTRAGE (pour matcher le resultat final de l'Excel) :
       - On supprime les bonds sans ticker dans l'Excel
         (equivalent du VBA DeleteRecFollNone qui supprime Rec/Fol = None)
       - On supprime les bonds dont le rating final reste NR / N.A.

Utilisation :
  1. Placer ce fichier dans le meme dossier que :
        - fixed_income.html
        - RISK_OBL.csv
        - Excel_Fixed_Income_Search_4.xlsm (ou _3, _5, etc.)
  2. Double-cliquer dessus (ou : python build_fixed_income_ratings.py)
  3. Une sauvegarde fixed_income.html.backup est creee, puis le fichier
     est reecrit avec les donnees mises a jour.

Aucune dependance externe : bibliotheque standard Python uniquement.
"""

import csv
import glob
import json
import os
import shutil
import sys
import xml.etree.ElementTree as ET
import zipfile


# ---------------------------------------------------------------------------
# CONFIGURATION
# ---------------------------------------------------------------------------

# Dossier du script (peu importe d'ou on le lance, double-clic Windows ok)
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

HTML_FILE = os.path.join(SCRIPT_DIR, "fixed_income.html")
CSV_FILE = os.path.join(SCRIPT_DIR, "RISK_OBL.csv")
BACKUP_FILE = os.path.join(SCRIPT_DIR, "fixed_income.html.backup")

# Le nom exact du fichier Excel peut changer avec les versions (_3, _4, _5...)
# On cherche un pattern au lieu d'un nom fige.
EXCEL_PATTERN = os.path.join(SCRIPT_DIR, "Excel_Fixed_Income_Search*.xlsm")

# Valeurs qui signifient "pas de rating"
MISSING_RATING_VALUES = {"NR", "N.A.", "N/A", "", None}

# Noms de colonnes dans RISK_OBL.csv
COL_ISIN = "ID_ISIN"
COL_TICKER = "TICKER"
COL_RTG_SP = "RTG_SP"
COL_RTG_ISSUER = "RTG_SP_LT_FC_ISSUER_CREDIT"
COL_BB_COUNTRY = "BB_COUNTRY_CODE"


# ---------------------------------------------------------------------------
# TABLE DE FALLBACK : CODES BLOOMBERG -> CODES ISO 3166-1
# ---------------------------------------------------------------------------
# Utilisee uniquement pour les bonds dont le ticker n'est pas dans le fichier
# Excel. Bloomberg utilise ses propres codes pays (TU=Turkey, LX=Luxembourg,
# SZ=Switzerland, DE=Denmark, GE=Germany, etc.).

BB_TO_ISO = {
    "US": "US", "FR": "FR", "NE": "NL", "SZ": "CH", "EN": "GB", "GE": "DE",
    "CA": "CA", "LX": "LU", "SP": "ES", "AU": "AU", "MX": "MX", "AR": "AR",
    "IR": "IE", "CI": "KY", "TU": "TR", "IT": "IT", "RO": "RO", "AS": "AT",
    "JN": "JP", "BZ": "BR", "BE": "BE", "SI": "SG", "CO": "CO", "CL": "CL",
    "UA": "AE", "IN": "IN", "DE": "DK", "NO": "NO", "ID": "ID", "SR": "SA",
    "PD": "PL", "GR": "GR", "SW": "SE", "VZ": "VE", "FI": "FI", "PO": "PT",
    "SA": "ZA", "EG": "EG", "IS": "IL", "PE": "PE", "MO": "MA", "HU": "HU",
    "VS": "VG", "NZ": "NZ", "UK": "UA", "KZ": "KZ", "RU": "RU", "BD": "BM",
    "JE": "JE", "OM": "OM", "HK": "HK", "SK": "KR", "PN": "PA", "QA": "QA",
    "SL": "LK", "UZ": "UZ", "LC": "LI", "IV": "CI", "ED": "EC", "BJ": "BH",
    "TH": "TH", "LE": "LB", "MA": "MY", "ES": "ES", "MP": "MU", "CC": "CY",
    "IO": "IM", "BH": "BS", "CZ": "CZ", "PH": "PH", "BK": "BY", "MR": "MH",
    "MB": "MT", "JO": "JO", "LU": "LU", "BN": "BJ", "GH": "GH", "UR": "UY",
    "DR": "DO", "BP": "BG", "LR": "LR", "EL": "SV", "SV": "SI", "LN": "LT",
    "MQ": "MC", "KN": "KE", "NG": "NG", "SM": "SM", "AN": "AD", "TR": "TT",
    "AZ": "AZ", "SO": "SK", "KY": "KY", "KU": "KW", "PG": "PY", "HR": "HR",
    "LL": "LV", "TJ": "TJ", "CR": "CR", "YV": "ME", "PK": "PK", "GS": "GG",
    "MJ": "MN",
    "SNAT": "",
}

NON_COUNTRY_ISIN_PREFIXES = {"XS", "EU", "CS", "QT", "QZ"}


# ---------------------------------------------------------------------------
# ETAPE 1 : LIRE LE FICHIER EXCEL (tables ticker et ISO)
# ---------------------------------------------------------------------------
#
# On parse directement le .xlsm comme un zip XML, sans openpyxl, pour rester
# en bibliotheque standard (firewall corporate bloque pip).

_NS = {"s": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}


def _col_letter_to_idx(letter):
    """AA -> 26, BV -> 73 (0-indexe)."""
    n = 0
    for c in letter:
        if c.isalpha():
            n = n * 26 + (ord(c.upper()) - 64)
    return n - 1


def _read_shared_strings(zf):
    """Lit le fichier de chaines partagees d'un xlsx."""
    root = ET.fromstring(zf.read("xl/sharedStrings.xml"))
    out = []
    t_tag = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}t"
    for si in root.findall("s:si", _NS):
        out.append("".join((t.text or "") for t in si.iter(t_tag)))
    return out


def _find_data_sheet_path(zf):
    """
    Trouve le chemin XML de la feuille 'Data' dans le xlsm
    via workbook.xml + relationships.
    """
    wb = ET.fromstring(zf.read("xl/workbook.xml"))
    rid_key = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"
    data_rid = None
    for s in wb.findall(".//s:sheet", _NS):
        if s.attrib.get("name") == "Data":
            data_rid = s.attrib.get(rid_key)
            break
    if not data_rid:
        return None

    rels = ET.fromstring(zf.read("xl/_rels/workbook.xml.rels"))
    rel_tag = "{http://schemas.openxmlformats.org/package/2006/relationships}Relationship"
    for rel in rels.findall(rel_tag):
        if rel.attrib.get("Id") == data_rid:
            return "xl/" + rel.attrib["Target"]
    return None


def load_excel_tables(xlsm_path):
    """
    Charge les 2 tables de reference du fichier Excel :
      ticker_map : { "HOLNSW": {"status": "Recommended", "rating": "BB+", "country": "CH"} , ... }
      iso_map    : { "CH":     {"country": "Switzerland", "region": "Europe", "subregion": "Developed"} , ... }
    """
    print("Lecture du fichier Excel :", os.path.basename(xlsm_path))
    with zipfile.ZipFile(xlsm_path) as zf:
        shared = _read_shared_strings(zf)
        data_path = _find_data_sheet_path(zf)
        if not data_path:
            print("ERREUR : feuille 'Data' introuvable dans le fichier Excel")
            sys.exit(1)

        root = ET.fromstring(zf.read(data_path))

    ticker_map = {}
    iso_map = {}

    for row in root.findall(".//s:row", _NS):
        cells = {}
        for c in row.findall("s:c", _NS):
            ref = c.attrib.get("r", "")
            letter = "".join(ch for ch in ref if ch.isalpha())
            idx = _col_letter_to_idx(letter)
            t = c.attrib.get("t", "")
            v = c.find("s:v", _NS)
            if v is None:
                continue
            cells[idx] = shared[int(v.text)] if t == "s" else v.text

        # Table 1 (tickers) : colonnes A(0), B(1), C(2), D(3)
        tkr = (cells.get(0) or "").strip()
        status = (cells.get(1) or "").strip()
        rating = (cells.get(2) or "").strip()
        country = (cells.get(3) or "").strip()
        if tkr and status in {"Recommended", "Followed"}:
            ticker_map[tkr.upper()] = {
                "status": status,
                "rating": rating,
                "country": country.upper(),
            }

        # Table 2 (ISO) : colonnes M(12), N(13), O(14), P(15)
        iso = (cells.get(12) or "").strip()
        country_name = (cells.get(13) or "").strip()
        region = (cells.get(14) or "").strip()
        subregion = (cells.get(15) or "").strip()
        if iso and iso != "ISO":
            iso_map[iso.upper()] = {
                "country": country_name,
                "region": region,
                "subregion": subregion,
            }

    print("  Tickers charges : {}".format(len(ticker_map)))
    print("  Pays charges    : {}".format(len(iso_map)))
    return ticker_map, iso_map


# ---------------------------------------------------------------------------
# ETAPE 2 : LIRE RISK_OBL.csv
# ---------------------------------------------------------------------------

def _clean_rating(raw):
    """
    Nettoie un rating :
      - enleve les espaces
      - retire le suffixe "u" final (unsolicited)
      - retourne None si c'est "NR", "N.A.", vide, etc.
    """
    if raw is None:
        return None
    s = str(raw).strip()
    if not s:
        return None
    # S&P ajoute parfois un "u" minuscule final (unsolicited). Les vrais
    # ratings n'ont jamais de minuscule, donc on peut retirer en securite.
    if s.endswith("u") and len(s) > 1:
        s = s[:-1].rstrip()
    if s.upper() in {"NR", "N.A.", "N/A", "#N/A"}:
        return None
    return s


def load_risk_obl(path):
    """Lit RISK_OBL.csv. Retourne { ISIN: {...} } pour joindre par ISIN."""
    if not os.path.exists(path):
        print("ERREUR : fichier introuvable :", path)
        sys.exit(1)

    mapping = {}
    with open(path, "r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f, delimiter=";")
        for row in reader:
            isin = (row.get(COL_ISIN) or "").strip().upper()
            if not isin:
                continue
            mapping[isin] = {
                "ticker": (row.get(COL_TICKER) or "").strip().upper(),
                "rtg_sp": _clean_rating(row.get(COL_RTG_SP)),
                "rtg_issuer": _clean_rating(row.get(COL_RTG_ISSUER)),
                "bb_country": (row.get(COL_BB_COUNTRY) or "").strip().upper(),
            }
    print("RISK_OBL.csv lu : {} obligations indexees".format(len(mapping)))
    return mapping


# ---------------------------------------------------------------------------
# ETAPE 3 : EXTRAIRE ET SERIALISER LE BLOC _BD DU HTML
# ---------------------------------------------------------------------------

def extract_bd_block(html):
    """
    Trouve le bloc `const _BD=[...]` et retourne :
      bonds       = liste Python des obligations
      start_pos   = index du `[` dans le HTML
      end_pos     = index apres le `]`
    """
    anchor = "const _BD="
    start = html.find(anchor)
    if start == -1:
        print("ERREUR : 'const _BD=' introuvable dans fixed_income.html")
        sys.exit(1)

    bracket_open = html.find("[", start)
    bracket_close = html.find("];", bracket_open)
    if bracket_open == -1 or bracket_close == -1:
        print("ERREUR : delimiteurs du bloc _BD introuvables")
        sys.exit(1)

    json_text = html[bracket_open:bracket_close + 1]
    bonds = json.loads(json_text)
    print("Bloc _BD extrait : {} obligations".format(len(bonds)))
    return bonds, bracket_open, bracket_close + 1


def serialize_bd(bonds):
    """JSON compact sans espaces."""
    return json.dumps(bonds, ensure_ascii=False, separators=(",", ":"))


# ---------------------------------------------------------------------------
# ETAPE 4 : LOGIQUE METIER
# ---------------------------------------------------------------------------

def _derive_country_fallback(isin, bb_country_code):
    """
    Derive le code pays quand le ticker n'est pas dans la table Excel.

    Priorite :
      1. BB_COUNTRY_CODE (le pays de l'emetteur selon Bloomberg) traduit
         via BB_TO_ISO. C'est le plus fiable : pour Venezuela emettant en
         USD via un ISIN US-prefixe, Bloomberg a bien "VZ" -> "VE".
      2. 2 premieres lettres de l'ISIN si pas de BB_COUNTRY_CODE utilisable.

    Avant on faisait l'inverse (ISIN prefix en priorite) mais ca plantait
    pour les SPV : Venezuela bonds (US922...) classes US, Petrobras (US716...)
    classe US, etc. alors que le vrai emetteur est etranger.
    """
    bb = (bb_country_code or "").strip().upper()
    if bb in BB_TO_ISO:
        iso = BB_TO_ISO[bb]
        if iso:
            return iso

    # Fallback de dernier recours : prefixe ISIN
    if isin and len(isin) >= 2:
        prefix = isin[:2].upper()
        if prefix not in NON_COUNTRY_ISIN_PREFIXES and prefix.isalpha():
            return prefix
    return ""


def apply_logic(bonds, risk_obl, ticker_map, iso_map):
    """
    Applique sur chaque obligation :
      - rating (override Excel > fallback Bloomberg)
      - country (override Excel > fallback ISIN/BB)
      - status (override Excel)
      - region + sub-region (via ISO map)
    Puis filtre pour garder uniquement les obligations qui seraient
    presentes dans le fichier Excel final :
      - ticker present dans la feuille Data (sinon VBA les supprime)
      - rating valide (pas NR / N.A.)
    Retourne (kept_bonds, stats).
    """
    stats = {
        "ticker_match": 0,
        "ticker_miss": 0,
        "rating_fixed_fallback": 0,
        "rating_unresolved": 0,
        "region_updated": 0,
        "region_mismatches_fixed": [],  # exemples
        "removed_no_ticker": 0,
        "removed_nr_rating": 0,
        "kept": 0,
    }
    kept = []

    for bond in bonds:
        isin = (bond.get("n") or "").strip().upper()
        rb = risk_obl.get(isin, {})
        ticker = rb.get("ticker", "")
        old_rating = bond.get("r", "")
        old_region = bond.get("R", "")
        old_subregion = bond.get("S", "")

        # === 1) Lookup ticker dans la table Excel (source de verite) ===
        tkr_data = ticker_map.get(ticker) if ticker else None

        if tkr_data:
            stats["ticker_match"] += 1
            if tkr_data["rating"]:
                bond["r"] = tkr_data["rating"]
            if tkr_data["country"]:
                bond["C"] = tkr_data["country"].lower()
            if tkr_data["status"]:
                bond["rc"] = tkr_data["status"]
        else:
            stats["ticker_miss"] += 1
            # Fallback rating
            if old_rating in MISSING_RATING_VALUES:
                fallback = rb.get("rtg_issuer")
                if fallback:
                    bond["r"] = fallback
                    stats["rating_fixed_fallback"] += 1
                else:
                    stats["rating_unresolved"] += 1
            # Fallback pays
            if not bond.get("C"):
                bond["C"] = _derive_country_fallback(
                    isin, rb.get("bb_country", "")
                ).lower()

        # === 2) Region + sub-region depuis la table ISO (toujours applique) ===
        country_iso = (bond.get("C") or "").upper()
        if country_iso and country_iso in iso_map:
            new_region = iso_map[country_iso]["region"]
            new_subregion = iso_map[country_iso]["subregion"]
            if new_region and new_region != old_region:
                if len(stats["region_mismatches_fixed"]) < 10:
                    stats["region_mismatches_fixed"].append({
                        "isin": isin,
                        "issuer": bond.get("i", "")[:38],
                        "old": old_region or "(vide)",
                        "new": new_region,
                    })
                bond["R"] = new_region
                stats["region_updated"] += 1
            if new_subregion and new_subregion != old_subregion:
                bond["S"] = new_subregion

        # === 3) Filtres pour reproduire le resultat final du fichier Excel ===
        # Filtre 1 : ticker doit etre dans la table Data de l'Excel
        # (equivalent VBA DeleteRecFollNone : supprime les Rec/Fol = None)
        if not tkr_data:
            stats["removed_no_ticker"] += 1
            continue
        # Filtre 2 : rating doit etre valide (pas NR / N.A.)
        if bond.get("r", "") in MISSING_RATING_VALUES:
            stats["removed_nr_rating"] += 1
            continue

        stats["kept"] += 1
        kept.append(bond)

    return kept, stats


# ---------------------------------------------------------------------------
# ETAPE 5 : ECRIRE LE HTML
# ---------------------------------------------------------------------------

def write_updated_html(html, start_pos, end_pos, new_block):
    shutil.copyfile(HTML_FILE, BACKUP_FILE)
    print("Sauvegarde creee :", BACKUP_FILE)
    new_html = html[:start_pos] + new_block + html[end_pos:]
    with open(HTML_FILE, "w", encoding="utf-8", newline="") as f:
        f.write(new_html)
    print("Fichier mis a jour :", HTML_FILE)


# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------

def main():
    print("=" * 70)
    print("  FIXED INCOME : SYNCHRONISATION DONNEES PORTAIL")
    print("=" * 70)
    print("Dossier du script :", SCRIPT_DIR)
    print("")

    # Trouver le fichier Excel (pattern Excel_Fixed_Income_Search*.xlsm)
    excel_candidates = sorted(glob.glob(EXCEL_PATTERN))
    if not excel_candidates:
        print("ERREUR : aucun fichier Excel_Fixed_Income_Search*.xlsm trouve")
        print("Il doit etre a cote du script.")
        try: input("Appuyer sur Entree pour quitter...")
        except EOFError: pass
        sys.exit(1)
    # On prend le dernier (plus grand suffixe = version la plus recente)
    XLSM_FILE = excel_candidates[-1]

    for f, name in [(HTML_FILE, "fixed_income.html"),
                    (CSV_FILE, "RISK_OBL.csv"),
                    (XLSM_FILE, "Excel")]:
        if not os.path.exists(f):
            print("ERREUR : fichier manquant :", name)
            try: input("Appuyer sur Entree pour quitter...")
            except EOFError: pass
            sys.exit(1)

    print("HTML   :", os.path.basename(HTML_FILE))
    print("CSV    :", os.path.basename(CSV_FILE))
    print("Excel  :", os.path.basename(XLSM_FILE))
    print("")

    # 1) Excel
    ticker_map, iso_map = load_excel_tables(XLSM_FILE)

    # 2) RISK_OBL
    risk_obl = load_risk_obl(CSV_FILE)

    # 3) HTML
    with open(HTML_FILE, "r", encoding="utf-8") as f:
        html = f.read()
    bonds, start_pos, end_pos = extract_bd_block(html)

    # 4) Logique metier + filtrage
    original_count = len(bonds)
    kept_bonds, stats = apply_logic(bonds, risk_obl, ticker_map, iso_map)

    # 5) Rapport
    print("")
    print("-" * 70)
    print("  RESULTATS")
    print("-" * 70)
    print("Obligations avant filtrage : {}".format(original_count))
    print("Obligations conservees     : {}".format(stats["kept"]))
    print("")
    print("  Supprimees (pas de ticker dans Excel) : {}".format(stats["removed_no_ticker"]))
    print("  Supprimees (rating NR / N.A.)         : {}".format(stats["removed_nr_rating"]))
    print("")
    print("Detail sur les bonds conserves :")
    pct_match = stats["ticker_match"] / original_count if original_count else 0
    print("  Ticker dans table Excel (source de verite) : {} ({:.0%})".format(
        stats["ticker_match"], pct_match))
    print("  Region/Sub-region mises a jour             : {}".format(stats["region_updated"]))
    if stats["region_mismatches_fixed"]:
        print("\n  Exemples de corrections de region :")
        for ex in stats["region_mismatches_fixed"]:
            print("    {:<16} {:<38} {:<12} -> {}".format(
                ex["isin"], ex["issuer"], ex["old"], ex["new"]))

    # 6) Ecrire
    new_block = "[" + serialize_bd(kept_bonds)[1:-1] + "]"
    print("\nTaille nouveau bloc : {} caracteres".format(len(new_block)))
    write_updated_html(html, start_pos, end_pos, new_block)

    print("\nOK : {} obligations synchronisees avec {}".format(
        stats["kept"], os.path.basename(XLSM_FILE)))
    print("=" * 70)

    try: input("\nAppuyer sur Entree pour quitter...")
    except EOFError: pass


if __name__ == "__main__":
    main()
