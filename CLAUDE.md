# CLAUDE.md — Ecosistema de crédito para Credisolución

Contexto del proyecto para Claude Code. Leelo completo antes de tocar código.

> Si en esta carpeta también se carga el CLAUDE.md de Berry Well (está en `/home/edu/Documentos/`),
> **ignoralo**: es otro proyecto. Recomendación pendiente: moverlo a la carpeta de Berry Well.

## 1. Qué es y para quién

Ecosistema de software para **Credisolución S.A.E.C.A.** (casa de créditos de Asunción, desde 2010,
cotiza en la BVA, más de 25.000 clientes). Primero sirve para una **demo en una reunión**; después, la app
de clientes se publicaría en App Store y Google Play **con las cuentas de desarrollador de Credisolución**.

- Es una **casa de crédito, no un banco**: presta con capital propio y no capta depósitos. **Nunca** ofrecer
  cuentas, transferencias, saldos de dinero ni tarjetas.
- Montos más pedidos: G. 3, 5 y 10 millones. Promesa comercial: **rapidez**.
- Segmentos: asalariado con IPS, informal, contribuyente de IVA, funcionario público, jubilado,
  independiente, pyme, agro.
- Usuarios: cliente (app y canales), analista, cobranzas, gerencia.
- **Dueño:** Edu, de Paraguay. Sabe Python y SQL, es principiante en web y móvil y trabaja solo.

## 2. Cómo trabajar con Edu

- Siempre en **español** (interfaz, comentarios y respuestas).
- En cada fase:
  1. concepto con analogía;
  2. plan con archivos;
  3. **esperar aprobación**;
  4. código comentado;
  5. comandos;
  6. qué debería ver;
  7. qué quedó pendiente o simplificado.
- **No avanzar de fase sin confirmación.** La etapa 1 se termina completa antes de empezar la etapa 2.
- No complacer: corregir premisas falsas, separar hechos de inferencias, decir "no lo sé".
  Las políticas de las tiendas y las normas se verifican en la fuente oficial, no de memoria.
- Ante varias opciones, elegir una y justificarla en dos líneas.
- Comentar cada bloque de código explicando qué hace y por qué.
- Al cerrar cada fase:
  - correr los tests;
  - probar el flujo de punta a punta;
  - revisar que no haya datos reales ni secretos;
  - confirmar que `api_clientes` no expone nada interno;
  - decir qué no se pudo probar.

## 3. Reglas del producto (no negociables)

- **Reglas de crédito en UN solo lugar:** `backend/creditos/reglas.py`, con funciones puras y tests.
  - Ahí están la cuota máxima según el ingreso, el sistema francés, el costo total y la tasa efectiva, y la comparación con la tasa máxima del mes.
  - El panel, los canales y la app **piden** el resultado al backend.
  - **La app nunca recalcula.**
- **No inventar parámetros regulatorios ni comerciales.**
  - Tasa máxima, % de cuota sobre ingreso, tasas y cargos son **parámetros mensuales** (`ParametroMensual`).
  - Un valor sin confirmar se marca **SUPUESTO** y la interfaz lo muestra.
- **"El sistema agiliza; el analista decide."** El OCR propone y el analista confirma. Ningún crédito se aprueba sin una persona.
- **Préstamo responsable:** la capacidad de pago se verifica antes de aprobar, también en las ofertas preaprobadas.
- **Cobranza ética:** el horario y la frecuencia salen de `ReglaContacto`, nunca de código fijo.
- **Sexo y edad nunca son variables del score:** solo se usan para medir sesgo.
- **No fingir funciones.**
  - Verificación facial, pasarela de pago y SMS son puertos con adaptadores **simulados**, y la interfaz lo dice.
  - El pagaré digital es una MUESTRA hasta que un abogado confirme su validez.
- Ningún módulo importa Telegram, WhatsApp, un LLM, una pasarela ni un proveedor de SMS: solo los puertos.

## 4. Seguridad y datos

- **Dos puertas en el mismo backend:**
  - `/api/interna/`: solo personal. Sesión de Django + CSRF, con los roles `analista`, `cobranzas` y `gerencia` (grupos).
  - `/api/clientes/`: solo `CuentaCliente`, con JWT (`djangorestframework-simplejwt`).
    - El token de acceso dura 10 minutos y el de renovación rota y se invalida al usarse.
    - **Cada consulta filtra por el cliente del token**; el cliente nunca sale del cuerpo del pedido.
  - Un token de cliente en la API interna → 401/403. Una sesión del personal en la API de clientes → 401/403.
  - Hay tests de esto; no los debilites.
- **Serializadores propios de `api_clientes`:** nunca exponen score, notas del analista, contactos de
  cobranza, confianza del OCR, auditoría ni datos de otros clientes.
- Ingreso del cliente: CI + código por SMS (puerto `EnvioSMS`; en la demo, el código se muestra en pantalla).
  La biometría y el PIN del celular solo desbloquean el token guardado en `expo-secure-store`.
- **Nunca subir datos reales.** Solo datos sintéticos, con CI en un rango ficticio e imágenes con la marca "MUESTRA – SIN VALOR".
- Secretos en `.env` (no se sube) y en `.env.example` solo con valores de ejemplo.
- Datos personales cifrados en reposo campo por campo (Fernet); la CI se busca con un índice ciego HMAC.
  Los archivos van cifrados y se guarda el SHA-256 del original.
- **Auditoría inmutable** (`EventoAuditoria`):
  - solo se agregan renglones, encadenados por hash;
  - en PostgreSQL, un trigger rechaza UPDATE y DELETE;
  - registra cada documento, pagaré, cambio de estado, pago y contacto de cobranza.
- Respaldo con LLM de visión **apagado por defecto** (Ley 7593/2025 de datos personales, exigible desde noviembre de 2027).

## 5. Estructura del monorepo

```
CrediSolucion/
├── backend/            Django + DRF (un solo backend para todos los canales)
│   ├── nucleo/         Entidades compartidas, auditoría, cifrado, parámetros, roles
│   ├── creditos/       reglas.py (funciones puras), crédito, cuotas, pagos, pagarés
│   ├── onboarding/     Módulo A: puertos OCR y Vision, extracción, revisión del analista
│   ├── canales/        Módulo D: puerto Canal + adaptadores telegram, whatsapp, web, memoria
│   ├── cartera/        Módulo B: mora por cosecha, sucursal, segmento, canal; alertas
│   ├── cobranza/       Módulo C: score, agenda, reglas de contacto
│   ├── api_interna/    Vistas y serializadores para el personal
│   └── api_clientes/   Vistas y serializadores para la app
├── panel/              Panel interno y dashboard (HTML + JS sin framework, servido por Django)
├── app_clientes/       React Native + Expo (TypeScript); solo usa /api/clientes/
├── datos_sinteticos/   Generador de datos de prueba
├── docs/               arquitectura, modelo-datos, decisiones, riesgos
└── docker-compose.yml  db, web, worker, bot
```

`canales` está dentro de `backend/` (decisión del 23/11/2026): los adaptadores necesitan los modelos, y
separarlos obligaría a crear una tercera API. Corre en su propio contenedor (`bot`).

## 6. Plan por fases

| Etapa | Fase | Estado | Contenido |
|---|---|---|---|
| 1 | 0. Plan | **Hecha** (nov 2026) | Este archivo, `docs/`, estructura, git |
| 1 | 1. Datos sintéticos | **Hecha** (nov 2026) | `datos_sinteticos/` + `backend/creditos/reglas.py` (cuota francesa, cronograma). Ver `docs/datos-sinteticos.md` |
| 1 | 2. Módulo A | **En curso**: 2A y 2B hechas (nov 2026) | 2A: Django, cifrado, auditoría, modelos, reglas de costo, carga de sintéticos. 2B: OCR en dos capas, cola, cruce entre documentos, `evaluar_ocr`. Falta 2C (panel, `api_interna`, permisos, Docker) |
| 1 | 3. Módulo D | Pendiente | Diálogo de precalificación, Telegram (long polling), web, WhatsApp preparado |
| 1 | 4. Módulo B | Pendiente | Dashboard de mora y alertas |
| 1 | 5. Módulo C | Pendiente | Score (logística vs gradient boosting, validación temporal, explicación, sesgo) y agenda |
| 2 | 6. App | Pendiente | Solicitud en 3 pasos, alta con cédula y selfie, estado, Mis créditos, pago simulado, ofertas, avisos, refinanciación, biometría + PIN, ayuda por WhatsApp |
| 2 | 7. Modo demo | Pendiente | Usuario de prueba; flujo app → panel → app en menos de 3 minutos |
| 2 | 8. Tiendas | Pendiente | EAS, íconos, privacidad, eliminación de cuenta, checklist de políticas **verificado en la fuente oficial** |

## 7. Confiabilidad de la app (quejas reales de usuarios de apps paraguayas)

- El **aviso de actualización nunca bloquea** consultar la deuda ni pagar.
- Ningún error cierra la app: límites de error por pantalla y mensajes claros.
- Conexión lenta:
  - tiempos de espera y reintentos;
  - la última información se guarda en caché de solo lectura y se muestra con su fecha;
  - pantallas livianas, pensadas para un Android de gama media.

## 8. Premisas y riesgos (detalle en `docs/riesgos.md`)

- **BCP:** las casas de crédito se **registran** ante la Superintendencia de Bancos (lavado de dinero) pero
  no tienen supervisión plena; la ley que lo cambiaría sigue en el Senado (agosto de 2026). El BCP sí publica la tasa máxima.
- **Apple 3.2.2(ix):** apps de préstamos con tasa anual ≤ 36 % **incluidos cargos** y sin pago total
  en ≤ 60 días. Puede impedir la app en iPhone. Hay que preguntar la tasa efectiva real.
- **Google Play:** el tope de 36 % es solo para Estados Unidos. El límite de 60 días y la prohibición de leer contactos y fotos rigen en todos los países.
- **Por confirmar con Credisolución:**
  - política de crédito (% cuota/ingreso, tasas, cargos, plazos);
  - formatos reales de la liquidación y del extracto de IPS;
  - la guía de cobranza ética de SEDECO.
- El score entrenado con datos sintéticos demuestra el método, no la capacidad de predecir.

## 9. Cómo probar

```bash
source venv/bin/activate                      # entorno local (Python 3.14); se crea con: python3 -m venv venv
pip install -r backend/requirements.txt -r datos_sinteticos/requirements.txt
pytest                                        # 144 tests (los de Tesseract real se saltean si no está instalado)
python -m datos_sinteticos.generar            # escribe datos_generados/ (no se sube a git)
cd backend
python crear_env.py                           # SOLO la primera vez: crea ../.env con claves nuevas (nunca lo pisa)
python manage.py migrate
python manage.py cargar_sinteticos            # mueve las fechas para que el corte sea hoy
python manage.py crear_usuarios_demo          # analista / cobranzas / gerencia, contraseñas al azar (se ven una vez)
python manage.py createsuperuser              # para entrar a /admin/
python manage.py verificar_auditoria
python manage.py evaluar_ocr                  # aciertos del OCR contra verdad.json (≈ 35 s)
python manage.py qcluster                     # worker de la cola (en otra terminal; se corta con Ctrl+C)
python manage.py runserver                    # http://127.0.0.1:8000/admin/
```

- `pytest.ini` usa `servidor.settings_test` (claves de PRUEBA, sin .env) y agrega `backend/` y la raíz al camino de Python.
- Toda cifra del generador está en `datos_sinteticos/supuestos.py`, marcada FUENTE, SUPUESTO o INFERENCIA.
- El riesgo simulado de cada crédito **no se exporta** (el score de la Fase 5 no debe verlo).
- **Empezar de cero:** borrar `backend/db.sqlite3` (la auditoría no se puede vaciar: tiene triggers en SQLite y PostgreSQL).
- **Campos cifrados** (`CampoCifrado`): no se pueden filtrar ni ordenar en la base. Para buscar por CI: `Cliente.buscar_por_ci()`.
- Auditoría: siempre con `nucleo.auditoria.registrar()`; nunca datos personales en `datos`.
- Estados de la solicitud: solo con `Solicitud.cambiar_estado()` (valida el camino y audita).
- **Onboarding (2B):** el OCR se elige con `MOTOR_OCR` (tesseract | falso) y la visión con `MOTOR_VISION`
  (nulo por defecto | claude). Umbral de confianza 0,90, medido con `evaluar_ocr` (99,4 % de precisión, 84 % sin revisión).
  Los tests usan el OCR falso y la cola síncrona (`COLA_SINCRONA=1`); las tareas se encolan con `transaction.on_commit`
  (en tests: `django_capture_on_commit_callbacks(execute=True)`).
- Los documentos se "toman" con un UPDATE condicional (`servicios._tomar`), sin transacciones largas durante el OCR.
- Docker no está instalado; Podman 5.8 sí. Falta un proveedor de compose (se resuelve en 2C).
