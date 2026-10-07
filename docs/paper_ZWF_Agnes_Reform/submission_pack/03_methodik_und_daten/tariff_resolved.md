# tariff_resolved.md

Szenarische Kalibrierung, erlösäquivalent nur für das Referenzkollektiv bei unveränderter Absatzstruktur; kein veröffentlichtes Preisblatt. AgNes befindet sich am 2026-09-15 im Festlegungsentwurf (Konsultation bis 2026-09-18, Az. GBK-25-01-1#3, geplantes Inkrafttreten 2029-01-01) -- es existieren keine amtlichen k/t_B-Ziffern je Ebene.

## Ebene ms

- StromNEV >=2500h: LP=210.72 EUR/kW/a, AP=3.7 EUR/MWh
- StromNEV <2500h: LP=24.0 EUR/kW/a, AP=18.0 EUR/MWh
- AgNes (synthetic_first_order): alpha=0.45, f=2.75, k=219.97 EUR/kW/a, t_B=2500.0 h
  -> KP=120.98 EUR/kW/a, AP1=39.59 EUR/MWh, AP2=108.89 EUR/MWh
  -> h*=1746.0 h/a, theta=0.698

## Ebene ns

- StromNEV >=2500h: LP=164.66 EUR/kW/a, AP=20.5 EUR/MWh
- StromNEV <2500h: LP=18.8 EUR/kW/a, AP=99.7 EUR/MWh
- AgNes (synthetic_first_order): alpha=0.45, f=2.75, k=215.91 EUR/kW/a, t_B=2500.0 h
  -> KP=118.75 EUR/kW/a, AP1=38.86 EUR/MWh, AP2=106.88 EUR/MWh
  -> h*=1746.0 h/a, theta=0.698

## Ebene hs_ms

- StromNEV >=2500h: LP=123.12 EUR/kW/a, AP=10.2 EUR/MWh
- StromNEV <2500h: LP=14.0 EUR/kW/a, AP=49.6 EUR/MWh
- AgNes (synthetic_first_order): alpha=0.45, f=2.75, k=148.62 EUR/kW/a, t_B=2500.0 h
  -> KP=81.74 EUR/kW/a, AP1=26.75 EUR/MWh, AP2=73.57 EUR/MWh
  -> h*=1746.0 h/a, theta=0.698

theta-Spannweite (alpha in [0.30,0.60], f in [2.0,3.5]): 0.267 .. 2.333 (Faktor 8.75)