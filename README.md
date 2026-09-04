# People Analytics TTE Brasil

Primera versión del dashboard HTML autocontenido para Ausentismo y Turn Over de Shipping Brasil. Usa exclusivamente fuentes oficiales ya confirmadas; no incorpora targets ni dimensiones organizacionales sin una fuente validada.

## Ejecutar

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
gcloud auth application-default login
python src/gen_dashboard.py --year 2026 --last-month 9
```

El resultado es `Dash_TTE_Brasil.html`. Para una corrida reproducible sin BigQuery, usar `--source-results-json ruta\resultados.json`.

## Alcance de esta versión

- País Brasil, año, mes, Región, Tipo de operación y Segmento.
- HC, HC promedio, bajas, TO, dotación programada y ausentismo.
- Segmentos: Total, Determinado (CDBR), Indeterminado y Externos.
- Sin targets, ni Director/Gerente/Tiers/PBP/PCD/Localidade, ni filtros no disponibles en el cubo oficial.
