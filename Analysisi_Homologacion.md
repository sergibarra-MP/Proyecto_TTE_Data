# Analysisi_Homologacion — TTE Brasil vs. Centralizado

> Estado: en investigación  
> Última actualización: 2026-09-05

## Objetivo final

Entender y documentar completamente las diferencias y similitudes entre el dashboard local del equipo **TTE Brasil** y el dashboard **Centralizado / Monthly People Planning**. El resultado objetivo es un solo dashboard, con una única versión trazable de la información, que conserve toda la granularidad necesaria para la operación local.

## Principios de homologación

- No declarar métricas como homologadas sólo por tener nombres similares.
- Comparar siempre mismo período, país, población, filtros y denominador.
- Mantener la fuente y regla de negocio de cada métrica documentadas.
- Preservar dimensiones locales que sean necesarias para la operación, aun si no están disponibles en la primera versión centralizada.
- Resolver diferencias de definición antes de consolidar los dashboards.

## Fuentes actualmente utilizadas en el dashboard TTE Brasil

| Dominio | Fuente oficial actual | Uso |
|---|---|---|
| HC, bajas e ingresos directos | `LK_PE_NOMINA_COMPLETA_API_PLANNING_V2` | HC, tipos y motivos de baja, Área, Subárea, Site. |
| HC y bajas externos | `KPI_LATAM_NC_TO_ALL` | Segmento Externos, tipos y motivos de baja, Área, Subárea, Site. |
| Ausentismo | `KPI_LATAM_HYPER_ABS` | Dotación, tipos y motivos de ausentismo, Área, Subárea, Site. |
| Clasificador | `TTE_REG_CLASSIFICADOR` | Región y Tipo de operación. |

## Grano de información publicado

El cubo actual se publica al grano:

`año × mes × segmento × región × tipo de operación × site × área × subárea`

También se conservan series mensuales por motivo de ausentismo y motivo de baja para las gráficas de detalle.

## Capacidades ya incorporadas

- Filtros dependientes: Año, Mes, Región, Área, Subárea, Tipo de operación, Site y Segmento.
- Filtros multiselección: Tipo de baja y Tipo de ausentismo.
- Gráficas mensuales de Ausentismo y Turnover.
- Comparativos CDBR vs. No CDBR.
- Gráficas de motivos mensuales; muestran los cuatro motivos con mayor incidencia bajo el contexto seleccionado.
- Los gráficos de motivos sólo muestran meses con datos disponibles; para 2026, actualmente enero a septiembre.

## Hallazgos de homologación

### H-01 — Cobertura de Área y Subárea

**Estado:** confirmado.

Las tres fuentes operativas contienen `Area` y `Subarea`. El dashboard dispone de 29 Áreas y 174 Subáreas en la última extracción. Estas dimensiones ya se incorporaron al grano de datos y a los filtros dependientes.

**Implicación:** Área y Subárea pueden preservarse en el dashboard unificado sin perder la segmentación local.

### H-02 — Motivos disponibles

**Estado:** confirmado.

Las fuentes contienen `Motivo_ausentismo` y `motivosDeSalida`. La última extracción contiene 13 motivos de ausentismo y 27 motivos de baja.

**Implicación:** el dashboard unificado puede mantener el análisis de causas, no sólo los agregados por tipo.

### H-03 — Meses futuros en gráficos de motivos

**Estado:** corregido.

Se detectó que las gráficas de motivos dibujaban octubre–diciembre como valores cero aunque el corte 2026 sólo llega a septiembre. Se corrigió el eje X para dibujar únicamente los meses con información disponible.

**Regla de homologación:** no mostrar meses no publicados como ceros; deben quedar fuera del dominio temporal.

### H-04 — Discrepancia de Turnover frente al Centralizado

**Estado:** abierto y prioritario.

Para TTE, utilizando Renuncia + Despido y HC mensual, el dashboard local calculó:

| Mes 2026 | HC usado | Renuncias | Despidos | TO local |
|---|---:|---:|---:|---:|
| ene | 13,324 | 526 | 385 | 6.84% |
| feb | 13,996 | 624 | 359 | 7.02% |
| mar | 17,036 | 948 | 273 | 7.17% |
| abr | 19,100 | 990 | 712 | 8.91% |
| may | 22,018 | 1,176 | 611 | 8.12% |
| jun | 25,729 | 1,322 | 583 | 7.40% |
| jul | 29,640 | 1,584 | 785 | 7.99% |
| ago | 30,093 | 1,638 | 1,670 | 10.99% |
| sept | 28,424 | 305 | 332 | 2.24% |

La referencia Centralizado mostrada por el equipo no coincide, por ejemplo en enero muestra aproximadamente 8.0%. El denominador implícito de esa referencia es cercano a 7.9k, mientras el cálculo local usa 13.3k.

**Conclusión:** el cálculo actual no puede considerarse homologado con el Centralizado.

**Hipótesis a validar:**

1. El Centralizado usa una población distinta —por ejemplo, segmento, contrato, Site u organización específica— como denominador.
2. El Centralizado usa un corte de HC diferente al HC mensual agregado del dashboard local.
3. Existen exclusiones adicionales de bajas o de HC que aún no están documentadas.
4. La visual de referencia podría combinar filtros activos distintos a los del dashboard local.

**Evidencia requerida para cierre:** definición exacta de la medida/SQL/LookML del Turnover Centralizado, filtros aplicados y desglose de numerador/denominador por mes.

## Matriz de homologación pendiente

| Métrica o dimensión | Local TTE Brasil | Centralizado | Estado | Próxima acción |
|---|---|---|---|---|
| HC mensual | Nómina + Externos | Por confirmar | Abierto | Comparar población y fecha de corte. |
| Turnover mensual | Bajas seleccionadas / HC mensual | Por confirmar | Abierto crítico | Obtener definición de medida Centralizado. |
| Tipos de baja | Renuncia, Abandono, Despido, No cuenta | Visual de referencia usa Renuncia y Despido | Parcial | Alinear tipos y exclusiones. |
| Ausentismo | Gestionable, No gestionable y Otros / Dotación | Por confirmar | Abierto | Confirmar numerador, denominador y exclusiones. |
| Motivos | 13 ABS y 27 TO disponibles | Por confirmar | Disponible localmente | Validar cuáles deben sobrevivir en el dashboard único. |
| Región / operación / Site | Clasificador oficial | Por confirmar | Parcial | Validar catálogo y reglas de mapeo. |
| Área / Subárea | Disponibles en tres fuentes | Por confirmar | Disponible localmente | Validar uso y nomenclatura Centralizado. |

## Próximos pasos recomendados

1. Solicitar la definición técnica del Turnover del Centralizado: SQL, LookML o fórmula y filtros implícitos.
2. Ejecutar una reconciliación mensual de HC y bajas, separada por Segmento, Región, Tipo de operación, Site, Área y Subárea.
3. Registrar cada diferencia con numerador, denominador, población, fecha de corte y regla de exclusión.
4. Acordar la definición canónica de cada métrica con el equipo local y el equipo Centralizado.
5. Construir el dashboard único sólo después de cerrar las diferencias críticas, empezando por Turnover.