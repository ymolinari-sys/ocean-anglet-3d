#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Génère assets/fiches/equipements.json + copie FT PDF et photos produit.

Sources (zéro invention : un champ non sourcé est ABSENT, jamais deviné) :
- nomenclature Océan  : Projets/everpro/protos/equipements_ocean.json
  (repère, désignation, marque, référence, dimensions L×P×H)
- devis EBP v4        : Projets/gafic/devis_ocean_anglet/presentation/v4.json
  (puissance kW uniquement si le texte de la ligne du devis la donne,
   une seule valeur distincte par référence — sinon rien). AUCUN prix repris.
- FT Gafic            : presentation/ft/<ref>.pdf puis ft/<ref>.pdf
  (PDF copié tel quel ; photo produit = <ref>-1.jpg si présent, sinon la
   plus grande image JPEG de la page 1 via pdfimages, contrôlée à l'œil —
   les puissances des FT ne sont PAS extraites : fiches multi-modèles).

Noms de champs = schéma library_equipment du doc de conception everpro
(docs/conception-bibliotheque-equipements.md §2.3) + brand{code,label}
(library_brands) + files[{kind,path}] (library_equipment_files), pour que la
bibliothèque Supabase alimente la même fiche plus tard sans réécriture.
"""
import json, re, shutil, subprocess, tempfile
from pathlib import Path

WS = Path.home() / 'evipro-workspace'
SRC_NOMENCLATURE = WS / 'Projets/everpro/protos/equipements_ocean.json'
SRC_DEVIS = WS / 'Projets/gafic/devis_ocean_anglet/presentation/v4.json'
SRC_FT_DIRS = [WS / 'Projets/gafic/devis_ocean_anglet/presentation/ft',
               WS / 'Projets/gafic/devis_ocean_anglet/ft']
SITE = Path(__file__).resolve().parent.parent
OUT_DIR = SITE / 'assets/fiches'
PDFIMAGES = Path.home() / '.local/bin/pdfimages'

# Photos rejetées au contrôle visuel (logo, schéma coté… au lieu du produit)
EXCLUDE_PHOTOS = {'130828', '523903', '523907', '980485', '998142', 'A22113', 'B13503'}

def find_ft(ref):
    for d in SRC_FT_DIRS:
        p = d / f'{ref}.pdf'
        if p.exists():
            return p
    return None

def find_photo(ref, ft_pdf):
    for d in SRC_FT_DIRS:
        p = d / f'{ref}-1.jpg'
        if p.exists():
            return p
    if not ft_pdf or not PDFIMAGES.exists():
        return None
    # plus grande image JPEG de la page 1 (photo produit sur les FT Gafic)
    with tempfile.TemporaryDirectory() as tmp:
        subprocess.run([str(PDFIMAGES), '-j', '-f', '1', '-l', '1',
                        str(ft_pdf), f'{tmp}/im'], capture_output=True)
        best, best_px = None, 0
        for f in Path(tmp).glob('im-*.jpg'):
            try:
                out = subprocess.run(['sips', '-g', 'pixelWidth', '-g', 'pixelHeight', str(f)],
                                     capture_output=True, text=True).stdout
                w = int(re.search(r'pixelWidth: (\d+)', out).group(1))
                h = int(re.search(r'pixelHeight: (\d+)', out).group(1))
            except Exception:
                continue
            if w >= 250 and h >= 150 and max(w, h) / max(1, min(w, h)) <= 4 and w * h > best_px:
                best, best_px = f, w * h
        if best:
            keep = OUT_DIR / 'photos' / f'_extract_{ref}.jpg'
            shutil.copy(best, keep)
            return keep
    return None

def energie_du_label(label, famille):
    t = f'{label} {famille}'.lower()
    if 'électri' in t or 'electri' in t:
        return 'electrique'
    if re.search(r'\bgaz\b', t):
        return 'gaz'
    return None  # non dit par la nomenclature → champ absent

def puissances_devis():
    """ref -> kW, seulement si le texte du devis donne UNE valeur distincte."""
    lignes = json.loads(SRC_DEVIS.read_text())['lignes']
    vals = {}
    for l in lignes:
        ref = (l.get('item_reference') or '').strip()
        txt = l.get('description_text') or ''
        if not ref or not txt:
            continue
        for m in re.finditer(r'(?i)puissance[^\d]{0,40}(\d+(?:[.,]\d+)?)\s*(kw|w)\b', txt):
            kw = float(m.group(1).replace(',', '.'))
            if m.group(2).lower() == 'w':
                kw /= 1000.0
            vals.setdefault(ref, set()).add(round(kw, 3))
    return {r: v.pop() for r, v in vals.items() if len(v) == 1}

def main():
    nom = json.loads(SRC_NOMENCLATURE.read_text())
    puissances = puissances_devis()
    (OUT_DIR / 'ft').mkdir(parents=True, exist_ok=True)
    (OUT_DIR / 'photos').mkdir(parents=True, exist_ok=True)

    fiches, refs_vues = [], {}
    for e in nom['equipements']:
        if not e.get('repere'):
            continue  # hottes : pas de repère nomenclature, donc pas cliquables
        ref = (e.get('reference') or '').strip()
        marque = (e.get('marque') or '').strip()
        dims = e.get('dims_mm') or {}
        f = {'repere': e['repere'], 'scene': e.get('scene', 'ensemble'),
             'label': e['label']}
        if marque:
            f['brand'] = {'code': re.sub(r'[^A-Z0-9]+', '_', marque.upper()).strip('_'),
                          'label': marque}
        if ref:
            f['manufacturer_reference'] = ref
        for k, col in (('L', 'largeur_mm'), ('P', 'profondeur_mm'), ('H', 'hauteur_mm')):
            if dims.get(k):
                f[col] = dims[k]
        energie = energie_du_label(e.get('label', ''), e.get('famille', ''))
        if energie:
            f['energie'] = energie
        if ref in puissances:
            if energie == 'gaz':
                f['puissance_gaz_kw'] = puissances[ref]
            else:
                f['puissance_elec_kw'] = puissances[ref]
        if e.get('params'):
            f['params'] = e['params']

        files = []
        if ref:
            if ref not in refs_vues:
                ft, photo = find_ft(ref), None
                if ft:
                    shutil.copy(ft, OUT_DIR / 'ft' / f'{ref}.pdf')
                if ref not in EXCLUDE_PHOTOS:
                    photo = find_photo(ref, ft)
                if photo:
                    dst = OUT_DIR / 'photos' / f'{ref}.jpg'
                    if photo != dst:
                        shutil.copy(photo, dst)
                    subprocess.run(['sips', '-Z', '800', '-s', 'format', 'jpeg',
                                    '-s', 'formatOptions', '72', str(dst)], capture_output=True)
                refs_vues[ref] = {'ft': bool(ft), 'photo': bool(photo)}
            if refs_vues[ref]['ft']:
                files.append({'kind': 'ft_pdf', 'path': f'assets/fiches/ft/{ref}.pdf'})
            if refs_vues[ref]['photo']:
                files.append({'kind': 'photo', 'path': f'assets/fiches/photos/{ref}.jpg'})
        if files:
            f['files'] = files

        f['sources'] = {'nomenclature': 'equipements_ocean.json (everpro/protos, 11/2026)',
                        'devis': 'v4 EBP' if ref in puissances else None,
                        'ft': 'FT Gafic' if any(x['kind'] == 'ft_pdf' for x in files) else None}
        f['sources'] = {k: v for k, v in f['sources'].items() if v}
        manque = [c for c, ok in (
            ('manufacturer_reference', bool(ref)), ('energie', bool(energie)),
            ('puissance_elec_kw' if energie != 'gaz' else 'puissance_gaz_kw', ref in puissances),
            ('photo', bool(files and any(x['kind'] == 'photo' for x in files))),
            ('ft_pdf', bool(files and any(x['kind'] == 'ft_pdf' for x in files)))) if not ok]
        if manque:
            f['a_completer'] = manque
        # « C18 · C21 » (dessus commun de l'îlot) : une fiche par repère
        for code in re.split(r'\s*·\s*', f['repere']):
            fiches.append({**f, 'repere': code})

    fiches.sort(key=lambda x: x['repere'])
    out = {'_source': 'Nomenclature Océan Anglet (devis de base ZANUSSI) — généré par tools/fiches_data.py',
           '_schema': 'library_equipment + brand{code,label} + files[{kind,path}] (doc conception everpro §2.3)',
           '_note_prix': 'Aucun prix dans ce fichier : lien public client.',
           'equipements': fiches}
    (OUT_DIR / 'equipements.json').write_text(
        json.dumps(out, ensure_ascii=False, indent=1), encoding='utf-8')
    for p in (OUT_DIR / 'photos').glob('_extract_*.jpg'):
        p.unlink()
    n_ft = sum(1 for r in refs_vues.values() if r['ft'])
    n_ph = sum(1 for r in refs_vues.values() if r['photo'])
    print(f"{len(fiches)} fiches | {len(refs_vues)} réfs | FT {n_ft} | photos {n_ph} | "
          f"puissances {sum(1 for f in fiches if 'puissance_elec_kw' in f or 'puissance_gaz_kw' in f)}")

if __name__ == '__main__':
    main()
