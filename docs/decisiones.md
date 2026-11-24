# Decisiones de arquitectura

Cada decisión: qué se eligió, por qué y qué se descartó.

1. **Monorepo con un solo backend.** Los datos se cruzan: la solicitud de la app es la misma que ve el
   analista. La separación entre lo interno y lo público la hacen las APIs y los permisos. EAS compila
   la app con `app_clientes/` como raíz, así que no hace falta otro repositorio.

2. **`canales` dentro de `backend/`.** Los adaptadores necesitan los modelos (conversación, solicitud).
   Afuera haría falta una tercera API con su propia autenticación. Corre en su propio contenedor (`bot`).

3. **Django REST Framework para las dos APIs.** Trae permisos, serializadores y tests listos.
   Cada API tiene sus propios serializadores, para que un campo interno no se filtre por descuido.

4. **Autenticación separada.**
   - Personal: sesión de Django + CSRF, porque el panel se sirve del mismo dominio.
   - Clientes: JWT con `djangorestframework-simplejwt`. El token de acceso dura 10 minutos y el de renovación rota y queda en la lista negra al usarse.
   - El cliente es una `CuentaCliente`, no un `User`, así que nunca puede heredar permisos de personal.

5. **Reglas de crédito en `backend/creditos/reglas.py`.** Funciones puras: sistema francés, costo total,
   tasa efectiva, cuota máxima y comparación con la tasa máxima. La app y los canales piden
   `POST simulaciones` y muestran lo que vuelve, sin calcular nada.

6. **Cola: django-q2 con la base de datos como cola.** No necesita Redis y alcanza para los picos.
   Descartados: Celery (complejo para empezar), RQ (exige Redis), django-q (abandonado).

7. **OCR: Tesseract (`spa`).** Liviano y ya instalado. EasyOCR arrastra PyTorch (más de 1 GB).

8. **Respaldo de visión con LLM: puerto con un adaptador nulo por defecto.** Enviar cédulas a un
   tercero requiere consentimiento (Ley 7593/2025). Si se activa, usa la API de Claude.

9. **Cifrado por campo con Fernet + índice ciego HMAC para la CI.** Claves distintas, en `.env`.

10. **Auditoría con cadena de hashes + triggers en la base.** PostgreSQL bloquea UPDATE, DELETE y
    TRUNCATE; SQLite bloquea UPDATE y DELETE (sí admite triggers). En PostgreSQL, un candado
    (`pg_advisory_xact_lock`) evita que dos eventos simultáneos cuelguen del mismo anterior, y
    `hash_anterior` es único como segunda red.

11. **Parámetros mensuales en la base.** La tasa máxima cambia cada mes; el % de cuota sobre ingreso es
    política de la empresa. Los valores sin confirmar se marcan `es_supuesto`.

12. **Score:** regresión logística como modelo principal y `HistGradientBoostingClassifier` como
    comparación, con validación temporal. La explicación sale de los coeficientes en la logística y de
    *permutation importance* en el boosting. El sesgo se mide por sexo y edad, que no son variables del modelo.
    Limitación: con datos sintéticos el modelo aprende las reglas del generador.

13. **Telegram por long polling** para la demo. WhatsApp Cloud API queda escrito y testeado contra un
    adaptador de memoria, sin probar contra Meta (necesita una cuenta de empresa verificada).

14. **Panel: HTML + JavaScript sin framework, servido por Django.** Sin paso de compilación; la misma
    sesión vale para el panel y `/api/interna/`.

15. **App: React Native + Expo con TypeScript.** Un solo código para Android e iOS; Edu ya sabe JavaScript.
    - Tokens guardados en `expo-secure-store`.
    - Biometría con `expo-local-authentication`; solo desbloquea el token, no prueba la identidad.
    - Demo en Android, porque Face ID no funciona en Expo Go.

16. **Confiabilidad de la app.**
    - `GET /api/clientes/version` solo **recomienda** actualizar: el aviso nunca bloquea consultar la deuda ni pagar.
    - Límite de errores por pantalla.
    - Tiempos de espera y reintentos.
    - La última respuesta se guarda en caché y se muestra con su fecha si no hay conexión.

17. **Pagos detrás del puerto `PasarelaPago`.** Una casa de crédito no puede guardar dinero ajeno: el pago
    lo procesa una pasarela externa. `IntentoPago` separa "iniciado" de "confirmado".
    En la demo, el adaptador es simulado.

18. **Docker Compose con cuatro servicios** (`db`, `web`, `worker`, `bot`). La app no va en Docker:
    corre en el celular y apunta a `web` (en Render para una reunión fuera de casa).

19. **Django 5.2 LTS** (soporte hasta abril de 2028), no la serie 6.x: DRF, django-q2 y simplejwt la
    soportan bien y no necesitamos nada de la 6.

20. **`crear_env.py` como script suelto, no como comando de Django.** Django no arranca sin las claves;
    el script que las crea tiene que funcionar sin Django. Nunca pisa un `.env` existente.

21. **`cargar_sinteticos` mueve las fechas a hoy.** Los datos tienen un "hoy" fijo (31/10/2026); sin
    moverlas, las cuotas vencidas desde entonces aparecerían impagas sin motivo.

22. **Datos laborales e ingreso del cliente, cifrados.** Son datos personales. Para filtrar y agrupar el
    dashboard se usan copias no personales en `Credito` (sucursal, segmento, canal, cosecha).

23. **Umbral de confianza del OCR: 0,90**, medido con `evaluar_ocr` sobre 105 imágenes sintéticas
    (99,4 % de los campos aceptados sin revisión estaban bien; 84 % se acepta sin revisión). Es técnico,
    no regulatorio: se vuelve a medir con documentos reales.

24. **Sin binarizar la imagen.** Probado: pasar a blanco y negro puro para borrar la marca de agua
    empeoró la lectura. Se usa escala de grises + autocontraste, y enderezado solo si la confianza es baja.

25. **Rótulo primero, forma después.** El extractor busca el valor debajo de su rótulo; si el rótulo
    salió ilegible, reconoce la CI y los montos por su forma, con 10 % menos de confianza.

26. **Cruce entre documentos.** Si la CI o el salario coinciden en dos o más documentos, el campo se
    acepta; si no coinciden, todos quedan "para revisar". El nombre se compara sin tildes.

27. **Visión con Claude (opcional):** modelo `claude-opus-5-5`, esfuerzo bajo, salida estructurada con
    esquema JSON y *fallbacks* del servidor ante rechazos. Su confianza es autodeclarada (no calibrada):
    el analista revisa igual. Cualquier error deja el campo "para revisar"; nunca se inventa un valor.

28. **Los documentos se "toman" con un UPDATE condicional**, no con una transacción larga: el OCR tarda
    segundos y SQLite bloquearía la base entera. Un documento abandonado (worker caído) se retoma a los 5 minutos.

