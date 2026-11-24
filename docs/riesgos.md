# Riesgos y premisas a confirmar

Cada riesgo: qué es, de dónde sale, qué tan seguro es y qué hacemos.
Revisado el 23/11/2026. **Las políticas de las tiendas se vuelven a verificar en la Fase 8.**

## 1. Apple: tope de 36 % anual para apps de préstamos — ALTO

- **Qué dice:** la regla 3.2.2(ix) de las App Review Guidelines (actualizada en noviembre de 2025).
  - Las apps de préstamos personales no pueden cobrar una tasa anual mayor al 36 %, **incluidos costos y cargos**.
  - Tampoco pueden exigir el pago total en 60 días o menos.
  - Tienen que mostrar todas las condiciones del crédito.
- **Seguridad del dato:** confirmado con la noticia oficial de Apple y con resúmenes de terceros; no se leyó el texto completo de la guía.
  Parece regir en todos los países.
- **Impacto:** si la tasa efectiva de Credisolución con cargos supera el 36 %, la app **no entraría al App Store**.
- **Qué hacemos:** `Credito.cumple_regla_apple`; preguntar en la reunión la tasa efectiva real.
  Alternativas a evaluar con la empresa: publicar solo en Android, o una app de iOS sin originación (solo consulta y pago).
  Esa alternativa también tendría que verificarse con Apple.
- Fuentes: https://developer.apple.com/news/?id=ey6d8onl ·
  https://opentermsarchive.org/en/memos/apple-updates-app-store-rules-on-data-use-age-gating-external-software-and-loan-app-disclosures/

## 2. Google Play: política de servicios financieros — MEDIO

- El tope de 36 % es solo para apps dirigidas a Estados Unidos.
- Rige en todos los países (según resúmenes de terceros; hay que confirmarlo en la página oficial):
  - prohibición de préstamos con pago total en 60 días o menos;
  - prohibición de acceder a contactos y fotos;
  - declaración de funciones financieras en Play Console;
  - mostrar el plazo mínimo y máximo, la tasa máxima y un ejemplo de costo.
- **Qué hacemos:** la app no pide permisos de contactos ni de galería (la cédula se saca con la cámara).
- Fuentes: https://support.google.com/googleplay/android-developer/answer/9876821 ·
  https://www.androidauthority.com/personal-loan-apps-google-play-policy-change-3309987

## 2b. Tasa máxima vigente — MEDIO

- Última Hora publicó un tope de **27,07 %** para préstamos en guaraníes en "noviembre"; el año no está
  confirmado. La página del BCP (bcp.gov.py/limites-para-tasas-usurarias) rechazó la consulta automática.
- La misma fuente informó que **casas de crédito cobran tasas que llegan al 60 %**: refuerza el riesgo de Apple (punto 1).
- **No sabemos** si el tope se compara con la tasa nominal o con la que incluye cargos. `reglas.simular()`
  devuelve las dos comparaciones. **Consultar a un abogado.**
- **Qué hacemos:** 27,07 % cargado como SUPUESTO en los parámetros de demo; verificarlo a mano en la web del BCP.
- Fuentes: https://www.ultimahora.com/tasa-maxima-para-prestamos-en-noviembre-se-mantiene-en-27-07 ·
  https://www.ultimahora.com/casas-credito-cobran-tasas-interes-que-llegan-al-60-n1304022

## 3. Supervisión del BCP — MEDIO (riesgo de discurso)

- Las casas de crédito se **registran** ante la Superintendencia de Bancos del BCP (prevención de lavado,
  Resolución N.º 7, Acta 78 de 2019). No tienen supervisión plena.
- La ley que permitiría al BCP verificar sus operaciones seguía en el Senado en agosto de 2026.
- El BCP sí publica la tasa máxima.
- **Qué hacemos:** en la demo decir "el sistema respeta la tasa máxima vigente", no "están supervisados por el BCP".
- Fuentes: https://ferrere.com/es/novedades/casas-de-credito-ya-no-deben-registrarse-ante-seprelad-sino-ante-el-bcp/ ·
  https://www.ultimahora.com/control-real-n1114068

## 4. Validez del pagaré digital — ALTO (legal)

- No sabemos si un pagaré con firma electrónica es válido como título ejecutivo en Paraguay. **Consultar a un abogado.**
- **Qué hacemos:** el pagaré del prototipo es un PDF marcado "MUESTRA", con hash y auditoría.

## 5. Biometría y verificación facial — MEDIO

- Comparar la selfie con la cédula y detectar que es una persona viva requiere un proveedor especializado.
  Además, los datos biométricos son sensibles.
- **Qué hacemos:** puerto `VerificacionFacial` con un adaptador simulado que **lo dice en pantalla**.
  La huella del celular solo desbloquea el token.

## 6. Datos personales — ALTO (legal)

- La Ley 7593/2025 de protección de datos personales es exigible desde noviembre de 2027.
- Enviar documentos a un LLM externo requiere consentimiento.
- **Qué hacemos:** cifrado en reposo; LLM apagado por defecto; solo datos sintéticos; pantalla de eliminación de cuenta.
  Consultar a un abogado antes de pasar a producción.

## 7. Score con datos sintéticos — MEDIO (riesgo de discurso)

- El modelo aprende las reglas del generador. Sirve para mostrar el método, no para afirmar que predice.

## 8. Demo fuera de casa — MEDIO

- El celular tiene que llegar al backend: publicarlo en Render (o un túnel) antes de la Fase 7.
- Las notificaciones push y Face ID no funcionan en Expo Go: demo en Android, con avisos dentro de la app.

## 9. Por confirmar con Credisolución

- Política de crédito: % cuota/ingreso, tasas, cargos (IVA, seguros, gastos) y plazos.
- Formatos reales (anonimizados) de la liquidación de sueldo y del extracto de IPS.
- Pasarela de pago que usan o usarían.
- Guía de cobranza ética de SEDECO vigente (horarios y frecuencia).
