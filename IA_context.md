# IA_context.md — People Analytics TTE Brasil

> Estado del documento: 2026-09-04  
> Alcance: primera versión del dashboard HTML de Ausentismo y Turn Over para Shipping Brasil.

Este documento permite continuar el proyecto sin asumir fuentes, reglas o métricas que no estén respaldadas por la implementación y los datos oficiales actuales. Una instrucción explícita y posterior del usuario siempre prevalece sobre este contexto.

## 1. Objetivo del proyecto

Construir un dashboard HTML autocontenido para publicar posteriormente en Grid. Debe reproducir, en la medida posible, la lectura operacional del dashboard regional **People Analytics TTE Brasil**, pero inicialmente sólo con fuentes oficiales ya confirmadas para el dashboard central/Monthly.

El dashboard resultante es:

`Dash_TTE_Brasil.html`

Nombre visible: **People Analytics TTE Brasil**.  
Subtítulo: **Ausentismo y Turn Over · Fuentes oficiales**.

La prioridad es consistencia métrica y trazabilidad, no una copia visual que introduzca datos o reglas no confirmadas.

## 2. Principios de trabajo acordados

- No inventar datos, targets, dimensiones, joins ni definiciones de negocio.
- Usar únicamente las fuentes oficiales configuradas hasta que se valide una fuente adicional.
- Mantener nombres de funciones, variables y comentarios explícitos.
- Conservar una arquitectura pequeña, modular y fácil de mantener.
- Centralizar parámetros editables —tablas, alcance, segmentos y excepciones— en `config/dashboard_config.json`.
- No guardar claves de servicio en el repositorio. BigQuery usa Application Default Credentials (ADC) del usuario.
- Todo nuevo filtro debe existir en el cubo de datos, tener una fuente identificada y no alterar silenciosamente sus denominadores.

## 3. Arquitectura actual

```text
config/dashboard_config.json
          │
          ▼
src/data_loader.py          Consultas parametrizadas a BigQuery
          │
          ▼
src/processors.py           Segmentación y cubo mensual agregable
          │
          ▼
src/builders.py             Serialización segura de datos al HTML
          │
          ▼
src/template_dashboard.html Interfaz, filtros, KPIs, barras y tabla
          │
          ▼
Dash_TTE_Brasil.html        Entregable portable para Grid
```

| Archivo | Responsabilidad |
|---|---|
| `config/dashboard_config.json` | Fuente única de verdad de alcance, tablas y reglas editables. |
| `src/data_loader.py` | Contiene el SQL y ejecuta únicamente las fuentes oficiales. |
| `src/processors.py` | Estandariza segmentos y construye las métricas aditivas al grano mensual. |
| `src/builders.py` | Inserta el cubo agregado en el template sin exponer credenciales ni SQL. |
| `src/template_dashboard.html` | HTML, CSS y JavaScript de filtros, cards, gráficos y tabla. |
| `src/gen_dashboard.py` | Punto de entrada: carga → procesa → genera. |
| `tests/fixtures/source_results_example.json` | Fixture sintético exclusivamente para pruebas locales; no es fuente productiva. |

## 4. Fuentes oficiales de BigQuery

Proyecto de facturación: `meli-people`.

| Fuente | Tabla | Uso actual | Precaución |
|---|---|---|---|
| Nómina | `meli-people.SILVER_PE_SHIPPING.LK_PE_NOMINA_COMPLETA_API_PLANNING_V2` | HC directo, bajas e ingresos. | Se filtra por Brasil, Shipping y agrupadores directos. |
| Externos | `meli-people.SILVER_PE_SHIPPING.KPI_LATAM_NC_TO_ALL` | HC y bajas de Representante Externo. | El conteo es `COUNT(*)`; no usarla para hirings individuales. |
| Ausentismo oficial | `meli-people.SILVER_PE_SHIPPING.KPI_LATAM_HYPER_ABS` | Dotación programada y ausentismo por tipo. | Mantener sus exclusiones de negocio. |
| Catálogo de ubicaciones | `meli-people.SILVER_PE_SHIPPING.TTE_REG_CLASSIFICADOR` | Región y Tipo de operación/Site. | No inferir dimensiones para ubicaciones sin mapeo. |

Cada consulta está parametrizada. `data_loader.py` fija un máximo de 160 GB facturables por consulta como protección preventiva de costo.

## 5. Alcance actual y segmentación

- País: `Brasil`.
- División: `Shipping`.
- Segmentos publicados:

| Segmento dashboard | Campo fuente / regla |
|---|---|
| `Determinado (CDBR)` | Nómina/Ausentismo con `Agrupador_1 = 'Representantes - CDBR'`. |
| `Indeterminado` | Nómina/Ausentismo con `Agrupador_1 = 'Representante'` y no externo. |
| `Externos` | Fuente de Externos; en Ausentismo, `colaborador_externo = 'Si'`. |
| `Total` | Agregación en el navegador de los tres segmentos anteriores. No es una fila duplicada del cubo. |

El grano del cubo publicado al navegador es:

`año × mes × segmento × región × tipo_de_operación`

Cada celda conserva solamente métricas aditivas. Las tasas se calculan después de filtrar, en JavaScript, para evitar promedios incorrectos de porcentajes.

## 6. Reglas vigentes

### Bajas

- Tipos publicados: `Renuncia`, `Despido`, `Abandono de empleo` y `No cuenta`.
- Se excluye `No cuenta` cuando `motivosDeSalida = 'Sin Especificar'`.
- Las bajas de directo provienen de Nómina y las de Externos de `KPI_LATAM_NC_TO_ALL`.

### Ausentismo

- Excluir `Motivo_ausentismo = 'N/A'`.
- Excluir categorías operativas `Melitlán` y `Citicenter`.
- Excluir temporalmente las ubicaciones sin dimensión TTE oficial:
  - `SC - SIMÕES FILHO SBA9`
  - `BELO HORIZONTE`
  - `SC - RIBEIRÃO PRETO SSP55`
  - `SC - SÃO BERNARDO CAMPO SSP52`
  - `FBM - SANTO ANDRÉ BRSP34`
- Para `BRES01` y `BRPR01`, cuando `CAT_TA = 'No MAP'`, el tipo de operación publicado es `Full`.
- La normalización visual `ART/ ACCIDENTES DE TRABAJO → INSS` está configurada, pero aún no se publica como filtro o desglose en la primera versión.

## 7. Definiciones métricas

| Métrica | Cálculo |
|---|---|
| HC mensual | Conteo de HC Histórico + HC Actual recibido de la fuente al mes. |
| HC promedio | Promedio aritmético de los HC mensuales visibles después de filtros. |
| TO mensual | `(Renuncias + Abandonos + Despidos + No cuenta) / HC mensual`. |
| TO del período filtrado | `Bajas acumuladas / HC promedio mensual del período`. |
| ABS Gestionable | `Ausentismo gestionable / Dotación programada`. |
| ABS No Gestionable | `Ausentismo no gestionable / Dotación programada`. |
| ABS Total | `(Gestionable + No gestionable + Otros) / Dotación programada`. |
| Share CDBR | `HC Determinado (CDBR) / HC directo`, donde HC directo excluye Externos. |

Los gráficos mensuales calculan cada componente sobre su denominador mensual. Por eso las secciones apiladas representan contribuciones porcentuales y su suma es la tasa mensual total.

## 8. Interfaz implementada

Filtros actualmente disponibles:

- Año.
- Mes.
- Región.
- Tipo de operación.
- Segmento: Total, Determinado (CDBR), Indeterminado o Externos.

Contenido:

- Cards: HC promedio, ABS Gestionable, ABS No Gestionable, ABS Total, Turn Over, Renuncia y Share CDBR.
- Barras apiladas de Ausentismo mensual: Gestionable, No gestionable y Otros.
- Barras apiladas de Turn Over mensual: Renuncia, Abandono, Despido y No cuenta.
- Etiqueta de porcentaje en cada componente distinto de cero y tasa total arriba de la barra, siguiendo la lectura del Looker TTE Brasil.
- Tabla mensual de detalle nominal y tasas.

## 9. Fuera de alcance por ahora

No se deben agregar hasta identificar y validar una fuente, un grano temporal y una regla de join:

- Director, Gerente, N3 y Tier 4–6.
- PBP, PCD y Localidade.
- INSS como filtro independiente.
- Campaña, Área, Subárea, Cargo, Seniority y Status.
- `TO Meta ACM` u otro target de Turn Over.

La ausencia de estos campos en el HTML actual no demuestra que no existan en alguna tabla. Demuestra únicamente que aún no están incorporados al contrato de datos oficial de este proyecto.

## 10. Ejecución

Preparación inicial:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
gcloud auth application-default login
```

Generar desde BigQuery:

```powershell
.\.venv\Scripts\python.exe src\gen_dashboard.py --year 2026 --last-month 9
```

Generar desde una extracción JSON para pruebas reproducibles:

```powershell
.\.venv\Scripts\python.exe src\gen_dashboard.py `
  --year 2026 `
  --last-month 9 `
  --source-results-json tests\fixtures\source_results_example.json
```

La corrida oficial realizada el 2026-09-04 generó 153 celdas agregadas para Brasil con meses disponibles de enero a septiembre de 2026. Un warning de ADC sin quota project puede aparecer; sólo requiere atención si BigQuery devuelve error de cuota o API.

## 11. Validaciones antes de publicar

1. Confirmar que el HTML se generó desde BigQuery, no desde el fixture de pruebas.
2. Comparar HC, bajas, dotación y ausentismo contra el dashboard central para el mismo corte y filtros.
3. Asegurar que las tasas se recalculen al cambiar filtros; nunca sumar ni promediar porcentajes visibles.
4. Confirmar visualmente etiquetas, leyendas, cards y tabla en el navegador.
5. Subir el HTML autocontenido a Grid sólo tras la validación funcional.

## 12. Próxima línea de investigación

Cuando el usuario comparta las tablas, fuentes Looker, SQL, LookML o campos calculados del dashboard regional de Brasil:

1. Registrar la fuente y el grano de cada nueva dimensión.
2. Compararla con las cuatro fuentes oficiales actuales.
3. Validar cardinalidad y temporalidad antes de cualquier join.
4. Medir el impacto sobre HC, bajas, dotación y tasas antes y después del join.
5. Añadir el campo a configuración, consulta, cubo, filtro e interfaz en una misma entrega.

