"""
Analyseur audio pour Xylophone Champion.

Charge un fichier MP3, détecte les instants de notes (onsets) et les
distribue sur 5 pistes en fonction du contenu fréquentiel (basses → aiguës).
Le résultat est mis en cache au format JSON pour éviter une re-analyse.

Auteurs: Julien Behani, Enzo Fournier - 2026
"""

import os
import json
import hashlib

from note import NUM_LANES

# Écart minimum (secondes) entre deux notes dans la même piste
_MIN_GAP_LANE = 0.25

# Écart minimum (secondes) entre deux notes consécutives (toutes pistes)
_MIN_GAP_GLOBAL = 0.08


def _cache_path(music_path: str, cache_dir: str) -> str:
    """
    Calcule le chemin du fichier cache pour une musique donnée.

    Le nom du cache inclut un hash MD5 des premiers octets du fichier afin
    de détecter les remplacements de fichier portant le même nom.

    Args:
        music_path: Chemin absolu ou relatif vers le fichier MP3.
        cache_dir: Dossier où stocker les caches.

    Returns:
        Chemin complet du fichier cache JSON.
    """
    with open(music_path, 'rb') as fh:
        digest = hashlib.md5(fh.read(8192)).hexdigest()[:8]
    basename = os.path.splitext(os.path.basename(music_path))[0]
    os.makedirs(cache_dir, exist_ok=True)
    return os.path.join(cache_dir, f"{basename}_{digest}.json")


def analyze_music(
    music_path: str,
    cache_dir: str = "cache",
) -> tuple[list[dict], float, float]:
    """
    Analyse un fichier MP3 et retourne la liste de notes générée.

    Si un cache valide existe pour ce fichier, il est utilisé directement.
    Sinon, librosa est utilisé pour :

    - Détecter le tempo.
    - Repérer les onsets (débuts de sons) via la force d'onset.
    - Attribuer chaque onset à une piste (0-4) selon sa bande fréquentielle
      dominante dans le CQT (basses → piste 0, aiguës → piste 4).

    Args:
        music_path: Chemin vers le fichier MP3.
        cache_dir: Dossier de cache (créé automatiquement si absent).

    Returns:
        Un triplet (notes, tempo, duration) où :
        - notes: liste de dict {'time': float, 'lane': int}
        - tempo: BPM détecté (float)
        - duration: durée totale de la musique en secondes (float)

    Raises:
        FileNotFoundError: Si music_path n'existe pas.
        RuntimeError: Si l'analyse échoue (fichier audio corrompu, etc.).
    """
    # --- Cache ---
    path = _cache_path(music_path, cache_dir)
    if os.path.exists(path):
        with open(path, 'r', encoding='utf-8') as fh:
            data = json.load(fh)
        return data['notes'], float(data['tempo']), float(data['duration'])

    # --- Analyse ---
    try:
        import librosa          # import différé : pas obligatoire au démarrage
        import numpy as np
    except ImportError as exc:
        raise RuntimeError(
            "librosa est requis pour l'analyse audio.\n"
            "Installez-le avec : pip install librosa"
        ) from exc

    y, sr = librosa.load(music_path, sr=22050, mono=True)
    duration = float(librosa.get_duration(y=y, sr=sr))

    # Tempo
    tempo_arr, _ = librosa.beat.beat_track(y=y, sr=sr)
    tempo = float(tempo_arr) if hasattr(tempo_arr, '__len__') else float(tempo_arr)

    # Détection des onsets
    onset_env = librosa.onset.onset_strength(y=y, sr=sr)
    onset_frames = librosa.onset.onset_detect(
        onset_envelope=onset_env,
        sr=sr,
        units='frames',
        delta=0.25,   # seuil : plus haut = moins de notes
        wait=6,       # frames minimum entre deux onsets (~130 ms à sr=22050)
    )
    onset_times = librosa.frames_to_time(onset_frames, sr=sr)

    # CQT pour l'analyse fréquentielle (60 bins = 5 octaves)
    cqt = np.abs(librosa.cqt(y, sr=sr, n_bins=60, bins_per_octave=12))
    band_size = cqt.shape[0] // NUM_LANES

    last_time_per_lane = {i: -999.0 for i in range(NUM_LANES)}
    last_any_time = -999.0
    notes = []

    for frame, time in zip(onset_frames, onset_times):
        # Ignorer si trop proche d'une note quelconque
        if time - last_any_time < _MIN_GAP_GLOBAL:
            continue

        # Sécurité : frame hors limites
        col = min(int(frame), cqt.shape[1] - 1)
        freq_content = cqt[:, col]

        # Énergie par bande fréquentielle
        band_energies = []
        for i in range(NUM_LANES):
            start = i * band_size
            end = (i + 1) * band_size if i < NUM_LANES - 1 else cqt.shape[0]
            band_energies.append(float(np.sum(freq_content[start:end])))

        # Choisir la piste avec le plus d'énergie,
        # en respectant l'écart minimum par piste
        sorted_lanes = sorted(range(NUM_LANES), key=lambda i: band_energies[i], reverse=True)
        chosen = None
        for lane in sorted_lanes:
            if time - last_time_per_lane[lane] >= _MIN_GAP_LANE:
                chosen = lane
                break

        if chosen is None:
            continue

        notes.append({'time': float(time), 'lane': int(chosen)})
        last_time_per_lane[chosen] = time
        last_any_time = time

    # --- Sauvegarde du cache ---
    data = {'notes': notes, 'tempo': tempo, 'duration': duration}
    with open(path, 'w', encoding='utf-8') as fh:
        json.dump(data, fh, indent=2)

    return notes, tempo, duration
