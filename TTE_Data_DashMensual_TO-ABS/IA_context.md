# IA_context.md — People Analytics TTE Brasil

> Estado del documento: 2026-09-07
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
| Fuerza laboral y bajas | `NOMINA_ALL` (`meli-people.SILVER_PE_SHIPPING.KPI_LATAM_NC_TO_ALL`) | HC, bajas e ingresos de Directos y Externos. | Directos Brasil validados contra Nómina Shipping para 2024–2026; Externos sin PBP informado. |
| Ausentismo oficial | `HYPER_ABS` (`meli-people.SILVER_PE_SHIPPING.KPI_LATAM_HYPER_ABS`) | Dotación programada y ausentismo por tipo. | Mantener sus exclusiones de negocio. |
| Catálogo de ubicaciones | `meli-people.SILVER_PE_SHIPPING.TTE_REG_CLASSIFICADOR` | Región y Tipo de operación/Site. | No inferir dimensiones para ubicaciones sin mapeo. |

Convención terminológica del proyecto: `NOMINA_ALL` es el alias funcional de `meli-people.SILVER_PE_SHIPPING.KPI_LATAM_NC_TO_ALL`. El nombre físico sólo se conserva en la configuración y cuando sea necesario para trazabilidad técnica.

Cada consulta está parametrizada. `data_loader.py` fija un máximo de 160 GB facturables por consulta como protección preventiva de costo.

## 5. Alcance actual y segmentación

- País: `Brasil`.
- Alcance de Directos: `Brasil + Agrupador_1`; equivalencia exacta contra `Brasil + Shipping` de Nómina validada para 2024–2026.
- Segmentos publicados:

| Segmento dashboard | Campo fuente / regla |
|---|---|
| `Determinado (CDBR)` | NOMINA_ALL/HYPER_ABS con `Agrupador_1 = 'Representantes - CDBR'`. |
| `Indeterminado` | NOMINA_ALL/HYPER_ABS con `Agrupador_1 = 'Representante'` y no externo. |
| `Externos` | Fuente de Externos; en Ausentismo, `colaborador_externo = 'Si'`. |
| `Total` | Agregación en el navegador de los tres segmentos anteriores. No es una fila duplicada del cubo. |

El grano del cubo publicado al navegador es:

`año × mes × segmento × región × tipo_de_operación × site × área × subárea`

Cada celda conserva solamente métricas aditivas. Las tasas se calculan después de filtrar, en JavaScript, para evitar promedios incorrectos de porcentajes.

## 6. Reglas vigentes

### Bajas

- Tipos publicados: `Renuncia`, `Despido`, `Abandono de empleo` y `No cuenta`.
- Se excluye `No cuenta` cuando `motivosDeSalida = 'Sin Especificar'`.
- Las bajas de Directos y Externos provienen de `NOMINA_ALL` (tabla física `KPI_LATAM_NC_TO_ALL`); se utiliza `tipoBaja`.

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
- Site operativo, normalizado como `UPPER(TRIM(Ubicacion__Nombre))` en NOMINA_ALL y `UPPER(TRIM(ubicacion))` en HYPER_ABS.
- PBP, normalizado desde el campo oficial de cada fuente; los valores vacíos se publican como `Sin PBP informado`.
- PCD, normalizado desde `Posee_Discapacidad` en Nómina/Turnover y Ausentismo; los valores vacíos se publican como `Sin PCD informado`.
- Supervisor, homologado como login: NOMINA_ALL resuelve `ID_de_sistema_del_usuario_lider` contra `ID_de_usuario_empleado → Nombre_de_usuario` dentro de NOMINA_ALL (tabla física `KPI_LATAM_NC_TO_ALL`); Ausentismo utiliza `Supervisor`. Externos sin cobertura común se publican como `Sin Supervisor informado`.
- Segmento: Total, Determinado (CDBR), Indeterminado o Externos.
- Tipo de baja multiselección: Renuncia, Abandono, Despido y No cuenta.
- Tipo de ausentismo multiselección: Gestionable, No gestionable y Otros.

Contenido:

- Cards: HC promedio, ABS Gestionable, ABS No Gestionable, ABS Total, Turn Over, Renuncia y Share CDBR.
- Barras apiladas de Ausentismo mensual: Gestionable, No gestionable y Otros.
- Barras apiladas de Turn Over mensual: Renuncia, Abandono, Despido y No cuenta.
- Etiqueta de porcentaje en cada componente distinto de cero y tasa total arriba de la barra, siguiendo la lectura del Looker TTE Brasil.
- Comparativos mensuales CDBR vs. No CDBR para Ausentismo Gestionable y Turnover (Renuncia, Abandono y Despido).
- Gráfica de líneas de Ausentismo por los cuatro principales motivos.
- Gráfica de líneas de Turnover por Tipo de baja, con colores estables: Despido verde oliva y Renuncia azul oscuro.
- Las gráficas de detalle sólo muestran meses con datos disponibles; no dibujan futuros meses como cero.

## 9. Separación de alcance vigente

En `Overview_ABS-TO_Homologado` siguen fuera de alcance Director, Gerente, N3, Tier 4–6, Localidade, INSS, Campaña, Cargo, Seniority, Status y TO Meta ACM porque aún no pertenecen al contrato central homologado.

Esos campos sí se publican en `Overview_ABS-TO_TeamTTE` desde la tabla regional identificada. Su presencia en esa pestaña no implica que estén homologados ni autoriza unirlos silenciosamente a las fuentes centrales.

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

La corrida oficial posterior a la migración a NOMINA_ALL realizada el 2026-09-07 generó 13,821 celdas agregadas para Brasil con meses disponibles de enero a septiembre de 2026. Un warning de ADC sin quota project puede aparecer; sólo requiere atención si BigQuery devuelve error de cuota o API.

## 11. Validaciones antes de publicar

1. Confirmar que el HTML se generó desde BigQuery, no desde el fixture de pruebas.
2. Comparar HC, bajas, dotación y ausentismo contra el dashboard central para el mismo corte y filtros.
3. Asegurar que las tasas se recalculen al cambiar filtros; nunca sumar ni promediar porcentajes visibles.
4. Confirmar visualmente etiquetas, leyendas, cards y tabla en el navegador.
5. Subir el HTML autocontenido a Grid sólo tras la validación funcional.

## 12. Próxima línea de investigación

Cuando el usuario comparta las tablas, fuentes Looker, SQL, LookML o campos calculados del dashboard regional de Brasil:

1. Registrar la fuente y el grano de cada nueva dimensión.
2. Compararla con las tres fuentes oficiales actuales.
3. Validar cardinalidad y temporalidad antes de cualquier join.
4. Medir el impacto sobre HC, bajas, dotación y tasas antes y después del join.
5. Añadir el campo a configuración, consulta, cubo, filtro e interfaz en una misma entrega.


## 13. Hallazgo crítico de homologación: Turnover

La comparación con la referencia del dashboard Centralizado/Monthly People Planning muestra que el Turnover no está homologado todavía. Con TTE y Renuncia + Despido, el dashboard local calcula enero 2026 como `911 / 13,324 = 6.84%`, mientras la referencia visual es cercana a 8.0%, cuyo denominador implícito se aproxima a 7.9k.

No se debe consolidar la métrica hasta confirmar la definición Centralizado: población de HC, fecha/corte del denominador, tipos de baja incluidos y exclusiones. El detalle vivo de evidencias, hipótesis y próximos pasos está en `Analysisi_Homologacion.md`.

## 14. Objetivo de homologación

El objetivo final es disponer de un único dashboard con una sola versión trazable de la información para TTE Brasil y Centralizado, sin perder las dimensiones y granularidad requeridas por la operación local. Toda diferencia deberá cerrarse con fuente, numerador, denominador, población, período y regla de exclusión documentados.
## 15. Migración a fuente única para fuerza laboral y bajas

Desde 2026-09-07, HC, bajas e ingresos usan únicamente NOMINA_ALL (tabla física `KPI_LATAM_NC_TO_ALL`) para Directos y Externos. La equivalencia de Directos contra Nómina Shipping fue validada por llave Año × Mes × Tipo × Agrupador_1 × ID en 2024–2026, sin registros exclusivos ni diferencias en Área, Subárea, ubicación, PBP, fecha de contratación o clasificación de bajas. Nómina queda fuera del flujo productivo y sólo puede consultarse como referencia de homologación o para historia previa a 2024.

## 16. Segunda vista: Overview_ABS-TO_TeamTTE

Desde 2026-09-07 el mismo HTML contiene dos pestañas con contratos independientes:

- `Overview_ABS-TO_Homologado`: conserva las fuentes centralizadas y la lógica anterior.
- `Overview_ABS-TO_TeamTTE`: reproduce la página regional desde una sola fuente, sin mezclarla con el cubo homologado.

Fuente exclusiva de la vista regional:

`meli-people.SILVER_PE_SHIPPING.TTE_BRASIL_TABELA_BASE_PEOPLEBUSINESSPARTNER`

La tabla tiene 122 columnas físicas, 8.094.786 filas al corte 2026-09-07 y cobertura entre 2024-01-01 y 2026-09-07. No está particionada ni clusterizada. Por año contiene 1.270.456 filas en 2024, 2.793.704 en 2025 y 4.030.626 en 2026. Dentro del alcance inicial 2026, la llave `data_completa × consumer_id` es única: 3.590.324 llaves y cero duplicados.

Para que el HTML siga siendo portable, `team_tte_data_loader.py` agrega la fuente al grano:

`persona × año × mes × combinación de dimensiones regionales`

El payload multianual contiene 428.154 celdas persona-mes. Conserva `consumer_id`, por lo que los conteos distintos se recalculan después de filtrar; las métricas diarias se conservan como sumas aditivas.

### 16.1 Filtros regionales y campos físicos

| Filtro | Campo de la tabla regional |
|---|---|
| Año / Mes | `ano` / `mes` |
| PBP | `people_business_partner` |
| Campaña | `campana` |
| Director | `diretor` |
| Gerente | `gerente` |
| N3 | `n3` |
| Tier 4 / 5 / 6 | `tier4` / `tier5` / `tier6` |
| Región | `regiao` |
| Localidade | `localidade` |
| Área / Subárea | `area` / `subarea` |
| Cargo | `cargo` |
| Seniority | `seniority` |
| Status | `status_historico` |
| PCD | `pcd` |
| INSS | `afastado_inss` |

El filtro INSS no usa `inss`: esa columna es numérica y corresponde al dominio de costos. `afastado_inss` es la dimensión binaria `nao/sim` observada en Looker.

Las opciones se obtienen de los datos y son dependientes. No hay listas manuales para Cargo ni Seniority. El estado inicial replica los filtros de página del Looker:

- Año: `2026`; 2024 y 2025 permanecen disponibles.
- Seniority: `Non CDBR` y `Representantes - CDBR`; la tabla contiene 12 categorías.
- Status: `ativo`, `historico` y `transferido`; `purga` permanece disponible pero sin seleccionar.

El control `Periodo` de Looker es un rango diario. La primera versión HTML muestra el rango automático real y lo actualiza con Año/Mes, pero no permite un corte arbitrario por día: hacerlo exactamente exigiría publicar millones de filas diarias o una estrategia adicional de sketches para conteos distintos.

### 16.2 Métricas regionales confirmadas

| Tarjeta / gráfico | Regla regional |
|---|---|
| HC Medio | Conteo distinto de personas en ventanas de cierre mensuales / cantidad de meses. Para el mes actual usa los últimos 7 días; para meses cerrados usa día ≥28 en meses de 31 días, ≥27 en meses de 30 días y ≥25 en febrero. |
| ABS Gestionable | `SUM(faltas_gestionaveis) / SUM(dotacao_programada)` |
| Turnover ACM | `COUNTIF(tipo_turnover IS NOT NULL) / HC Medio` |
| TO Meta ACM | `SUM(turnover_meta) / HC Medio` |
| Renuncia ACM | `COUNTIF(tipo_turnover='Renuncia') / HC Medio` |
| Despido ACM | `COUNTIF(tipo_turnover='Despido') / HC Medio` |
| Abandono | `COUNTIF(motivo_saida='Abandono de emprego') / COUNTIF(tipo_turnover='Despido')` |
| Share CDBR | Personas distintas con `seniority='Representantes - CDBR'` / personas distintas totales |
| Barras ABS | Gestionable, no gestionable y otros / dotación programada mensual |
| Barras TO | Despido y Renuncia / personas distintas mensuales |
| Comparativo ABS | Gestionable de cada Seniority / dotación de ese mismo Seniority |
| Comparativo TO | Bajas de cada Seniority / personas distintas de ese mismo Seniority |

La fórmula exacta de HC Medio fue ejecutada contra BigQuery y devolvió `193.187 / 9 = 21.465,22`, mostrado como `21.465`.

Al corte actual, siete tarjetas coinciden exactamente con la captura. Turnover ACM devuelve 18.259 y 85,1%, mientras la captura conserva 18.283 y 85,2%; la diferencia son 24 eventos entre cortes de datos, no una diferencia de fórmula.

### 16.3 Módulos regionales

- `src/team_tte_data_loader.py`: SQL exclusivo de la tabla regional.
- `src/team_tte_processors.py`: contrato JSON regional y tipado explícito.
- `src/builders.py`: comprime por separado los payloads Homologado y Team TTE.
- `src/template_dashboard.html`: mantiene estados, filtros y renderizadores separados por pestaña.

La generación productiva multianual es:

```powershell
.\.venv\Scripts\python.exe src\gen_dashboard.py --first-year 2024 --year 2026 --last-month 9
```
## 17. Tercera vista: Overview_ABS-TO_Homologado+TTE

Esta vista experimental conserva como fuentes métricas exclusivas:

- `NOMINA_ALL` (tabla física `meli-people.SILVER_PE_SHIPPING.KPI_LATAM_NC_TO_ALL`) para HC, altas y bajas.
- `meli-people.SILVER_PE_SHIPPING.KPI_LATAM_HYPER_ABS` para dotación y ausentismo.

`meli-people.SILVER_PE_SHIPPING.TTE_BRASIL_TABELA_BASE_PEOPLEBUSINESSPARTNER` se usa únicamente para enriquecer dimensiones. No aporta ni sustituye numeradores o denominadores oficiales.

### 17.1 Llaves y temporalidad

| Familia oficial | Llave hacia TTE | Regla temporal |
|---|---|---|
| HC | `ID_de_usuario_empleado = consumer_id` + Año/Mes | Último registro TTE disponible de la persona dentro del mes. |
| Altas | `ID_de_usuario_empleado = consumer_id` | Fecha de contratación = `data_completa`. |
| Bajas | `ID_de_usuario_empleado = consumer_id` | Fecha de terminación = `data_completa`. |
| Ausentismo | `NK_Dim_Empleado = consumer_id` | `Dia = data_completa`. |
| Externos | Sin llave regional validada | Se conservan como `Sin cobertura TTE`. |

Todos los cruces son `LEFT JOIN`. La llave diaria `data_completa × consumer_id` fue validada como única. Para HC se aplica `ROW_NUMBER()` y se elige la fecha más reciente del mes para impedir relaciones muchos-a-muchos cuando una persona cambia de dimensión.

### 17.2 Dimensiones añadidas

Campaña, Director, Gerente, N3, Región TTE, Tier 4, Tier 5, Tier 6, Localidade, Cargo, Seniority, Status e INSS. La `Región homologada` existente no se sustituye; coexiste con `Región TTE` para permitir reconciliación.

Los controles de fuente centralizada se muestran en azul tenue y los de origen TTE en amarillo tenue. `Cobertura TTE` permite separar `Con cobertura TTE` y `Sin cobertura TTE`. Por defecto se incluyen ambos estados, de modo que abrir la pestaña no altera los totales oficiales.

### 17.3 Validaciones al corte 2026-09

- 162.619 celdas métricas enriquecidas y 373.394 celdas de motivos.
- Cero diferencias frente a la pestaña homologada al reagrupar las diez métricas por Año × Mes × Segmento.
- Cero diferencias en los motivos de ausentismo y de baja al reagruparlos sin dimensiones TTE.
- Cobertura descriptiva TTE: 34,5% del HC acumulado, 25,2% de la dotación programada, 23,3% del ausentismo gestionable, 21,4% de renuncias y 22,6% de despidos.

La cobertura parcial no es un error del `LEFT JOIN`; expresa que la tabla regional no cubre toda la población de las fuentes centrales. Aplicar un filtro TTE sí restringe el universo a los registros vinculados o a la categoría explícita elegida.

### 17.4 Módulos

- `src/homologated_tte_enrichment_loader.py`: SQL y reglas de cruce temporal.
- `src/homologated_tte_enrichment_processors.py`: contrato dimensional y cubo aditivo enriquecido.
- `tests/test_homologated_tte_enrichment.py`: regresiones sobre `LEFT JOIN`, temporalidad, coexistencia de regiones y conservación de métricas sin match.
### 17.5 Rendimiento del HTML

El HTML productivo pesa aproximadamente 41,17 MB porque incluye tres payloads comprimidos e independientes: Homologado 7,29 MB, Team TTE 13,43 MB y Homologado+TTE 20,36 MB en Base64. Mantenerlos embebidos es el costo de entregar un solo archivo portable para Grid.

Para evitar que el navegador convierta ese peso en bloqueos de interfaz se aplicaron estas reglas:

- Sólo la vista Homologada se descomprime al abrir el archivo; Team TTE y Homologado+TTE usan inicialización diferida al seleccionar su pestaña.
- Cada pestaña pesada se inicializa una sola vez y conserva su promesa de carga.
- Los filtros son dependientes entre sí: cada catálogo muestra únicamente valores compatibles con las demás selecciones activas. Los resultados se cachean por combinación de filtros y los controles desactualizados se recalculan al abrirlos, conservando selección múltiple, búsqueda y rendimiento.
- Cambiar un filtro reconstruye únicamente ese control, no todos los controles de la pestaña.
- El motor evalúa sólo filtros con selección explícita; `Todos seleccionados` no añade comparaciones por fila.
- Las celdas métricas filtradas se reutilizan en KPIs, barras y denominadores de motivos, evitando repetir la misma selección completa.

Estas optimizaciones no modifican payloads, métricas ni resultados; reducen trabajo de CPU y memoria en el navegador. Si el límite de tamaño de Grid exige una reducción adicional, el siguiente paso arquitectónico sería un contrato columnar/diccionario o payloads externos bajo demanda, sujeto a confirmar qué recursos admite Grid.
### 17.6 Ampliación controlada a los 12 Seniorities TTE

La vista Homologado+TTE publica las 12 categorías observadas en la fuente regional. NOMINA_ALL contiene correspondencias reales para todas ellas y `Agrupador_1` coincide exactamente con el `seniority` TTE. Los grupos adicionales sólo entran cuando existe match persona-periodo y ambos campos son idénticos; quedan agrupados en el segmento técnico `Otros Seniorities TTE`.

La selección inicial del filtro Seniority incluye `Non CDBR`, `Representantes - CDBR`, `Sin cobertura TTE` y `Sin Seniority informado`. Esta combinación preserva exactamente el universo de la vista Homologada; las otras diez categorías quedan disponibles para selección explícita.

HYPER_ABS sólo presentó correspondencias para `Non CDBR` y `Representantes - CDBR`. Por ello, los Seniorities adicionales tienen HC, altas y bajas de NOMINA_ALL, pero no dotación ni ausentismo. No se completa ese vacío con ceros inferidos ni con métricas de la tabla regional.

La validación productiva confirmó 12 opciones y cero diferencias en la selección inicial contra las diez métricas homologadas por Año × Mes × Segmento.
### 17.7 Exclusión de Melicidade

`Melicidade` no pertenece al alcance acordado. Se agregó a `business_rules.operational_categories_to_exclude` y se excluye en el origen de todas las métricas oficiales:

- NOMINA_ALL: `TTE_REG_CLASSIFICADOR.Site != 'Melicidade'` para HC, altas y bajas, tanto directos como externos.
- HYPER_ABS: `CAT_TA != 'Melicidade'` para dotación y ausentismo.

La regla se aplica por igual a Homologado y Homologado+TTE; no es un ocultamiento de la opción en HTML. La regeneración 2026-09 confirmó cero celdas `operationType = Melicidade`. La vista Homologada no cambió métricas porque ya no contenía población métrica de esa categoría; la ampliación de Seniorities en Homologado+TTE sí redujo el cubo de 175.308 a 173.800 celdas. `EXT` permanece como categoría independiente del clasificador y no forma parte de esta exclusión.