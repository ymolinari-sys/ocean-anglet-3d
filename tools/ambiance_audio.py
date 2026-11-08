# Ambiance sonore de la visite 3D — boucles 100 % synthétiques (numpy), AUCUNE source externe,
# aucun enregistrement tiers : mêmes recettes que film/build_audio.py (bande-son des films, validée),
# adaptées en boucles sans couture. Chaque texture est rendue avec une marge de fin, puis le début
# fond la continuation de la fin dans l'original (boucle()) : le point de bouclage tombe dans une
# matière identique, inaudible. Le viewer règle loopStart/loopEnd pour sauter le silence d'encodage MP3.
#   /Applications/Blender.app/Contents/Resources/5.2/python/bin/python3.13 tools/ambiance_audio.py
# Sorties : assets/audio/*.mp3 (mono pour les sources spatialisées, stéréo pour la musique) + SOURCES.json.
import numpy as np, subprocess, os, wave, json, tempfile, datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AUD = f'{ROOT}/assets/audio'
FFMPEG = os.path.expanduser('~/.local/bin/ffmpeg')
os.makedirs(AUD, exist_ok=True)
SR = 48000
rng = np.random.default_rng(11)

def lisse(x, n):
    """Moyenne glissante (passe-bas grossier)."""
    if n <= 1: return x
    c = np.cumsum(np.concatenate(([0.], x)))
    y = (c[n:] - c[:-n]) / n
    return np.concatenate((np.full(n - 1, y[0]), y))

def bruit(n): return rng.standard_normal(n)

def bruit_rose(n):
    b = bruit(n)
    return lisse(b, 7) + 0.4 * lisse(b, 45) + 0.15 * lisse(b, 300)

def boucle(x, fondu=1.0):
    """x rendu sur (durée + fondu) s → boucle de (durée) s : le début fond la continuation
    de la fin (x[N:]) dans l'original (x[:F]) ; x[N-1] → x[N] est continu par construction."""
    F = int(fondu * SR); N = len(x) - F
    y = x[:N].copy()
    w = np.linspace(0, 1, F)
    if x.ndim > 1: w = w[:, None]
    y[:F] = x[N:N + F] * (1 - w) + x[:F] * w
    return y

def rms_cible(x, db):
    """Niveau RMS cible (dBFS), crête bornée à −1 dB."""
    r = np.sqrt((x ** 2).mean())
    x = x * (10 ** (db / 20) / max(r, 1e-9))
    p = np.abs(x).max()
    if p > 0.89: x = x * (0.89 / p)
    return x

def ecrit_mp3(nom, x, stereo=False, q='7'):
    x = np.clip(x, -1, 1)
    pcm = (x * 32767).astype('<i2')
    with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f: wavp = f.name
    with wave.open(wavp, 'wb') as w:
        w.setnchannels(2 if stereo else 1); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes(pcm.tobytes())
    out = f'{AUD}/{nom}.mp3'
    subprocess.run([FFMPEG, '-y', '-loglevel', 'error', '-i', wavp,
                    '-codec:a', 'libmp3lame', '-q:a', q, out], check=True)
    os.remove(wavp)
    ko = os.path.getsize(out) / 1024
    print(f'→ {nom}.mp3  {len(x)/SR:.1f} s  {ko:.0f} Ko')
    return round(len(x) / SR, 2), os.path.getsize(out)

# ---------- les boucles (recettes de film/build_audio.py, sans enveloppes de début/fin) ----------
def amb_hotte(dur=12.0, F=1.0):
    n = int((dur + F) * SR); t = np.arange(n) / SR
    g = lisse(bruit(n), 90) * 2.2 + lisse(bruit(n), 18) * 0.5          # souffle large
    ron = 0.55 * np.sin(2 * np.pi * 96 * t + 0.8 * np.sin(2 * np.pi * 0.3 * t))   # ronronnement moteur
    mod = 1 + 0.06 * np.sin(2 * np.pi * 0.13 * t)                      # respiration lente du caisson
    return rms_cible(boucle((g + ron) * mod, F), -17)

def amb_friteuse(dur=12.0, F=1.0):
    n = int((dur + F) * SR); t = np.arange(n) / SR
    bulle = lisse(bruit(n), 40) * (0.6 + 0.4 * np.sin(2 * np.pi * 7.3 * t + lisse(bruit(n), 9000) * 4))
    pops = np.zeros(n)
    for _ in range(int(dur * 14)):                                     # éclats de bulles
        i = rng.integers(0, n - 900)
        pops[i:i + 900] += np.sin(2 * np.pi * rng.uniform(300, 800) * np.arange(900) / SR) \
            * np.exp(-np.linspace(0, 14, 900)) * rng.uniform(0.2, 0.6)
    hf = (bruit(n) - lisse(bruit(n), 6)) * (0.45 + 0.55 * np.clip(lisse(bruit(n), 24000) * 6 + .5, 0, 1))
    return rms_cible(boucle(bulle * 2.2 + pops + hf * 0.5, F), -17)

def amb_four(dur=12.0, F=1.0):
    n = int((dur + F) * SR); t = np.arange(n) / SR
    ventil = np.sin(2 * np.pi * 97 * t + 0.5 * np.sin(2 * np.pi * 0.21 * t)) \
        + 0.45 * np.sin(2 * np.pi * 194 * t + 0.7) + 0.2 * np.sin(2 * np.pi * 291 * t + 1.3)
    souffle = (lisse(bruit(n), 22) - lisse(bruit(n), 150)) * (1 + 0.25 * np.sin(2 * np.pi * 0.17 * t))
    return rms_cible(boucle(ventil * 0.28 + souffle * 2.0, F), -20)

def amb_plonge(dur=16.0, F=1.0):
    n = int((dur + F) * SR); t = np.arange(n) / SR
    jet = (bruit(n) - lisse(bruit(n), 10)) * (0.5 + 0.5 * np.clip(lisse(bruit(n), 20000) * 4 + .5, 0, 1))
    machine = lisse(bruit(n), 120) * (0.6 + 0.4 * np.sin(2 * np.pi * 0.4 * t)) * 2.5 \
        + 0.3 * np.sin(2 * np.pi * 73 * t + 0.4 * np.sin(2 * np.pi * 0.4 * t))     # cycle du lave-vaisselle
    vaisselle = np.zeros(n); tc = 0.8
    while tc < dur - 0.8:                                              # entrechocs de vaisselle, clairsemés
        d = rng.uniform(0.25, 0.5); m = int(d * SR); tv = np.arange(m) / SR; f0 = rng.uniform(900, 2400)
        s = sum(np.sin(2 * np.pi * f0 * r * tv) * np.exp(-tv * (14 + 9 * r)) * a
                for r, a in [(1, 1), (1.47, 0.6), (2.09, 0.45), (2.73, 0.3)]) * np.exp(-tv * 6)
        i = int(tc * SR)
        if i + m < n: vaisselle[i:i + m] += s * rng.uniform(0.25, 0.7)
        tc += rng.exponential(1 / 0.35)
    return rms_cible(boucle(jet * 1.0 + machine * 0.8 + vaisselle * 0.5, F), -18)

def amb_brouhaha(dur=24.0, F=1.0):
    n = int((dur + F) * SR)
    voix = sum(lisse(bruit(n), 70) * (0.5 + 0.5 * np.clip(lisse(bruit(n), 14000) * 5 + .4, 0, 1))
               for _ in range(2))                                      # murmure de la brigade, sans mots
    couteau = np.zeros(n); t = 0.3
    while t < dur - 0.3:                                               # rafales de découpe
        for _ in range(rng.integers(5, 11)):
            m = int(0.09 * SR); tt = np.arange(m) / SR
            s = np.sin(2 * np.pi * rng.uniform(160, 230) * tt) * np.exp(-tt * 55) * 0.9
            s += (bruit(m) - lisse(bruit(m), 4)) * np.exp(-tt * 180) * 0.5
            s += np.sin(2 * np.pi * rng.uniform(1900, 2600) * tt) * np.exp(-tt * 300) * 0.25
            i = int(t * SR)
            if i + m < n: couteau[i:i + m] += s * rng.uniform(0.5, 1.0)
            t += rng.normal(1 / 4.4, 0.02)
        t += rng.uniform(1.2, 3.0)
    cass = np.zeros(n); t = 1.0
    while t < dur - 1:                                                 # casseroles, rares
        d = rng.uniform(0.25, 0.5); m = int(d * SR); tv = np.arange(m) / SR; f0 = rng.uniform(900, 2400)
        s = sum(np.sin(2 * np.pi * f0 * r * tv) * np.exp(-tv * (14 + 9 * r)) * a
                for r, a in [(1, 1), (1.47, 0.6), (2.09, 0.45), (2.73, 0.3)]) * np.exp(-tv * 6)
        i = int(t * SR)
        if i + m < n: cass[i:i + m] += s * rng.uniform(0.25, 0.8)
        t += rng.exponential(1 / 0.14)
    return rms_cible(boucle(voix * 1.0 + couteau * 0.16 + cass * 0.3 + bruit_rose(n) * 0.12, F), -20)

def musique(dur=64.0, F=2.0):
    """Nappe ambiante douce : 4 accords de 16 s en fondu (cycle exactement périodique sur 64 s),
    partiels doux légèrement désaccordés gauche/droite, cloches pentatoniques rares, échos courts."""
    n = int((dur + F) * SR); t = np.arange(n) / SR; tm = t % dur
    ACC = [[110.00, 164.81, 220.00, 261.63],   # Am : A2 E3 A3 C4
           [87.31, 130.81, 174.61, 220.00],    # F  : F2 C3 F3 A3
           [130.81, 196.00, 261.63, 329.63],   # C  : C3 G3 C4 E4
           [98.00, 146.83, 196.00, 293.66]]    # G  : G2 D3 G3 D4
    seg = dur / len(ACC)
    cosr = lambda u: 0.5 - 0.5 * np.cos(np.pi * np.clip(u, 0, 1))
    L = np.zeros(n); R = np.zeros(n)
    for k, notes in enumerate(ACC):
        d = (tm - k * seg) % dur
        fen = lambda d: cosr((d + 1.5) / 3) * cosr((seg + 1.5 - d) / 3)
        w = np.maximum(fen(d), fen(d - dur))                           # fenêtre périodique, fondu de 3 s
        for j, f in enumerate(notes):
            det = 1 + 0.0012 * ((j % 2) * 2 - 1)
            vib = 0.25 * np.sin(2 * np.pi * 0.09 * t + j * 1.7)
            g = [1.0, 0.72, 0.55, 0.45][j]
            L += w * g * (np.sin(2 * np.pi * f * t + vib) + 0.33 * np.sin(2 * np.pi * 2 * f * det * t)
                          + 0.10 * np.sin(2 * np.pi * 3 * f * t + 0.5))
            R += w * g * (np.sin(2 * np.pi * f * det * t + vib + 0.6) + 0.33 * np.sin(2 * np.pi * 2 * f * t)
                          + 0.10 * np.sin(2 * np.pi * 3 * f * det * t))
    pent = [440.00, 523.25, 587.33, 659.26, 783.99]                    # cloches : La pentatonique
    for i, tc in enumerate(sorted(rng.uniform(3, dur - 4, 11))):
        f = pent[rng.integers(len(pent))]; m = int(3.0 * SR); tv = np.arange(m) / SR
        s = (np.sin(2 * np.pi * f * tv) + 0.18 * np.sin(2 * np.pi * 2.76 * f * tv)) * np.exp(-tv * 1.8) * 1.6
        i0 = int(tc * SR); pan = 0.3 + 0.4 * (i % 2)
        if i0 + m < n: L[i0:i0 + m] += s * (1 - pan); R[i0:i0 + m] += s * pan
    souffle = lisse(bruit(n), 300) * 0.5                               # air discret sous la nappe
    L += souffle; R += lisse(bruit(n), 300) * 0.5
    for d_s, g in [(0.031, 0.26), (0.057, 0.18), (0.089, 0.12)]:       # petite pièce (échos courts)
        k = int(d_s * SR)
        L[k:] += L[:-k].copy() * g; R[k:] += R[:-k].copy() * g * 0.9
    L = lisse(L, 6); R = lisse(R, 6)                                   # adoucit le haut
    return rms_cible(boucle(np.stack([L, R], 1), F), -24)

# ---------- fabrication + SOURCES.json ----------
FICHES = [
    ('hotte', amb_hotte, False, '7', 'Souffle du caisson de la hotte au-dessus de la ligne de cuisson, ronronnement moteur à 96 Hz.'),
    ('friteuse', amb_friteuse, False, '7', 'Bain des friteuses : bouillonnement, éclats de bulles, grésillement fin.'),
    ('four', amb_four, False, '7', 'Four mixte : ventilation (97 Hz et harmoniques), souffle de convection lent.'),
    ('plonge', amb_plonge, False, '7', "Plonge et lave-vaisselle à capot : jet d'eau, cycle machine, entrechocs de vaisselle."),
    ('brouhaha', amb_brouhaha, False, '7', 'Brigade au travail : murmure sans paroles, découpe au couteau, casseroles éparses.'),
    ('musique', musique, True, '6', "Musique d'ambiance douce : nappe de 4 accords (Am F C G) en cycle de 64 s, cloches pentatoniques rares."),
]
sources = {
    '_licence': "Tous les fichiers de ce dossier sont des créations EVI PRO : synthèse numérique maison "
                "(tools/ambiance_audio.py, numpy), même famille de recettes que la bande-son des films "
                "(film/build_audio.py). Aucune source externe, aucun enregistrement tiers, aucune licence à créditer. "
                "Libre d'usage et de diffusion par EVI PRO.",
    '_boucle': "Boucles sans couture (fondu de fin recopié au début). Le viewer saute le silence d'encodage MP3 "
               "avec loopStart ≈ 0,06 s et loopEnd = durée − 0,08 s.",
    '_date': str(datetime.date.today()),
    'fichiers': {},
}
for nom, fab, st, q, desc in FICHES:
    duree, octets = ecrit_mp3(nom, fab(), stereo=st, q=q)
    sources['fichiers'][nom + '.mp3'] = {
        'description': desc, 'duree_s': duree, 'octets': octets,
        'canaux': 'stéréo' if st else 'mono (source spatialisée)',
        'licence': 'création EVI PRO — synthèse maison, aucune source externe',
        'generation': f'tools/ambiance_audio.py (graine {11})',
    }
with open(f'{AUD}/SOURCES.json', 'w') as f:
    json.dump(sources, f, ensure_ascii=False, indent=2)
print('OK —', AUD, '· total', round(sum(v['octets'] for v in sources['fichiers'].values()) / 1048576, 2), 'Mo')
