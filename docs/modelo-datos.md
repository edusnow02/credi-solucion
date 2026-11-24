# Modelo de datos

Analogía: cada tabla es un tipo de carpeta del archivo central. Las flechas son "esta carpeta
menciona a aquella" (clave foránea). Todas las tablas viven en el **mismo backend**: lo que pide la
app es lo mismo que ve el analista.

```
CuentaCliente 1──1 Cliente 1──* Solicitud 1──* Documento 1──* CampoExtraido
                     │              │
                     │              1──1 Credito 1──* Cuota
                     │                     │ 1──* Pago ◄──1 IntentoPago
                     │                     │ 1──* Pagare
                     │                     │ 1──* ScoreAtraso
                     │                     │ 1──* ContactoCobranza
                     │                     │ 1──* PedidoRefinanciacion
                     │                     *──1 ParametroMensual
                     1──* OfertaPreaprobada
                     1──* Aviso
Conversacion *──1 Solicitud (opcional)
EventoAuditoria → cualquier entidad (tipo + id)
```

🔒 = cifrado en reposo. 🚫 = nunca sale por `api_clientes`.

## Cliente
| Campo | Tipo | Nota |
|---|---|---|
| id | UUID | |
| ci | texto 🔒 | |
| ci_indice | texto, único | HMAC-SHA256 de la CI normalizada; permite buscar sin descifrar |
| nombre, telefono, correo | texto 🔒 | |
| fecha_nacimiento | texto 🔒 | Solo para la auditoría de sesgo por edad 🚫 |
| sexo | F / M / sin dato | Solo para la auditoría de sesgo; **nunca** entra al score 🚫 |
| segmento | opción | ips, informal, iva, funcionario, jubilado, independiente, pyme, agro |
| sucursal | texto | |
| canal_origen | opción | app, telegram, whatsapp, web, telefono, sucursal |
| creado | fecha y hora | |

## CuentaCliente (acceso a la app)
| Campo | Tipo | Nota |
|---|---|---|
| cliente | FK única | |
| activa | sí/no | |
| pin_hash | texto | Hash del PIN (nunca el PIN) |
| ultimo_ingreso | fecha y hora | |
| eliminacion_pedida | fecha y hora | Pedido desde la app; se procesa respetando lo que la ley obliga a conservar |

Separada del `User` de Django: un cliente **nunca** puede tener rol de personal.
Los tokens de renovación invalidados se guardan en la tabla de simplejwt (lista negra).

## Solicitud
| Campo | Tipo | Nota |
|---|---|---|
| cliente | FK | |
| monto_pedido | entero (G.) | Guaraníes, sin decimales |
| plazo_meses | entero | |
| canal | opción | |
| estado | opción | borrador → faltan_documentos → en_ocr → en_revision → aprobada / rechazada / desistida |
| ingreso_confirmado | entero (G.) | Lo confirma el analista |
| cuota_maxima | entero (G.) | Calculada por `reglas.py` |
| analista | FK usuario 🚫 | |
| notas_analista | texto 🚫 | |
| motivo_rechazo | texto | Se muestra al cliente en lenguaje simple |
| oferta | FK OfertaPreaprobada (opcional) | |
| creado, actualizado | fecha y hora | |

## Documento
| Campo | Tipo | Nota |
|---|---|---|
| solicitud | FK | |
| tipo | opción | ci_frente, ci_dorso, selfie, liquidacion, extracto_ips |
| archivo | archivo 🔒 | |
| sha256 | texto | Del original; prueba que no se alteró |
| estado | opción | recibido, procesando, legible, ilegible |
| verificacion_facial | JSON | Solo para la selfie; dice `simulado: true` mientras no haya proveedor 🚫 |
| recibido | fecha y hora | |

## CampoExtraido 🚫
documento, nombre (nombre, ci, empleador, salario, antiguedad_meses…), valor_ocr 🔒, confianza (0–1),
motor (tesseract, vision), valor_confirmado 🔒, confirmado_por, confirmado_en.

## Credito
| Campo | Tipo | Nota |
|---|---|---|
| solicitud | FK única | |
| monto, plazo_meses | entero | |
| tasa_nominal_anual | decimal | |
| cargos | JSON | Lista {concepto, monto, periodicidad}; conceptos por confirmar |
| costo_total | entero (G.) | Todo lo que paga el cliente |
| tasa_efectiva_anual | decimal | Con cargos; se compara con la tasa máxima del mes |
| cumple_regla_apple | sí/no | Tasa efectiva ≤ 36 % y plazo > 60 días (ver `riesgos.md`) 🚫 |
| parametro | FK ParametroMensual | La tasa máxima vigente que se aplicó |
| fecha_desembolso | fecha | Define la **cosecha** |
| sucursal, segmento, canal | copia | Para filtrar el dashboard |
| estado | opción | vigente, cancelado, en_mora, castigado, refinanciado |

## Cuota
numero, vencimiento, capital, interes, cargos, total, saldo_pendiente, estado (pendiente, pagada, atrasada), fecha_pago.

## Pagare
| Campo | Nota |
|---|---|
| credito | |
| archivo 🔒 | PDF; en el prototipo, marcado "MUESTRA" |
| sha256 | Huella del archivo |
| estado | emitido, firmado, devuelto, anulado |
| firmado_en, devuelto_en | El pagaré se **devuelve** (o se anula) al cancelar el crédito; queda en la auditoría |

## IntentoPago
credito, cuotas (lista), monto, pasarela, referencia_externa, estado (iniciado, aprobado, rechazado, vencido), creado.
Recién cuando la pasarela confirma se crea el `Pago`. Así un pago a medio camino no marca la cuota como pagada.

## Pago
credito, cuota (opcional), fecha, monto, medio (app, sucursal, boca de cobranza…), intento (opcional),
comprobante_sha256, registrado_por. Se guardan **todos**, también los pagos al día (idea del Cadastro Positivo).

## ParametroMensual
mes (único), tasa_maxima (BCP), pct_max_cuota_ingreso, cargos_por_defecto (JSON), fuente, es_supuesto.

## OfertaPreaprobada
cliente, monto_maximo, plazo_maximo, valida_hasta, motivo (p. ej., "al día los últimos 6 meses"), estado.
"Preaprobada" no es "aprobada": al aceptarla se crea una `Solicitud` que pasa por las reglas y el analista.

## PedidoRefinanciacion
credito, motivo, cuota_deseada, estado (pedido, en_revision, aceptado, rechazado), creado.

## Aviso
cliente, tipo (vencimiento, estado_solicitud, oferta, general), texto, leido, creado.
La app los muestra adentro; las notificaciones push quedan para una build (Fase 6).

## ScoreAtraso 🚫
credito, fecha, probabilidad, modelo_version, explicacion (JSON: aporte de cada variable).

## ReglaContacto 🚫
nombre, hora_desde, hora_hasta, dias_permitidos, max_contactos_por_semana, activa, fuente.

## ContactoCobranza 🚫
credito, fecha_hora, canal, agente, resultado (contactado, no_atiende, promesa_pago…), nota.

## Conversacion
canal, id_externo 🔒, paso_actual, datos_parciales (JSON), solicitud (opcional), actualizado.

## EventoAuditoria 🚫 (solo agregar)
| Campo | Nota |
|---|---|
| id | Secuencial |
| fecha | |
| actor | Usuario, "sistema" o "cliente:canal" |
| accion | documento_recibido, pagare_emitido, estado_cambiado, campo_corregido, pago_registrado, contacto_cobranza… |
| entidad, entidad_id | A qué se refiere |
| datos | JSON, **sin** datos personales en claro |
| hash_anterior, hash | `hash = SHA256(hash_anterior + contenido)`; si alguien altera un renglón, la cadena se rompe |
