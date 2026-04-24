import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import numpy as np

# --- Daten einlesen ---
data = {
    "Monat": ["2025-01","2025-02","2025-03","2025-04","2025-05","2025-06",
              "2025-07","2025-08","2025-09","2025-10","2025-11","2025-12"] * 3,
    "Strom_MWh": [
        2.244673761,2.032223689,2.247223187,2.177778614,2.250439378,2.177886088,
        2.250511707,2.250533497,2.177951427,2.250578488,2.177973967,2.250581623,
        1.346748753,1.202706414,1.377189438,1.394472065,1.516498391,1.494015087,
        1.347778878,1.427855839,1.372631559,1.405043421,1.296030656,1.329273134,
        1.327228664,1.199564879,1.335542781,1.315972868,1.36126917,1.34453195,
        1.330128985,1.341410923,1.299761366,1.331676426,1.295044713,1.328032043
    ],
    "CO2_jaehrlich_t": [
        623.9379962,564.8845717,624.6466441,605.3435684,625.5406287,605.3734423,
        625.5607336,625.5667903,605.3916041,625.5792962,605.3978694,625.5801677,
        374.3473696,334.308817,382.8087773,387.6127217,421.53162,415.2820761,
        374.633707,396.8922015,381.5418522,390.5511757,360.2495758,369.4897805,
        368.921492,333.435584,371.2325153,365.7927885,378.3835196,373.7311787,
        369.727676,372.8636462,361.286578,370.1578087,359.9755195,369.1448022
    ],
    "CO2_monatlich_t": [
        738.683713,785.7975221,785.1235858,625.750158,441.8403404,402.2955792,
        612.2615181,525.472196,514.5540924,594.0091103,708.7361648,627.914829,
        443.1919623,465.0490617,481.1555505,400.6794397,297.7419307,275.9720392,
        366.6691175,333.3869699,324.2924416,370.8418067,421.7423212,370.868714,
        436.7682353,463.834328,466.60525,378.12394,267.2649792,248.359757,
        361.8673872,313.2031336,307.0764212,351.4776015,421.4214849,370.5224483
    ],
    "CO2_woechentlich_t": [
        757.341379,761.5805125,790.9865748,613.5870897,455.5952726,400.7040939,
        608.9615319,529.2758113,503.5898608,603.4364216,704.6925068,632.9902759,
        451.5437877,449.9435253,483.8078458,392.3060339,307.3730353,274.7680251,
        364.4997806,333.5285233,315.3548806,372.2089765,418.2128625,373.7229744,
        446.762125,448.5007838,470.1202161,370.9409709,276.1015779,247.7196765,
        359.8666442,315.1261149,300.3086935,356.8941642,418.106243,373.4000909
    ],
    "CO2_stuendlich_t": [
        739.2138879,785.7993553,785.1201308,625.7498006,441.8423648,402.2966191,
        612.2630705,525.474968,514.5523758,594.0095026,708.7362575,627.9155823,
        431.6148772,462.0115467,461.1380421,369.0196325,266.4716118,239.4974155,
        348.1029328,306.2294622,299.5393581,347.8972449,414.5253877,362.2357569,
        428.5540197,458.9704087,452.4371582,357.1128767,250.1768056,224.9362782,
        343.1184754,296.1458039,291.4808914,340.8168444,412.8793616,360.6014413
    ],
    "CO2_15min_t": [
        739.2138879,785.7993553,785.1201308,625.7498006,441.8423648,402.2966191,
        612.2630705,525.474968,514.5523758,593.850288,708.7362575,627.4481759,
        431.6148772,462.0115467,461.1380421,369.0196325,266.4716118,239.4974155,
        348.1029328,306.2294622,299.5393581,347.7915937,414.5253877,361.9256108,
        428.5540197,458.9704087,452.4371582,357.1128767,250.1768056,224.9362782,
        343.1184754,296.1458039,291.4808914,340.7111932,412.8793616,360.2912952
    ],
    "Szenario": ["S1_Lastfolge"]*12 + ["S2_Kosten"]*12 + ["S3_Kosten_Emissionen"]*12
}

df = pd.DataFrame(data)
df["Monat"] = pd.to_datetime(df["Monat"])
df["Monat_kurz"] = df["Monat"].dt.strftime("%b")

# Farben & Labels
farben = {"S1_Lastfolge": "#1f77b4", "S2_Kosten": "#ff7f0e", "S3_Kosten_Emissionen": "#2ca02c"}
labels = {"S1_Lastfolge": "S1 – Lastfolge", "S2_Kosten": "S2 – Kosten", "S3_Kosten_Emissionen": "S3 – Kosten & Emissionen"}
resolutions = ["CO2_jaehrlich_t","CO2_monatlich_t","CO2_woechentlich_t","CO2_stuendlich_t","CO2_15min_t"]
res_labels = ["Jährlich","Monatlich","Wöchentlich","Stündlich","15 min"]

monate_kurz = df[df["Szenario"]=="S1_Lastfolge"]["Monat_kurz"].values

# ============================================================
# PLOT 1: Stromverbrauch je Szenario
# ============================================================
fig1, ax1 = plt.subplots(figsize=(12, 5))
x = np.arange(12)
breite = 0.25
for i, sz in enumerate(farben.keys()):
    werte = df[df["Szenario"]==sz]["Strom_MWh"].values
    ax1.bar(x + i*breite, werte, breite, label=labels[sz], color=farben[sz], edgecolor="white")
ax1.set_xlabel("Monat", fontsize=12)
ax1.set_ylabel("Stromverbrauch [MWh]", fontsize=12)
ax1.set_title("Monatlicher Stromverbrauch je Szenario (2025)", fontsize=14, fontweight="bold")
ax1.set_xticks(x + breite)
ax1.set_xticklabels(monate_kurz)
ax1.legend(fontsize=10)
ax1.grid(axis="y", alpha=0.3)
fig1.tight_layout()
plt.savefig("01_stromverbrauch.png", dpi=200)
plt.show()

# ============================================================
# PLOT 2: CO₂-Emissionen (monatliche Auflösung) je Szenario
# ============================================================
fig2, ax2 = plt.subplots(figsize=(12, 5))
for sz in farben:
    sub = df[df["Szenario"]==sz]
    ax2.plot(x, sub["CO2_monatlich_t"].values, marker="o", label=labels[sz], color=farben[sz], linewidth=2)
ax2.set_xlabel("Monat", fontsize=12)
ax2.set_ylabel("CO₂-Emissionen [t]", fontsize=12)
ax2.set_title("Monatliche CO₂-Emissionen je Szenario (monatl. Auflösung)", fontsize=14, fontweight="bold")
ax2.set_xticks(x)
ax2.set_xticklabels(monate_kurz)
ax2.legend(fontsize=10)
ax2.grid(alpha=0.3)
fig2.tight_layout()
plt.savefig("02_co2_monatlich.png", dpi=200)
plt.show()

# ============================================================
# PLOT 3: Vergleich zeitliche Auflösungen – ein Subplot pro Szenario
# ============================================================
fig3, axes = plt.subplots(1, 3, figsize=(18, 6), sharey=True)
for idx, sz in enumerate(farben.keys()):
    sub = df[df["Szenario"]==sz]
    for r, rl in zip(resolutions, res_labels):
        axes[idx].plot(x, sub[r].values, marker="s", markersize=4, label=rl, linewidth=1.5)
    axes[idx].set_title(labels[sz], fontsize=13, fontweight="bold")
    axes[idx].set_xticks(x)
    axes[idx].set_xticklabels(monate_kurz, fontsize=9)
    axes[idx].set_xlabel("Monat")
    axes[idx].grid(alpha=0.3)
    axes[idx].legend(fontsize=8, loc="upper right")
axes[0].set_ylabel("CO₂-Emissionen [t]", fontsize=12)
fig3.suptitle("CO₂-Emissionen nach zeitlicher Auflösung der Optimierung", fontsize=15, fontweight="bold", y=1.02)
fig3.tight_layout()
plt.savefig("03_co2_aufloesung_vergleich.png", dpi=200, bbox_inches="tight")
plt.show()

# ============================================================
# PLOT 4: Jahressumme CO₂ je Szenario & Auflösung (Heatmap)
# ============================================================
jahressumme = pd.DataFrame(index=list(labels.values()), columns=res_labels, dtype=float)
for sz, lbl in labels.items():
    sub = df[df["Szenario"]==sz]
    for r, rl in zip(resolutions, res_labels):
        jahressumme.loc[lbl, rl] = sub[r].sum()

fig4, ax4 = plt.subplots(figsize=(10, 4))
im = ax4.imshow(jahressumme.values.astype(float), cmap="YlOrRd", aspect="auto")
ax4.set_xticks(range(len(res_labels)))
ax4.set_xticklabels(res_labels, fontsize=11)
ax4.set_yticks(range(len(labels)))
ax4.set_yticklabels(list(labels.values()), fontsize=11)
for i in range(len(labels)):
    for j in range(len(res_labels)):
        val = jahressumme.values[i, j]
        ax4.text(j, i, f"{val:.0f}", ha="center", va="center", fontsize=10,
                 color="white" if val > 5500 else "black", fontweight="bold")
cbar = fig4.colorbar(im, ax=ax4)
cbar.set_label("CO₂-Jahressumme [t]", fontsize=11)
ax4.set_title("Jahres-CO₂-Emissionen nach Szenario und Auflösung", fontsize=14, fontweight="bold")
fig4.tight_layout()
plt.savefig("04_heatmap_jahressumme.png", dpi=200)
plt.show()

# ============================================================
# PLOT 5: Abweichung zur 15-min-Auflösung (Referenz) je Szenario
# ============================================================
fig5, axes5 = plt.subplots(1, 3, figsize=(18, 6), sharey=True)
ref_col = "CO2_15min_t"
vergl_res = ["CO2_jaehrlich_t","CO2_monatlich_t","CO2_woechentlich_t","CO2_stuendlich_t"]
vergl_labels = ["Jährlich","Monatlich","Wöchentlich","Stündlich"]
cmap_abw = plt.cm.Set2

for idx, sz in enumerate(farben.keys()):
    sub = df[df["Szenario"]==sz].reset_index(drop=True)
    ref = sub[ref_col].values
    for k, (r, rl) in enumerate(zip(vergl_res, vergl_labels)):
        abw = ((sub[r].values - ref) / ref) * 100
        axes5[idx].bar(x + k*0.2, abw, 0.18, label=rl, color=cmap_abw(k), edgecolor="grey", linewidth=0.5)
    axes5[idx].axhline(0, color="black", linewidth=0.8)
    axes5[idx].set_title(labels[sz], fontsize=13, fontweight="bold")
    axes5[idx].set_xticks(x + 0.3)
    axes5[idx].set_xticklabels(monate_kurz, fontsize=9)
    axes5[idx].set_xlabel("Monat")
    axes5[idx].grid(axis="y", alpha=0.3)
    axes5[idx].legend(fontsize=8)
axes5[0].set_ylabel("Abweichung zur 15-min-Referenz [%]", fontsize=11)
fig5.suptitle("Relative Abweichung der CO₂-Werte zur 15-min-Auflösung", fontsize=15, fontweight="bold", y=1.02)
fig5.tight_layout()
plt.savefig("05_abweichung_referenz.png", dpi=200, bbox_inches="tight")
plt.show()

print("✅ Alle 5 Plots erstellt und gespeichert.")