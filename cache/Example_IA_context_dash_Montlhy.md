# IA_context.md — Guía de continuidad del proyecto

> Estado del documento: 2026-09-03
> Alcance: Dashboard mensual de People Analytics para Shipping LATAM.

Este archivo resume el contexto funcional y técnico necesario para continuar el proyecto de forma consistente. No sustituye una petición explícita del usuario: ante cualquier conflicto, la instrucción más reciente del usuario prevalece.

## 1. Propósito

Construir un dashboard HTML estático de seguimiento mensual para People Ops Analytics de Shipping en Brasil, México, Argentina y Chile. El dashboard se genera desde fuentes oficiales de BigQuery y permite analizar headcount, bajas, ingresos, turn over y ausentismo.

El entregable es un único HTML autocontenido:

`Dash_People_Analytics_Mensual.html`

El nombre visible del dashboard es **Monthly People Planning** y el subtítulo es **People Analytics · Shipping LATAM**. La jerarquía visual aprobada es: encabezado negro con acento amarillo estilo Meli, barra de filtros globales, pestañas y, finalmente, el contenido de la pestaña activa comenzando por sus cards. Los encabezados de las tablas siguen la misma combinación negro/amarillo; la vista Total usa grises, Determinados azules, Indeterminados amarillos y Externos verdes. Cada pestaña muestra, debajo de su título, un indicador discreto y dinámico de `Filtro activo · País` para hacer auditable la población que alimenta sus gráficos y tablas. Los filtros se mantienen compartidos para no alterar la comparabilidad entre Trends Mensuales y Turn Over.

## 2. Forma de trabajo esperada

- No inventar reglas de negocio, fuentes, mapeos o definiciones métricas.
- Ante una duda que pueda cambiar el resultado, documentarla y solicitar la definición correspondiente.
- Priorizar código explícito: nombres de funciones y variables descriptivos; comentarios que expliquen el porqué de cada regla.
- Mantener modularidad práctica, no fragmentación excesiva: pocos archivos, cada uno con una responsabilidad clara.
- Mantener una única fuente de verdad para parámetros y reglas editables: `config/dashboard_config.json`.
- No almacenar ni versionar claves de servicio. La conexión a BigQuery usa Application Default Credentials (ADC) del usuario.

## 3. Arquitectura actual

```text
config/dashboard_config.json
            │
            ▼
src/gen_dashboard.py       Punto de entrada único
            │
            ▼
src/data_loader.py         Consultas parametrizadas a BigQuery
            │
            ▼
src/processors.py          Reglas de negocio y cubo mensual
            │
            ▼
src/builders.py            Datos + configuración para el HTML
            │
            ▼
src/template_dashboard.html  Interfaz, filtros, gráficos y tablas
            │
            ▼
Dash_People_Analytics_Mensual.html
```

La estructura está deliberadamente contenida. No crear módulos nuevos para reglas pequeñas que pertenezcan claramente a uno de estos archivos.

## 4. Archivos que se usan

| Archivo | Responsabilidad |
|---|---|
| `config/dashboard_config.json` | Configuración central: tablas, países, segmentos, Peak, exclusiones y colores. |
| `src/gen_dashboard.py` | Ejecuta el flujo completo y escribe el HTML final. |
| `src/data_loader.py` | Carga configuración y ejecuta las cuatro consultas oficiales. |
| `src/processors.py` | Estandariza segmentos, aplica reglas y calcula el cubo de métricas. |
| `src/builders.py` | Serializa el cubo y la configuración visual hacia el template. |
| `src/template_dashboard.html` | HTML, CSS y JavaScript del dashboard. |
| `README.md` | Guía breve de instalación y ejecución. |
| `requirements.txt` | Dependencia productiva de BigQuery. |

## 5. Ejecución y autenticación

Instalación inicial:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Autenticación local, una vez por máquina o cuando expire la sesión:

```powershell
gcloud auth login
gcloud auth application-default login
```

Generación normal del dashboard:

```powershell
python src/gen_dashboard.py
```

No se usa `GOOGLE_APPLICATION_CREDENTIALS` ni una clave JSON de service account. El warning de ADC sin quota project no impide necesariamente la ejecución; sólo debe atenderse si BigQuery informa un error de cuota o API.

## 6. Fuentes oficiales de BigQuery

| Fuente | Rol en el dashboard | Precaución |
|---|---|---|
| `LK_PE_NOMINA_COMPLETA_API_PLANNING_V2` | Headcount directo, bajas, ingresos y denominador de Ratio TL. | La clasificación de directos y Team Leader depende de país y `Agrupador_1`. |
| `KPI_LATAM_NC_TO_ALL` | Headcount y bajas de Representante Externo. | Los IDs y fechas de terminación son placeholders; no contar personas distintas ni calcular ingresos con esta fuente. |
| `KPI_LATAM_HYPER_ABS` | Dotación programada y ausentismo oficial mensual. | Aplicar las excepciones CAT_TA y de ubicación configuradas. |
| `TTE_REG_CLASSIFICADOR` | Región y tipo de operación para ubicaciones mapeadas. | No asumir valores para ubicaciones sin catálogo. |

Proyecto de facturación actual: `meli-people`.

## 7. Alcance y segmentación

Alcance geográfico: Brasil, México, Argentina y Chile.  
División: `Shipping`.

### 7.1 Mapeo de colaboradores directos

| País | Determinados | Indeterminados |
|---|---|---|
| Brasil | `Representantes - CDBR` | `Representante` |
| México | `Representante eventual` | `Representante` |
| Argentina | `Representante Inicial` | `Representante` |
| Chile | `Representante Inicial` | `Representante` |

`Representante Externo` se trata como Externos. En Ausentismo se identifica mediante `colaborador_externo = 'Si'`; las exclusiones por país/año se aplican en la carga conforme a la configuración.

Excepción histórica aprobada: Externos de México 2025 con `Ubicacion__Nombre = '-'` se conservan como `Sin especificar` / `No MAP`. Es una regla estrictamente acotada, auditable y centralizada en `regla_externos_sin_ubicacion_historica`.

Excepción temporal aprobada: Externos de Chile 2026 con `Ubicacion__Nombre` `SVC CHILE` o `XD CHILE` se conservan como `Sin especificar` / `No MAP`. Aplica únicamente a la fuente `KPI_LATAM_NC_TO_ALL`, hasta recibir las dimensiones oficiales TTE, y está centralizada en `regla_externos_chile_sin_ubicacion_historica`.

### 7.2 Regla Peak

`Rep eventual - Peak`:

- Se incluye únicamente para México, abril de 2026.
- Se muestra como segmento `Peak` en el cubo.
- En los análisis de Turn Over participa sólo dentro de `Total`.
- No es Determinado ni Indeterminado.
- Debe conservarse esta regla aunque existan registros de Peak en otros meses de la fuente.

## 8. Reglas confirmadas de calidad y exclusión

### 8.1 Ubicaciones sin dimensión oficial TTE

Mientras no exista un mapeo oficial de `Región` y `Site` en `TTE_REG_CLASSIFICADOR`, las siguientes ubicaciones se excluyen de todos los cálculos comparables del dashboard (headcount, bajas, ingresos y ausentismo):

- `SC - SIMÕES FILHO SBA9`
- `BELO HORIZONTE`
- `SC - RIBEIRÃO PRETO SSP55`
- `SC - SÃO BERNARDO CAMPO SSP52`

- `FBM - Santo André BRSP34` (Brasil, septiembre 2026; exclusión temporal pendiente de mapeo TTE).
La exclusión está centralizada en `ubicaciones_temporalmente_excluidas` dentro de `config/dashboard_config.json`. No asignar una región o un tipo de operación por inferencia.

### 8.2 Ausentismo oficial

- Excluir `Motivo_ausentismo = 'N/A'`.
- Excluir categorías operativas `Melitlán` y `Citicenter`.
- Brasil: en visualizaciones desglosadas por motivo, `ART/ ACCIDENTES DE TRABAJO` se publica como `INSS`. Es una normalización de etiqueta de negocio; no cambia el valor fuente ni las métricas.
- México: los registros con `CAT_TA = 'No MAP'` no se incluyen.
- Chile: `SIN ESPECIFICAR` se conserva con región `Sin especificar` y tipo de operación `TTE`.
- Las excepciones `BRES01`, `BRPR01` y `FBM - COQUIMBO CLCO01` siguen las reglas nativas implementadas en la consulta de ausentismo.
- Externos de México y Argentina no se incluyen en Ausentismo 2026 según la regla oficial compartida.

Cualquier cambio a estas reglas debe hacerse primero en `dashboard_config.json` y, cuando aplique, reflejarse claramente en la consulta de `data_loader.py`.

## 9. Definiciones métricas vigentes

### Trends Mensuales

- Las líneas de TO y Ausentismo muestran su tasa redondeada a un decimal en una etiqueta tipo pill: TO en blanco/gris arriba y Ausentismo en crema/amarillo debajo. Las etiquetas con valor 0% se omiten para evitar ruido y, si las dos tasas de un mes se aproximan, se reubican automáticamente hacia afuera para no solaparse. Los totales nominales de bajas no se muestran sobre las barras para no competir con estas tasas.

- **HC mensual:** headcount al cierre del último día del mes, según definición interna.
- **HC promedio mensual YTD:** media aritmética de los headcounts mensuales visibles.
- **Bajas:** apiladas por Renuncia, Abandono de empleo, Despido y No cuenta. En Trends, barras y leyenda usan la paleta gris de Total definida en `visualizacion.colores_bajas`, salvo `No cuenta`, que se presenta en negro (`#1d1d1d`) para distinguirlo claramente de Despido. Esta excepción es exclusiva de Trends.
- **No cuenta:** excluye `motivosDeSalida = 'Sin Especificar'`.
- **TO mensual:** bajas del mes / HC mensual del mes.
- **TO acumulado YTD:** bajas acumuladas del periodo visible / HC promedio mensual YTD.
- **Ausentismo mensual:** ausentismo del mes / dotación programada del mes.
- **Ausentismo acumulado YTD:** ausentismo acumulado / dotación programada acumulada.
- **Hirings:** sólo directos, porque la fuente de Externos no tiene una fecha de contratación confiable.
- **Renuncias, Despidos y Abandonos YTD:** cada card muestra conteo acumulado y su porcentaje respecto al HC promedio mensual YTD.

Los porcentajes del hover usan dos decimales. El eje conserva una precisión visual más simple para no recargar el gráfico.

### Vista trimestral de Trends

Trends Mensuales presenta dos gráficas paralelas bajo las cards: **Trimestral** a la izquierda y **Mensual** a la derecha. Ambas responden a los mismos seis filtros globales y comparten una sola leyenda de bajas, TO y ausentismo.

- La gráfica y la tabla trimestrales agregan Renuncias, Abandonos, Despidos, No cuenta, Hirings y ausentismo de los meses incluidos. **HC promedio** es el promedio de los HC mensuales del periodo; el TO trimestral es `bajas del trimestre / HC promedio trimestral` y el ausentismo trimestral es `ausentismo acumulado / dotación programada acumulada`.
- La carga histórica de Trends se limita a enero–septiembre de 2025: Q1, Q2 y Q3 2025 están completos; Q4 queda fuera porque no está aprobado como información comparable. Las visualizaciones YTD mantienen su propio corte a último mes cerrado. Para el año de reporte se incluye además el trimestre en curso con meses cerrados: se marca con `*`, se detalla en la nota y el título muestra el corte. Con corte agosto de 2026, `Q3 '26*` contiene julio–agosto; septiembre abierto no participa.
- La tabla trimestral se ubica antes de la mensual e incluye HC promedio, Hirings, mezclas Meli vs Agencia e Indet vs Det, bajas nominales y variación QoQ. La tabla mensual conserva MoM y no cambia su lógica.
- La restricción histórica se aplica en `src/data_loader.py` con `source.Mes BETWEEN 1 AND 9` para `comparison_calendar_year`; no debe ampliarse a Q4 sin una aprobación explícita. Tras cada generación, comprobar que el cubo sólo entregue `2025-01` a `2025-09`.
- En escritorio, las seis cards existentes de Trends (tres KPIs generales y tres drivers YTD) se compactan en una sola franja para dar más área a las gráficas. En pantallas intermedias pasan a 3 × 2 y en móviles a una columna.
- Cada SVG ajusta su lienzo y márgenes al ancho real de la card. El margen derecho reserva espacios distintos para última barra, etiquetas de escala y título vertical, evitando superposiciones.
### Turn Over

La pestaña contiene las vistas, en este orden:

1. Total
2. Determinados
3. Indeterminados
4. Externos

Cada vista —**Total**, **Determinados**, **Indeterminados** y **Externos**— se presenta en una misma fila. **Total** aparece primero, seguido de los otros segmentos.

- A la **izquierda**, la gráfica mensual de TO por tipo de baja. Esta columna es intencionalmente más ancha para mostrar los meses con claridad. Sus barras apiladas representan Renuncias, Abandonos de empleo, Despidos y No cuenta; el total de TO va sobre la barra y los componentes se muestran de forma discreta dentro de ella cuando hay espacio. El segundo eje Y usa una composición pertinente a la vista: en **Total** y **Externos** es HC Mix (% Meli sobre Meli + Agencia); en **Determinados** es % Determinados (sobre Det + Indet), y en **Indeterminados** es % Indeterminados (sobre Det + Indet). Las dos últimas líneas son complementarias y usan el mismo universo filtrado.
- Debajo de cada gráfica mensual de **Total**, **Determinados**, **Indeterminados** y **Externos** se presenta una mini tabla de una fila con el **HC promedio mensual** por mes; funciona como contexto del denominador y no se duplica bajo el comparativo YTD.

- A la **derecha**, el comparativo YTD de TO por tipo de baja, incluido también para **Total**.
- Ambos gráficos comparten una sola leyenda debajo del par: Renuncia, Abandono de empleo, Despido, No cuenta y la línea correspondiente a la vista (HC Mix (% Meli), % Determinados o % Indeterminados). No duplicar la leyenda dentro de cada gráfico.

El comparativo YTD confronta el año anterior con el año de reporte, desde enero hasta el último mes cerrado. En septiembre de 2026, por ejemplo, compara enero–agosto de 2025 contra enero–agosto de 2026; septiembre no participa porque sigue abierto. Cada tasa es bajas acumuladas por tipo / HC promedio mensual YTD del mismo segmento.

### Composición del TO YTD

La pestaña Turn Over incluye, después de los gráficos por segmento y antes de la tabla, **Composición del TO YTD**. Es un ranking de drivers `segmento × tipo de baja`, ordenado por su contribución al TO total.

- **Contribución en pp:** `bajas YTD del componente / HC promedio mensual total YTD × 100`.
- **% de bajas:** participación nominal del componente sobre las bajas YTD actualmente seleccionadas.
- El denominador es común para todos los componentes; por eso la suma de sus aportes en pp coincide exactamente con el TO total YTD para los filtros activos.
- Se usa enero hasta el último mes cerrado del año de reporte. Responde a los mismos seis filtros del dashboard.
- Colores: Determinados azul, Indeterminados amarillo, Externos verde y Peak gris. Peak se muestra sólo si tiene bajas, para que el detalle siga sumando al Total sin clasificarlo artificialmente como Det o Indet.

Esta representación es preferible a comparar sólo tasas internas por segmento cuando el objetivo es priorizar acciones: identifica los componentes que realmente mueven el TO total, no sólo los que tienen una tasa alta en una población pequeña.
La tabla resumen de Turn Over responde a los mismos filtros y presenta valores nominales mensuales —HC promedio, Hirings, Renuncias, Abandonos, Despidos y No cuenta—, sus variaciones MoM y los cortes Meli vs Agencia e Indeterminados vs Determinados. No incluir una fila adicional de % Ausentismo en esa tabla.

Paleta visual:

- Determinados: azules.
- Indeterminados: amarillos.
- Externos: verdes.
- Total: grises.

Los filtros compartidos de ambas pestañas son: País, Tipo de baja, Región, Tipo de operación, Segmento y Tipo de ausentismo. Todos permiten selección múltiple; una selección vacía muestra Ninguno y no devuelve datos hasta elegir al menos un valor.

La lista de **Región** depende dinámicamente de los países seleccionados: con un país muestra únicamente sus regiones disponibles; con varios países muestra la unión de sus regiones. Al cambiar País, se eliminan selecciones de Región incompatibles y, si ninguna permanece, se seleccionan las regiones disponibles para evitar un resultado vacío involuntario.


### Ausentismo

La pestaña **Ausentismo** reutiliza la estructura visual y los filtros compartidos de Turn Over para que ambas lecturas sean comparables, sin mezclar sus denominadores.

1. Total
2. Determinados
3. Indeterminados
4. Externos

Cada segmento se muestra como un par de gráficos:

- A la **izquierda**, la serie mensual. Las barras apiladas son **Gestionable**, **No gestionable** y **Otros**, expresadas como porcentaje de la dotación programada mensual. El eje derecho es la línea de **dotación programada mensual** del segmento.
- A la **derecha**, el comparativo YTD del año anterior contra el año de reporte. Cada componente se calcula de forma ponderada: `ausentismo acumulado por tipo / dotación programada acumulada` entre enero y el último mes cerrado.
- Ambos gráficos comparten una sola leyenda por segmento. La paleta continúa por población: azules para Determinados, amarillos para Indeterminados, verdes para Externos y grises para Total. Peak sólo forma parte de Total.

La sección **Composición del ausentismo YTD** ordena los drivers `segmento × tipo de ausentismo` por su contribución en puntos porcentuales sobre la dotación programada acumulada total. Esto permite priorizar los componentes que explican el ausentismo total bajo los filtros activos. La tabla inferior presenta los nominales de ausentismo, las tasas por tipo, la tasa total y la dotación programada mensual para cada población.

### Waterfall de Ausentismo

La pestaña compara el **último mes cerrado** contra el mes cerrado inmediatamente anterior; con corte agosto de 2026, compara julio contra agosto. Usa la fuente oficial `KPI_LATAM_HYPER_ABS` y conserva `Motivo_ausentismo` para explicar el cambio.

- Cada driver es `Motivo_ausentismo × tipo de ausentismo` (Gestionable, No gestionable u Otros).
- El aporte se expresa en puntos porcentuales y usa una descomposición Shapley: separa el cambio de ausentismo por motivo del **efecto dotación programada**.
- La suma de los drivers reconcilia exactamente la variación entre las dos tasas mensuales. Se muestran los **cinco** motivos principales por impacto y se agrupa el resto como `Otros motivos`.
- El **efecto de dotación programada** es un ajuste neutral del denominador: cuantifica cuánto cambia la tasa por la variación de la dotación programada, sin atribuirlo a un motivo de ausentismo. Se conserva para que la descomposición reconcilie exactamente con la variación total.
- Visualmente, las etiquetas se muestran en una franja inferior alineada a cada barra, con chips `G`, `NG` u `O` para el tipo de ausentismo y `HC` para el efecto de dotación. El detalle completo permanece disponible en hover.
- Responde a País, Región, Tipo de operación, Segmento y Tipo de ausentismo. Tipo de baja no modifica esta métrica porque no es una dimensión de la fuente de Ausentismo.
### Heatmap de Ausentismo

La pestaña **Heatmap Ausentismo** analiza la intensidad mensual por `Motivo_ausentismo` con la misma fuente oficial y el mismo detalle que Waterfall.

- Las filas son motivos de ausentismo, ordenados por su volumen acumulado en el periodo; las columnas van desde enero del año comparativo hasta el último mes cerrado del año de reporte.
- Cada celda es `ausentismo del motivo / dotación programada total del mes × 100`. El denominador mensual es común para todos los motivos, permitiendo identificar los que más aportan a la tasa.
- La fila **Total** es la tasa mensual de los tipos de ausentismo seleccionados; no se excluyen motivos del total sin una regla explícita de negocio.
- Responde a País, Región, Tipo de operación, Segmento y Tipo de ausentismo. Tipo de baja no aplica, porque no existe en la fuente de Ausentismo.
- La escala verde–amarillo–rojo es visual y está centralizada en `visualizacion.heatmap_ausentismo` de `dashboard_config.json`. En pantallas pequeñas la tabla permite scroll horizontal y conserva fija la columna Motivo.
#### Contribución por driver y población

Debajo del Heatmap se muestra una matriz del **último mes cerrado** con columnas Det, Indet, Ext, Total y `%`.

- Cada celda en pp es `ausentismo del motivo y población / dotación programada total de la población filtrada × 100`.
- Todas las columnas comparten el mismo denominador. Esto permite comparar el impacto real de cada motivo sobre la tasa total; no representa la tasa interna de cada segmento.
- `%` es la participación del driver sobre el ausentismo total seleccionado del mes. Las filas se agrupan según Gestionable, No gestionable u Otros y la estrella marca el mayor driver de cada población.
- **Total** incorpora Peak solo cuando exista en el corte; Peak no tiene columna propia, de acuerdo con su tratamiento general.
- Responde a País, Región, Tipo de operación, Segmento y Tipo de ausentismo. Tipo de baja no aplica.
#### Evolución Pago vs No pago

La misma pestaña incorpora un gráfico de evolución y una tabla de composición mensual basados en el campo oficial `PAGO_NOPAGO` de `KPI_LATAM_HYPER_ABS`.

- `Pago` y `No Pago` se conservan con la clasificación publicada por la fuente.
- `DOTACION` se excluye: es un registro de denominador y no aporta ausentismo.
- `No Aplica`, valores vacíos y cualquier valor nuevo no mapeado se publican como **Sin clasificar**; no se infieren a partir del motivo.
- Cada mes muestra la participación de Pago, No pago y Sin clasificar sobre el ausentismo seleccionado; las tres categorías suman 100%.
- Responde a País, Región, Tipo de operación, Segmento y Tipo de ausentismo. Tipo de baja no aplica.
- El gráfico mantiene etiquetas porcentuales de 0% a 100%, pero no usa líneas horizontales de referencia; se prioriza una lectura visual limpia. En pantallas pequeñas, tanto el gráfico como la tabla permiten scroll horizontal sin recortar la serie.
## 9.1 KPIs por site

La pestaña **KPIs por site** usa el mismo alcance de filtros globales y se organiza por pais y tipo de operacion. No incluye Cob. Hiring ni targets.

- **HC:** headcount del ultimo mes cerrado por site.
- **TO YTD / ABS YTD:** tasas ponderadas hasta el ultimo mes cerrado. Las cards superiores comparan cada indicador del alcance filtrado contra el mismo YTD del ano anterior (vs LY), sin targets.
- **Delta TO / Delta ABS:** diferencia en puntos porcentuales entre el site y el promedio ponderado de su pais dentro del alcance filtrado. No es una comparacion contra target ni un promedio simple de sites.
- **Ratio TL:** `HC operativo directo activo / (Team Leader + Sr Team Leader activos)` al cierre del ultimo mes cerrado, por site. El numerador excluye Externos y Bajas; el denominador proviene de Nomina, con `Agrupador_1` igual a `Team Leader` o `Sr Team Leader`. Supervisor, Manager y Coordinator no se consideran TL.
- El estado visual de Ratio TL es 1:25-30 favorable, 1:20-24 o 1:31-35 neutral y fuera de esos rangos requiere atencion. Es una guia visual, no un target aprobado.
- Si un site no tiene HC directo o no tiene lideres capturados en Nomina, el Ratio TL se muestra como `—`; no se infiere ni se imputa.

Para esta pestaña, el cubo mensual conserva adicionalmente `site`, normalizado desde la ubicacion fuente. Las visualizaciones previas no filtran por ese campo y por ello mantienen sus agregados existentes. `team_leader_headcount` es una consulta separada y solo alimenta el denominador de Ratio TL.

Durante la corrida 2026-09 se identificaron tres filas de Team Leader sin Region/Tipo de operacion oficial: `SC - Cascavel SPR9` (Brasil), `SC - Guadalajara SGD5` (Mexico) y `RC - Itupeva BRRC05` (Brasil), todas en septiembre abierto. Se omiten explicitamente del denominador, sin asignarles una dimension inventada; no afectan el corte cerrado de agosto.
## 10. Métrica pendiente: ausentismo acumulado previo a la baja

La definición de negocio acordada es:

> **% Ausentismo acumulado previo a la baja** = suma del ausentismo acumulado previo de las personas que tuvieron esa baja / suma de su dotación acumulada previa.

Debe calcularse ponderado, no como promedio simple de porcentajes individuales.

Para implementarla correctamente hace falta una fuente individual de ausentismo, por ejemplo `LK_PE_SHIPPING_ABSENCES_PP`, y un join por ID de usuario con Nómina. La ventana temporal debe ir desde junio de 2023 hasta el día anterior a la fecha de terminación de cada persona.

Limitación vigente: la fuente de Externos usa IDs vacíos/placeholder. Por ello no es válido calcular el ausentismo previo a la baja para Externos, ni para un Total que los incluya, hasta contar con un identificador individual confiable o una definición alternativa aprobada. La línea actual de Turn Over no debe etiquetarse como esa métrica pendiente.

## 11. Criterios para cambios futuros

1. Revisar primero si la regla pertenece a configuración. Si es editable por negocio, centralizarla en `dashboard_config.json`.
2. Si cambia una fuente, validar schema, alcance temporal, país, segmentación y duplicidades antes de modificar el procesador.
3. No corregir ubicaciones inventando Región o Site; documentar y excluir temporalmente hasta recibir el catálogo oficial.
4. Mantener el cubo mensual como contrato interno entre `processors.py` y el HTML. Modificar ambos lados en una sola entrega cuando se agregue una métrica.
5. Mantener el dashboard autocontenido: no introducir servidores, bases locales ni pasos manuales adicionales sin solicitud explícita.
6. Después de cambios de lógica, ejecutar `python src/gen_dashboard.py` y revisar el HTML generado con los filtros, cards, hover, gráfico y tabla correspondientes.

## 12. Estado actual y siguientes decisiones útiles

Implementado:

- Dashboard HTML con pestañas Trends Mensuales, Turn Over, Ausentismo, Waterfall Ausentismo, Heatmap Ausentismo y KPIs por site.
- Filtros multi-selección compartidos.
- Cards YTD compactadas, gráficas trimestral y mensual, hover, tabla trimestral y tabla resumen mensual de Trends; histórico aprobado de Trends: enero–septiembre de 2025 (Q1–Q3, sin Q4).
- Reglas de país, Peak, Externos y exclusiones actuales centralizadas.

Pendiente de definición o de fuente:

- Fuente/identificador confiable para calcular ausentismo acumulado previo a la baja de Externos.
- Mapeo oficial TTE para las cinco ubicaciones excluidas temporalmente y para las dos ubicaciones de Externos Chile conservadas como Sin especificar / No MAP.
- Cualquier nueva pestaña debe definirse con sus métricas, nivel de detalle, fuente y reglas antes de construirla.
