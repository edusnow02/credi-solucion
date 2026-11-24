# Arquitectura

## Analogía

Un edificio con **un solo archivo central** (el backend) y **dos puertas**:

- **Puerta del personal (`/api/interna/`):** se entra con credencial y rol. Lo usan el panel y el dashboard.
- **Ventanilla del público (`/api/clientes/`):** cada cliente muestra un ticket que vence en minutos
  (token) y solo le alcanzan **sus** carpetas. Desde la ventanilla nunca se abre la puerta del personal.

Adentro, cada piso es un módulo, y todos usan las mismas carpetas. Los **puertos** son los enchufes
de la pared y los **adaptadores** son los cables (Telegram, WhatsApp, pasarela de pago, SMS…).

## Diagrama

```
 Telegram ─┐                                        App (Expo) ── /api/clientes/ (JWT) ─┐
 WhatsApp ─┼─► Puerto Canal ─► D: precalificación ─┐                                     │
 Web      ─┘                                       ▼                                     ▼
                                   Solicitud + Documentos ◄──────────────────── api_clientes
                                           │ (cola django-q2)
                                           ▼
   A: Onboarding ─ Puerto OCR (Tesseract) ─(confianza baja)─► Puerto Vision (nulo | LLM)
                                           │ analista confirma y aprueba (panel ─ /api/interna/)
                                           ▼
   creditos/reglas.py  →  Crédito · Cuotas · Pagaré · Pagos ◄── Puerto PasarelaPago (simulado)
                                           │
               ┌───────────────────────────┴───────────────────────────┐
   B: Cartera y mora (dashboard, alertas)                C: Score + agenda de cobranza
                                           │
                         EventoAuditoria (cadena de hashes, solo agregar)
```

## Contenedores (docker-compose)

| Servicio | Qué corre | Por qué está separado |
|---|---|---|
| `db` | PostgreSQL | Base de datos única |
| `web` | Django + DRF (gunicorn); sirve también `panel/` | Panel, las dos APIs, formulario web |
| `worker` | `manage.py qcluster` (django-q2) | OCR y tareas largas sin trabar la web |
| `bot` | `manage.py bot_telegram` | Long polling de Telegram; no necesita una URL pública |

La app (`app_clientes/`) **no** corre en Docker: corre en el celular (Expo Go o build interna) y
se conecta a `web`. Para una reunión fuera de casa, `web` tiene que estar publicado (Render).

## Las dos APIs

| | `/api/interna/` | `/api/clientes/` |
|---|---|---|
| Quién | Personal (usuario de Django en un grupo) | `CuentaCliente` (sin usuario de Django) |
| Autenticación | Sesión + CSRF (el panel se sirve del mismo dominio) | JWT: acceso 10 min, renovación que rota |
| Permisos | Por rol: analista, cobranzas, gerencia | Solo los datos de su propio cliente |
| Serializadores | Completos para el rol | Propios, sin datos internos |

Lo que `api_clientes` **nunca** devuelve: score, explicación del score, contactos de cobranza, notas del
analista, confianza del OCR, auditoría, analista asignado ni datos de otros clientes.

Endpoints previstos de `api_clientes` (Fase 6):
- `POST auth/codigo`, `POST auth/verificar`, `POST auth/renovar`
- `POST simulaciones`: monto y plazo → cuota, costo total y tasa efectiva, calculados por `reglas.py`
- `POST solicitudes`, `GET solicitudes/{id}` (estado), `POST solicitudes/{id}/documentos`
- `GET creditos`, `GET creditos/{id}` (cuotas, historial), `GET creditos/{id}/pagare`, `GET pagos/{id}/comprobante`
- `POST pagos/intentos`: inicia el pago en la pasarela
- `GET ofertas`, `POST refinanciaciones`, `GET avisos`
- `GET version`: versión mínima recomendada (el aviso **nunca bloquea**)
- `DELETE cuenta`: pedido de eliminación de cuenta (obligatorio en las tiendas)

## Puertos y sus métodos

Cada puerto es una clase abstracta en `<app>/puertos.py`. Los adaptadores viven en `<app>/adaptadores/`
y se eligen con una variable de `.env`. Todos tienen un adaptador de memoria o simulado para los tests.

| Puerto | App | Métodos | Adaptadores |
|---|---|---|---|
| `Canal` | canales | `enviar_texto`, `enviar_opciones`, `descargar_archivo` | telegram, whatsapp (preparado), web, memoria |
| `MotorOCR` | onboarding | `leer(imagen) -> texto + palabras con confianza` | tesseract, falso |
| `MotorVision` | onboarding | `extraer(imagen, tipo, campos) -> {campo: (valor, confianza)}` | nulo (por defecto), claude |
| `VerificacionFacial` | onboarding | `comparar(selfie, foto_ci) -> resultado` | simulado (lo dice en pantalla) |
| `PasarelaPago` | creditos | `iniciar(intento) -> url/referencia`, `confirmar(notificacion)` | simulado |
| `EnvioSMS` | nucleo | `enviar(telefono, texto)` | consola (demo) |

## Flujo de la demo (Fase 7)

1. En la app, el cliente elige monto y plazo; el backend devuelve la cuota y el costo total.
2. El cliente escanea la cédula y saca la selfie. El backend crea la `Solicitud` y los `Documento` y encola el OCR.
3. El worker extrae los campos con su confianza y marca faltantes o ilegibles.
4. En el panel, el analista confirma o corrige los campos y aprueba.
5. Se crean el `Credito`, las `Cuota` y el `Pagare` (MUESTRA). Todo queda en la auditoría.
6. La app muestra el crédito y la primera cuota. El dashboard y la agenda de cobranza ya lo incluyen.
