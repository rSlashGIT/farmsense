"""
generate_dataset.py — FarmSense AI
Generates a deterministic synthetic Crop Recommendation Dataset (5,600 rows, 56 crops)
from the crop parameter distributions configured in this project.
Run this if you don't have crop_data.csv:
  python generate_dataset.py
"""

import numpy as np
import pandas as pd
from pathlib import Path

np.random.seed(42)

# Project-configured crop parameter ranges (mean, std) for N, P, K, temp, humidity, pH, rainfall.
# Validate or replace these ranges before making publication-grade agronomic provenance claims.
CROP_PARAMS = {
    # Base crop set
    "rice":        dict(N=(80,10),  P=(45,10),  K=(42,10),  temp=(23,2),  hum=(82,5),  ph=(6.5,0.3), rain=(202,30)),
    "wheat":       dict(N=(100,10), P=(46,10),  K=(42,10),  temp=(22,3),  hum=(65,8),  ph=(6.8,0.3), rain=(84,15)),
    "maize":       dict(N=(100,10), P=(60,10),  K=(60,10),  temp=(22,3),  hum=(65,10), ph=(6.2,0.4), rain=(85,15)),
    "chickpea":    dict(N=(40,10),  P=(67,10),  K=(79,10),  temp=(18,3),  hum=(16,5),  ph=(7.2,0.3), rain=(80,15)),
    "kidneybeans": dict(N=(20,5),   P=(67,10),  K=(20,5),   temp=(20,2),  hum=(22,5),  ph=(5.7,0.3), rain=(105,20)),
    "pigeonpeas":  dict(N=(20,5),   P=(67,10),  K=(20,5),   temp=(27,3),  hum=(48,7),  ph=(5.7,0.3), rain=(149,20)),
    "mothbeans":   dict(N=(21,5),   P=(47,8),   K=(20,5),   temp=(28,3),  hum=(53,8),  ph=(6.8,0.3), rain=(51,10)),
    "mungbean":    dict(N=(21,5),   P=(47,8),   K=(19,5),   temp=(28,3),  hum=(85,5),  ph=(6.7,0.3), rain=(49,10)),
    "blackgram":   dict(N=(40,8),   P=(67,10),  K=(19,5),   temp=(30,3),  hum=(65,8),  ph=(7.1,0.3), rain=(68,15)),
    "lentil":      dict(N=(19,5),   P=(68,10),  K=(19,5),   temp=(24,3),  hum=(65,8),  ph=(6.9,0.3), rain=(46,10)),
    "pomegranate": dict(N=(18,5),   P=(18,5),   K=(40,8),   temp=(21,3),  hum=(90,5),  ph=(6.0,0.4), rain=(107,20)),
    "banana":      dict(N=(100,10), P=(82,10),  K=(50,10),  temp=(27,2),  hum=(80,5),  ph=(5.9,0.3), rain=(105,20)),
    "mango":       dict(N=(20,5),   P=(27,5),   K=(30,5),   temp=(31,3),  hum=(50,8),  ph=(6.0,0.4), rain=(95,20)),
    "grapes":      dict(N=(23,5),   P=(22,5),   K=(30,5),   temp=(24,4),  hum=(81,5),  ph=(6.0,0.4), rain=(70,15)),
    "watermelon":  dict(N=(100,10), P=(10,3),   K=(50,8),   temp=(25,3),  hum=(85,5),  ph=(6.5,0.3), rain=(50,10)),
    "muskmelon":   dict(N=(100,10), P=(17,5),   K=(50,8),   temp=(28,3),  hum=(92,4),  ph=(6.5,0.3), rain=(25,8)),
    "apple":       dict(N=(21,5),   P=(134,10), K=(199,10), temp=(22,4),  hum=(92,4),  ph=(5.8,0.3), rain=(113,20)),
    "orange":      dict(N=(20,5),   P=(16,4),   K=(10,3),   temp=(22,3),  hum=(92,4),  ph=(7.0,0.3), rain=(111,20)),
    "papaya":      dict(N=(50,8),   P=(59,8),   K=(50,8),   temp=(33,3),  hum=(92,4),  ph=(6.5,0.3), rain=(145,25)),
    "coconut":     dict(N=(22,5),   P=(16,4),   K=(30,5),   temp=(27,2),  hum=(94,3),  ph=(5.8,0.3), rain=(176,25)),
    "cotton":      dict(N=(118,10), P=(46,8),   K=(43,8),   temp=(24,3),  hum=(79,5),  ph=(6.9,0.3), rain=(80,15)),
    "jute":        dict(N=(78,10),  P=(46,8),   K=(39,8),   temp=(25,3),  hum=(79,5),  ph=(6.7,0.3), rain=(175,25)),
    "coffee":      dict(N=(101,10), P=(28,6),   K=(29,6),   temp=(25,3),  hum=(58,8),  ph=(6.7,0.3), rain=(158,25)),
    
    # Extended crop set (vegetables, spices, cash crops, tubers, etc.)
    "tomato":      dict(N=(45,10),  P=(40,8),   K=(50,8),   temp=(25,3),  hum=(70,8),  ph=(6.5,0.3), rain=(60,15)),
    "potato":      dict(N=(70,12),  P=(50,8),   K=(80,15),  temp=(18,3),  hum=(65,8),  ph=(5.5,0.3), rain=(50,15)),
    "onion":       dict(N=(60,10),  P=(45,10),  K=(50,10),  temp=(22,3),  hum=(68,8),  ph=(6.5,0.3), rain=(55,15)),
    "garlic":      dict(N=(50,8),   P=(45,8),   K=(45,8),   temp=(18,3),  hum=(68,8),  ph=(6.8,0.3), rain=(65,15)),
    "ginger":      dict(N=(90,15),  P=(55,10),  K=(60,10),  temp=(28,3),  hum=(80,8),  ph=(6.0,0.3), rain=(150,30)),
    "turmeric":    dict(N=(100,15), P=(50,10),  K=(70,12),  temp=(28,3),  hum=(85,8),  ph=(6.0,0.3), rain=(160,30)),
    "chilli":      dict(N=(55,10),  P=(45,8),   K=(55,10),  temp=(26,3),  hum=(70,8),  ph=(6.5,0.3), rain=(70,15)),
    "capsicum":    dict(N=(60,10),  P=(50,8),   K=(60,10),  temp=(24,3),  hum=(75,8),  ph=(6.5,0.3), rain=(65,15)),
    "cabbage":     dict(N=(100,15), P=(45,8),   K=(80,10),  temp=(18,3),  hum=(70,8),  ph=(6.5,0.3), rain=(60,15)),
    "cauliflower": dict(N=(95,15),  P=(50,8),   K=(75,10),  temp=(17,3),  hum=(75,8),  ph=(6.2,0.3), rain=(55,15)),
    "spinach":     dict(N=(110,15), P=(35,8),   K=(65,10),  temp=(15,3),  hum=(65,8),  ph=(6.8,0.3), rain=(40,10)),
    "carrot":      dict(N=(40,10),  P=(45,8),   K=(95,15),  temp=(16,3),  hum=(60,8),  ph=(6.2,0.3), rain=(45,10)),
    "radish":      dict(N=(45,10),  P=(40,8),   K=(80,10),  temp=(18,3),  hum=(65,8),  ph=(6.5,0.3), rain=(40,10)),
    "sweet_potato":dict(N=(30,8),   P=(50,10),  K=(100,15), temp=(25,3),  hum=(75,8),  ph=(5.8,0.3), rain=(80,15)),
    "sugarcane":   dict(N=(130,20), P=(60,12),  K=(85,15),  temp=(30,4),  hum=(80,8),  ph=(6.5,0.3), rain=(180,30)),
    "tobacco":     dict(N=(90,15),  P=(60,10),  K=(80,15),  temp=(26,3),  hum=(70,8),  ph=(6.2,0.3), rain=(90,20)),
    "tea":         dict(N=(100,15), P=(30,8),   K=(40,10),  temp=(21,3),  hum=(85,8),  ph=(5.0,0.3), rain=(200,40)),
    "rubber":      dict(N=(80,15),  P=(25,6),   K=(35,8),   temp=(28,3),  hum=(90,8),  ph=(5.5,0.3), rain=(250,40)),
    "cashew":      dict(N=(50,10),  P=(20,5),   K=(30,8),   temp=(30,3),  hum=(70,8),  ph=(6.0,0.3), rain=(110,25)),
    "strawberry":  dict(N=(40,8),   P=(100,15), K=(110,15), temp=(15,3),  hum=(85,8),  ph=(6.0,0.3), rain=(60,15)),
    "pineapple":   dict(N=(95,15),  P=(35,8),   K=(85,15),  temp=(28,3),  hum=(80,8),  ph=(5.5,0.3), rain=(140,25)),
    "guava":       dict(N=(40,8),   P=(35,8),   K=(45,10),  temp=(28,3),  hum=(65,8),  ph=(6.5,0.3), rain=(100,20)),
    "lemon":       dict(N=(35,8),   P=(30,6),   K=(45,10),  temp=(25,3),  hum=(70,8),  ph=(6.5,0.3), rain=(100,20)),
    "mustard":     dict(N=(60,10),  P=(45,8),   K=(40,8),   temp=(20,3),  hum=(55,8),  ph=(6.8,0.3), rain=(40,10)),
    "sunflower":   dict(N=(55,10),  P=(50,8),   K=(55,10),  temp=(24,3),  hum=(60,8),  ph=(6.8,0.3), rain=(50,15)),
    "soybean":     dict(N=(20,5),   P=(65,10),  K=(45,8),   temp=(26,3),  hum=(70,8),  ph=(6.5,0.3), rain=(90,20)),
    "groundnut":   dict(N=(20,5),   P=(55,10),  K=(45,8),   temp=(28,3),  hum=(65,8),  ph=(6.8,0.3), rain=(70,15)),
    "sesame":      dict(N=(45,8),   P=(40,8),   K=(30,6),   temp=(30,3),  hum=(55,8),  ph=(6.5,0.3), rain=(45,10)),
    "castor":      dict(N=(50,10),  P=(45,8),   K=(40,8),   temp=(28,3),  hum=(50,8),  ph=(6.5,0.3), rain=(50,15)),
    "coriander":   dict(N=(45,8),   P=(35,8),   K=(40,8),   temp=(20,3),  hum=(60,8),  ph=(6.8,0.3), rain=(55,15)),
    "cumin":       dict(N=(40,8),   P=(30,6),   K=(35,8),   temp=(22,3),  hum=(50,8),  ph=(7.2,0.3), rain=(30,8)),
    "cardamom":    dict(N=(65,12),  P=(45,8),   K=(50,10),  temp=(24,3),  hum=(85,8),  ph=(5.8,0.3), rain=(220,35)),
    "pepper":      dict(N=(70,12),  P=(40,8),   K=(45,8),   temp=(26,3),  hum=(80,8),  ph=(6.0,0.3), rain=(190,30)),

}

SAMPLES_PER_CROP = 100  # 56 × 100 = 5,600 total

rows = []
for crop, params in CROP_PARAMS.items():
    n  = np.random.normal(params["N"][0],   params["N"][1],   SAMPLES_PER_CROP).clip(0, 140)
    p  = np.random.normal(params["P"][0],   params["P"][1],   SAMPLES_PER_CROP).clip(0, 145)
    k  = np.random.normal(params["K"][0],   params["K"][1],   SAMPLES_PER_CROP).clip(0, 205)
    t  = np.random.normal(params["temp"][0],params["temp"][1],SAMPLES_PER_CROP).clip(8, 50)
    h  = np.random.normal(params["hum"][0], params["hum"][1], SAMPLES_PER_CROP).clip(10, 100)
    ph = np.random.normal(params["ph"][0],  params["ph"][1],  SAMPLES_PER_CROP).clip(3.0, 10.0)
    r  = np.random.normal(params["rain"][0],params["rain"][1],SAMPLES_PER_CROP).clip(20, 300)

    for i in range(SAMPLES_PER_CROP):
        rows.append({
            "N": round(n[i], 2),
            "P": round(p[i], 2),
            "K": round(k[i], 2),
            "temperature": round(t[i], 2),
            "humidity":    round(h[i], 2),
            "ph":          round(ph[i], 2),
            "rainfall":    round(r[i], 2),
            "label":       crop,
        })

df = pd.DataFrame(rows)
df = df.sample(frac=1, random_state=42).reset_index(drop=True)

out = Path(__file__).parent / "data" / "crop_data.csv"
out.parent.mkdir(parents=True, exist_ok=True)
df.to_csv(out, index=False)
print(f"[OK] Generated {len(df)} rows ({df['label'].nunique()} crops) -> {out}")
print(df["label"].value_counts().to_string())
